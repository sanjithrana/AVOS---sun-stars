"""
Week 3 Day 14 - repair classification + the 3-attempt ladder (Engineer 2).
Pure logic: attempt number -> rung is deterministic and bounded, and a
RepairPlan's shape matches what services/repair_service.py needs to
actually apply the fix (or, at HUMAN_REQUIRED, deliberately apply none).
"""

import pytest

from agentic_core.agents.repair.classifier import (
    build_repair_plan,
    classify_failure,
    rung_for_attempt,
)
from packages.contracts.qa import QADimension, QADimensionResult, QAResult, QAStatus


def _fail_result(worst: QADimension = QADimension.GEOMETRY, score: float = 0.1) -> QAResult:
    return QAResult(
        shot_id="00000000-0000-0000-0000-000000000000",
        video_asset_id="00000000-0000-0000-0000-000000000001",
        status=QAStatus.FAIL,
        score=0.4,
        confidence=0.9,
        evidence={},
        recommended_action="repair",
        dimensions=[
            QADimensionResult(dimension=worst, score=score, confidence=1.0),
            QADimensionResult(dimension=QADimension.VISUAL, score=1.0, confidence=1.0),
        ],
    )


@pytest.mark.parametrize(
    "attempt,expected", [(1, "MICRO"), (2, "MACRO"), (3, "HUMAN_REQUIRED"), (4, "HUMAN_REQUIRED"), (99, "HUMAN_REQUIRED")]
)
def test_rung_escalates_and_then_stays_at_human_required(attempt, expected):
    assert rung_for_attempt(attempt) == expected


def test_attempt_below_one_is_rejected():
    with pytest.raises(ValueError):
        rung_for_attempt(0)


def test_classify_failure_requires_a_failing_result():
    passing = _fail_result().model_copy(update={"status": QAStatus.PASS})
    with pytest.raises(ValueError):
        classify_failure(passing)


def test_classify_failure_names_the_worst_dimension():
    failure, target = classify_failure(_fail_result(worst=QADimension.GEOMETRY))
    assert failure == "geometry_mismatch"
    assert target == "video_generation"

    failure2, _ = classify_failure(_fail_result(worst=QADimension.VISUAL))
    assert failure2 == "visual_defect"


def test_micro_plan_is_a_small_scoped_change_that_preserves_upstream_work():
    plan = build_repair_plan(_fail_result(), attempt=1)

    assert plan["rung"] == "MICRO"
    assert plan["changes"]["action"] == "regenerate_candidates"
    assert "prompt_suffix" not in plan["changes"]
    assert "shot_spec" in plan["preserve"] and "physics_proxy" in plan["preserve"]


def test_macro_plan_is_a_bigger_change_than_micro_but_still_preserves_upstream_work():
    plan = build_repair_plan(_fail_result(), attempt=2)

    assert plan["rung"] == "MACRO"
    assert "prompt_suffix" in plan["changes"]
    assert plan["changes"]["seed_offset"] != build_repair_plan(_fail_result(), attempt=1)["changes"]["seed_offset"]
    assert "shot_spec" in plan["preserve"]


def test_human_required_plan_applies_no_automatic_changes():
    plan = build_repair_plan(_fail_result(), attempt=3)

    assert plan["rung"] == "HUMAN_REQUIRED"
    assert plan["changes"] == {}
    assert set(plan["preserve"]) == {"shot_spec", "physics_proxy", "video_generation"}


def test_a_fourth_attempt_is_still_human_required_not_a_new_rung():
    plan = build_repair_plan(_fail_result(), attempt=4)
    assert plan["rung"] == "HUMAN_REQUIRED"
