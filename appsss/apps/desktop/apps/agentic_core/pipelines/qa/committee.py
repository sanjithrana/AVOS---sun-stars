"""
QA committee (Week 3 Day 14, Engineer 2 - AVOS-03 v1.1 s15, AVOS-08 s?).

Pure logic: given a shot's content, its physics-proxy scene layout (the
Blender scaffold from Day 12) and one generated candidate's thumbnail
bytes, score the shot across the 6 AVOS-06 QA dimensions and return a
QAResult. No I/O here - the api layer (services/qa_service.py) is what
reads the physics-proxy/candidate assets from the Asset Registry and
persists the result; this module only judges what it's handed, so it's
directly unit-testable with fabricated inputs (including deliberately
"wrong" ones, to force a FAIL and drive the repair ladder).

Two dimensions are real this week:

  - VISUAL: is the candidate's frame a well-formed, correctly-sized
    image? (decodes the thumbnail PNG and checks its declared size)
  - GEOMETRY: does the *rendered* physics scaffold's subject size match
    what the shot's camera framing (wide/medium/close_up/insert) claims?
    (compares the Blender proxy's subject_box against the same
    shot-type -> scale mapping MockBlenderClient itself renders with, so
    a mismatch here is a genuine, meaningful continuity-of-framing bug,
    not an arbitrary threshold)

The other 4 (temporal, identity, audio, prompt_adherence) are explicit
placeholders (score=1.0, confidence=0.5, diagnostics.todo=True) until a
real video/audio model exists to judge them - Week 4+.
"""

import struct
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from packages.contracts.qa import (
    QADimension,
    QADimensionResult,
    QAIssue,
    QAResult,
    QAStatus,
)
from packages.contracts.shotspec import ShotContent


def _png_size(data: bytes) -> tuple[int, int]:
    """(width, height) from a PNG's IHDR. agentic_core stays independent
    of the api layer's encoder (src/core/blender/png.py) - this reads
    the same 8 bytes of any standard PNG, so the two never need to share
    an import."""
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not a PNG")
    return struct.unpack(">II", data[16:24])

# Same shot_type -> subject-box scale MockBlenderClient renders with
# (src/core/blender/client.py). Geometry QA checks the *rendered* scene
# against this mapping - if they disagree, the proxy is stale/wrong for
# this shot's current framing.
SHOT_TYPE_SCALE = {"wide": 0.3, "medium": 0.5, "close_up": 0.75, "insert": 0.6}
GEOMETRY_TOLERANCE = 0.08  # absolute scale-ratio slack before it's a fail

REAL_PASS_THRESHOLD = 0.6
PLACEHOLDER_DIMENSIONS = (
    QADimension.TEMPORAL,
    QADimension.IDENTITY,
    QADimension.AUDIO,
    QADimension.PROMPT_ADHERENCE,
)


@dataclass(frozen=True)
class PhysicsScene:
    """The subset of the physics_proxy asset's JSON doc geometry QA
    needs (src/services/blender_stage_service.py's `proxy_doc["scene"]`)."""

    width: int
    height: int
    subject_box: tuple[int, int, int, int]  # x0, y0, x1, y1


def _decode(data: bytes) -> tuple[int, int, float | None]:
    """(width, height, brightness spread) of a PNG / JPEG / WebP frame; spread is None if Pillow can't tell."""
    try:
        from io import BytesIO

        from PIL import Image, ImageStat

        with Image.open(BytesIO(data)) as im:
            w, h = im.size
            small = im.convert("L").resize((64, 64))
            return w, h, float(ImageStat.Stat(small).stddev[0])
    except Exception:  # noqa: BLE001 - not an image Pillow can read: fall back to the PNG header
        w, h = _png_size(data)
        return w, h, None


MIN_REAL_SIDE = 256       # a real generated frame (not a thumbnail placeholder) is at least this big
BLANK_SPREAD = 3.0        # brightness standard deviation below this = a blank / single-colour frame
ASPECT_TOLERANCE = 0.03


def _visual_dimension(thumbnail_bytes: bytes, expected_size: tuple[int, int],
                      expected_aspect: float | None = None) -> QADimensionResult:
    """A well-formed frame: the exact mock placeholder size, or a real picture of the shot's aspect ratio that is
    big enough and not blank (a failed generation often returns a black or single-colour frame)."""
    issues: list[QAIssue] = []
    spread: float | None = None
    try:
        width, height, spread = _decode(thumbnail_bytes)
        if (width, height) == expected_size and width > 0:
            valid, why = True, None
        elif expected_aspect and abs(width / max(1, height) - expected_aspect) / expected_aspect > ASPECT_TOLERANCE:
            valid, why = False, f"aspect ratio {width}x{height} doesn't match the shot ({expected_aspect:.3f})"
        elif min(width, height) < MIN_REAL_SIDE:
            valid, why = False, f"too small ({width}x{height}px)"
        elif spread is not None and spread < BLANK_SPREAD:
            valid, why = False, "blank or single-colour frame"
        else:
            valid, why = expected_aspect is not None or (width, height) == expected_size, \
                None if expected_aspect is not None else f"decoded as {width}x{height}px"
    except (ValueError, IndexError):
        width, height, valid, why = 0, 0, False, "not a readable image"

    if not valid:
        issues.append(
            QAIssue(
                issue_id=str(uuid4()),
                issue_type="malformed_frame",
                severity="error",
                description=(
                    f"Candidate frame {why or 'is malformed'}; expected "
                    + (f"aspect {expected_aspect:.3f}" if expected_aspect else f"{expected_size[0]}x{expected_size[1]}px")
                    + "."
                ),
                evidence={"decoded_size": [width, height], "expected_size": list(expected_size),
                          "expected_aspect": expected_aspect, "spread": spread},
            )
        )
    return QADimensionResult(
        dimension=QADimension.VISUAL,
        score=1.0 if valid else 0.0,
        confidence=1.0,
        diagnostics={"decoded_size": [width, height], "expected_size": list(expected_size),
                     "expected_aspect": expected_aspect, "spread": None if spread is None else round(spread, 2)},
        issues=issues,
    )


def _geometry_dimension(content: ShotContent, scene: PhysicsScene) -> QADimensionResult:
    x0, y0, x1, y1 = scene.subject_box
    box_w, box_h = max(0, x1 - x0), max(0, y1 - y0)
    frame_area = max(1, scene.width * scene.height)
    actual_ratio = (box_w * box_h) / frame_area

    expected_scale = SHOT_TYPE_SCALE.get(content.camera.shot_type.value, 0.5)
    expected_ratio = expected_scale * expected_scale

    diff = abs(actual_ratio - expected_ratio)
    score = max(0.0, 1.0 - diff / max(expected_ratio, 1e-6))
    passed = diff <= GEOMETRY_TOLERANCE

    issues: list[QAIssue] = []
    if not passed:
        issues.append(
            QAIssue(
                issue_id=str(uuid4()),
                issue_type="geometry_mismatch",
                severity="error",
                description=(
                    f"Physics scaffold's subject occupies {actual_ratio:.1%} of frame; a "
                    f"{content.camera.shot_type.value.replace('_', ' ')} shot expects ~{expected_ratio:.1%}. "
                    "The physics proxy looks stale for this shot's current framing."
                ),
                evidence={
                    "actual_ratio": actual_ratio,
                    "expected_ratio": expected_ratio,
                    "shot_type": content.camera.shot_type.value,
                    "subject_box": list(scene.subject_box),
                },
            )
        )
    return QADimensionResult(
        dimension=QADimension.GEOMETRY,
        score=round(min(1.0, score), 4),
        confidence=1.0,
        diagnostics={
            "actual_ratio": actual_ratio,
            "expected_ratio": expected_ratio,
            "shot_type": content.camera.shot_type.value,
        },
        issues=issues,
    )


def _placeholder_dimension(dimension: QADimension) -> QADimensionResult:
    return QADimensionResult(
        dimension=dimension,
        score=1.0,
        confidence=0.5,
        diagnostics={"todo": True, "reason": "no real model wired up yet (Week 4+)"},
        issues=[],
    )


def _forced_failure(real: list[QADimensionResult]) -> list[QADimensionResult]:
    """Week 3 Day 15 (integration checkpoint): override the real
    dimensions' verdict to a genuine FAIL, on purpose, so the repair
    ladder can be driven end to end through the live system instead of
    a pytest fixture. This is loud, not silent: every overridden
    dimension gets score 0.0, diagnostics.forced=True, and an explicit
    `forced_failure` issue - nothing here pretends the candidate was
    actually bad."""
    forced: list[QADimensionResult] = []
    for d in real:
        forced.append(
            QADimensionResult(
                dimension=d.dimension,
                score=0.0,
                confidence=d.confidence,
                diagnostics={**d.diagnostics, "forced": True, "original_score": d.score},
                issues=[
                    QAIssue(
                        issue_id=str(uuid4()),
                        issue_type="forced_failure",
                        severity="error",
                        description=(
                            "Deliberately forced FAIL (Day 15 integration checkpoint) - "
                            f"this dimension actually scored {d.score:.2f}."
                        ),
                        evidence={"original_score": d.score},
                    )
                ],
            )
        )
    return forced


def evaluate_shot(
    *,
    shot_id: str,
    video_asset_id: str,
    content: ShotContent,
    scene: PhysicsScene,
    thumbnail_bytes: bytes,
    thumbnail_size: tuple[int, int],
    force_fail: bool = False,
    expected_aspect: float | None = None,
) -> QAResult:
    """Score one candidate against the 6 QA dimensions and return the
    committee's verdict. FAILs on either real dimension scoring below
    REAL_PASS_THRESHOLD; placeholders never fail (they're not yet real
    judges, so they can't yet veto).

    force_fail runs the real evaluation exactly as usual, then
    deliberately overrides the real dimensions to a genuine FAIL
    (see _forced_failure) - for proving the repair ladder fires through
    the real Gateway/audit/SSE/UI path rather than by seeding qa_results
    directly. Always visible in the result (evidence.forced=True).
    """
    real = [
        _visual_dimension(thumbnail_bytes, thumbnail_size, expected_aspect),
        _geometry_dimension(content, scene),
    ]
    if force_fail:
        real = _forced_failure(real)
    dimensions = [*real, *[_placeholder_dimension(d) for d in PLACEHOLDER_DIMENSIONS]]

    failing = [d for d in real if d.score < REAL_PASS_THRESHOLD]
    status = QAStatus.FAIL if failing else QAStatus.PASS

    score = sum(d.score for d in dimensions) / len(dimensions)
    confidence = sum((d.confidence or 0.0) for d in dimensions) / len(dimensions)

    evidence: dict[str, Any] = {
        "failing_dimensions": [d.dimension.value for d in failing],
        "per_dimension": {d.dimension.value: d.diagnostics for d in dimensions},
        "forced": force_fail,
    }

    return QAResult(
        shot_id=shot_id,
        video_asset_id=video_asset_id,
        status=status,
        score=round(score, 4),
        confidence=round(confidence, 4),
        evidence=evidence,
        recommended_action=None if status == QAStatus.PASS else "repair",
        dimensions=dimensions,
    )
