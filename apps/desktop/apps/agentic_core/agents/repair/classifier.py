"""
Repair classification + the 3-attempt ladder (Week 3 Day 14, Engineer 2 -
AVOS-03 v1.1 s14, AVOS-06 s7 "Surgical Repair Contract").

Pure logic, no I/O: given a failing QAResult and which attempt number
this is *for this shot* (the durable counter lives in Postgres -
services/repair_service.py derives it by counting existing repair_plans
rows, so restarting the worker mid-sequence can't lose or duplicate it -
see AVOS-03 v1.1 s14.6), decide:

  1. classify_failure(): which QA dimension is most responsible, and
     what pipeline stage a fix targets;
  2. rung_for_attempt(): which rung of the ladder this attempt sits on
     - MICRO (1st), MACRO (2nd), HUMAN_REQUIRED (3rd and every attempt
       after, since there is no 4th automatic rung); and
  3. build_repair_plan(): the RepairPlan for that rung - a real,
     minimal, scoped set of changes for MICRO/MACRO (a nudged seed, or a
     larger prompt correction), and no changes at all for HUMAN_REQUIRED
     (nothing is auto-applied once a human is required).

Escalation is monotonic and attempt-driven, not "did the last repair
work" driven: three consecutive failures always reach HUMAN_REQUIRED on
attempt 3, never later and never earlier, which is exactly the "bounded,
not an infinite or LLM-forgotten loop" guarantee AVOS-03 v1.1 s14.6 asks
for and api/tests/test_repair_ladder.py proves directly.
"""

from typing import Literal

from packages.contracts.qa import QAResult, QAStatus

Rung = Literal["MICRO", "MACRO", "HUMAN_REQUIRED"]

RUNG_FOR_ATTEMPT: dict[int, Rung] = {1: "MICRO", 2: "MACRO"}


def rung_for_attempt(attempt: int) -> Rung:
    """1 -> MICRO, 2 -> MACRO, 3 and anything after -> HUMAN_REQUIRED.
    There is no rung past HUMAN_REQUIRED to escalate to - once reached,
    every further attempt for this shot stays HUMAN_REQUIRED."""
    if attempt < 1:
        raise ValueError("attempt must be >= 1")
    return RUNG_FOR_ATTEMPT.get(attempt, "HUMAN_REQUIRED")


def classify_failure(qa_result: QAResult) -> tuple[str, str]:
    """(failure, target) - the worst-scoring failing dimension names the
    failure type; the repair target is always the generation stage in
    this mock pipeline (a real geometry fix would mean a new Blender
    pass, which needs a ShotSpec edit - a creative/human decision this
    automatic ladder does not make on its own)."""
    if qa_result.status != QAStatus.FAIL:
        raise ValueError("classify_failure requires a FAILing QAResult")

    failing = [d for d in qa_result.dimensions if d.score < 0.6]
    worst = min(failing, key=lambda d: d.score) if failing else min(
        qa_result.dimensions, key=lambda d: d.score
    )
    failure = f"{worst.dimension.value}_defect" if worst.dimension.value != "geometry" else "geometry_mismatch"
    return failure, "video_generation"


def build_repair_plan(
    qa_result: QAResult,
    *,
    attempt: int,
    max_attempts: int | None = None,
) -> dict:
    """A plain dict (not the locked RepairPlan contract, which fixes its
    own field set) carrying everything services/repair_service.py needs
    to both persist a repair_plans row and actually apply the fix:
    failure/target/changes/preserve plus the attempt/rung this call
    resolved to."""
    rung = rung_for_attempt(attempt)
    # Generation limits (Model Fabric): max_attempts counts generations including the first, so repair attempt N
    # is generation N + 1. Past the limit a person decides, whatever the ladder would have tried next.
    if max_attempts is not None and attempt + 1 > max_attempts:
        rung = "HUMAN_REQUIRED"
    failure, target = classify_failure(qa_result)

    if rung == "MICRO":
        changes = {
            "action": "regenerate_candidates",
            "seed_offset": attempt * 1000,
            "note": "Nudge the generation seed; same prompt, same physics proxy.",
        }
        preserve = ["shot_spec", "physics_proxy"]
    elif rung == "MACRO":
        changes = {
            "action": "regenerate_candidates",
            "seed_offset": attempt * 1000,
            "prompt_suffix": (
                "Correct the framing so the subject's on-screen size matches the "
                "requested shot type exactly."
            ),
            "note": "Nudge the seed and add a corrective prompt instruction.",
        }
        preserve = ["shot_spec", "physics_proxy"]
    else:  # HUMAN_REQUIRED
        changes = {}
        preserve = ["shot_spec", "physics_proxy", "video_generation"]

    return {
        "failure": failure,
        "target": target,
        "changes": changes,
        "preserve": preserve,
        "attempt": attempt,
        "rung": rung,
    }
