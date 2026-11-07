"""
Week 3 Day 14 - QA committee (Engineer 2). Pure logic: fabricate a
physics scene + candidate thumbnail directly (no DB, no Blender/video
services) and check the two real dimensions score what's actually there.
"""

import struct
import zlib

import pytest

from agentic_core.pipelines.qa.committee import PhysicsScene, evaluate_shot
from packages.contracts.qa import QADimension, QAStatus
from packages.contracts.shotspec import Camera, ShotContent, ShotType

FRAME_W, FRAME_H = 64, 36


def _png(width: int, height: int) -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    row = b"\x00" + bytes((128, 128, 128)) * width
    raw = row * height
    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(raw, 9))
    png += chunk(b"IEND", b"")
    return png


def _content(shot_type: ShotType = ShotType.WIDE) -> ShotContent:
    return ShotContent(
        beat_label="beat_1", start_time=0.0, end_time=3.0, narration="x",
        camera=Camera(shot_type=shot_type),
    )


def _scene_for(shot_type: ShotType, *, correct: bool) -> PhysicsScene:
    """A subject_box sized per SHOT_TYPE_SCALE (correct) or deliberately
    for a *different* shot type (wrong - forces a geometry FAIL)."""
    from agentic_core.pipelines.qa.committee import SHOT_TYPE_SCALE

    scale = SHOT_TYPE_SCALE[shot_type.value] if correct else SHOT_TYPE_SCALE["close_up"]
    box_w, box_h = int(FRAME_W * scale), int(FRAME_H * scale)
    x0, y0 = (FRAME_W - box_w) // 2, (FRAME_H - box_h) // 2
    return PhysicsScene(width=FRAME_W, height=FRAME_H, subject_box=(x0, y0, x0 + box_w, y0 + box_h))


def _evaluate(*, shot_type: ShotType, geometry_correct: bool, thumb_size: tuple[int, int]):
    return evaluate_shot(
        shot_id="00000000-0000-0000-0000-000000000000",
        video_asset_id="00000000-0000-0000-0000-000000000001",
        content=_content(shot_type),
        scene=_scene_for(shot_type, correct=geometry_correct),
        thumbnail_bytes=_png(*thumb_size),
        thumbnail_size=(64, 36),
    )


def test_a_well_formed_correctly_framed_shot_passes():
    result = _evaluate(shot_type=ShotType.WIDE, geometry_correct=True, thumb_size=(64, 36))

    assert result.status == QAStatus.PASS
    assert result.recommended_action is None
    visual = next(d for d in result.dimensions if d.dimension == QADimension.VISUAL)
    geometry = next(d for d in result.dimensions if d.dimension == QADimension.GEOMETRY)
    assert visual.score == 1.0
    assert geometry.score >= 0.9  # integer box rounding, not an exact ratio


def test_geometry_mismatch_between_shot_type_and_rendered_scene_fails():
    """A wide shot whose physics proxy was rendered as if it were a
    close-up (stale scaffold) must fail geometry, not just score lower."""
    result = _evaluate(shot_type=ShotType.WIDE, geometry_correct=False, thumb_size=(64, 36))

    assert result.status == QAStatus.FAIL
    assert result.recommended_action == "repair"
    geometry = next(d for d in result.dimensions if d.dimension == QADimension.GEOMETRY)
    assert geometry.score < 0.6
    assert any(i.issue_type == "geometry_mismatch" for i in geometry.issues)
    assert "geometry" in result.evidence["failing_dimensions"]


def test_malformed_or_wrongly_sized_thumbnail_fails_visual():
    result = _evaluate(shot_type=ShotType.WIDE, geometry_correct=True, thumb_size=(8, 8))

    assert result.status == QAStatus.FAIL
    visual = next(d for d in result.dimensions if d.dimension == QADimension.VISUAL)
    assert visual.score == 0.0
    assert any(i.issue_type == "malformed_frame" for i in visual.issues)


def test_placeholder_dimensions_never_veto_a_pass():
    result = _evaluate(shot_type=ShotType.CLOSE_UP, geometry_correct=True, thumb_size=(64, 36))
    placeholders = {d.dimension.value for d in result.dimensions} - {"visual", "geometry"}
    assert placeholders == {"temporal", "identity", "audio", "prompt_adherence"}
    for d in result.dimensions:
        if d.dimension.value in placeholders:
            assert d.score == 1.0
            assert d.confidence == 0.5
            assert d.diagnostics["todo"] is True
    assert result.status == QAStatus.PASS


@pytest.mark.parametrize("shot_type", [ShotType.WIDE, ShotType.MEDIUM, ShotType.CLOSE_UP, ShotType.INSERT])
def test_every_shot_type_passes_when_correctly_scaffolded(shot_type):
    result = _evaluate(shot_type=shot_type, geometry_correct=True, thumb_size=(64, 36))
    assert result.status == QAStatus.PASS


def test_visual_check_judges_real_pictures():
    from io import BytesIO
    import random

    from PIL import Image

    from agentic_core.pipelines.qa.committee import _visual_dimension

    def img(w, h, solid=False, fmt="PNG"):
        im = Image.new("RGB", (w, h), (40, 90, 160))
        if not solid:
            rnd = random.Random(1)
            im.putdata([(rnd.randrange(256), rnd.randrange(256), rnd.randrange(256)) for _ in range(w * h)])
        buf = BytesIO()
        im.save(buf, fmt)
        return buf.getvalue()

    tall = 9 / 16
    assert _visual_dimension(img(288, 512), (64, 36), tall).score == 1.0                    # real 9:16 frame
    assert _visual_dimension(img(288, 512, fmt="JPEG"), (64, 36), tall).score == 1.0        # JPEG too
    blank = _visual_dimension(img(288, 512, solid=True), (64, 36), tall)
    assert blank.score == 0.0 and "blank" in blank.issues[0].description
    assert "aspect" in _visual_dimension(img(512, 288), (64, 36), tall).issues[0].description
    assert "too small" in _visual_dimension(img(90, 160), (64, 36), tall).issues[0].description
    assert _visual_dimension(img(64, 36, solid=True), (64, 36), tall).score == 1.0          # the mock placeholder
    assert _visual_dimension(b"not an image", (64, 36), tall).score == 0.0
