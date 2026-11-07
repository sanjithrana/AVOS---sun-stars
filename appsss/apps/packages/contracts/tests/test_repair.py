import pytest
from pydantic import ValidationError

from packages.contracts.repair import (
    RepairExecution,
    RepairPlan,
    RepairResult,
)


def valid_repair_plan() -> RepairPlan:
    return RepairPlan(
        failure="geometry_drift",
        target="video_generation",
        changes={
            "controlnet_depth_weight": 0.95,
            "seed": 84729,
        },
        preserve=[
            "script",
            "audio",
            "shot_spec",
            "blender_scene",
        ],
    )


def test_valid_repair_plan_is_accepted():
    plan = valid_repair_plan()

    assert plan.failure == "geometry_drift"
    assert "shot_spec" in plan.preserve


def test_empty_preserve_list_is_rejected():
    with pytest.raises(ValidationError):
        RepairPlan(
            failure="geometry_drift",
            target="video_generation",
            changes={},
            preserve=[],
        )


def test_missing_failure_is_rejected():
    with pytest.raises(ValidationError):
        RepairPlan(
            target="video_generation",
            changes={},
            preserve=["shot_spec"],
        )
