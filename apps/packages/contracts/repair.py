from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class RepairPlan(BaseModel):
    """
    AVOS-06 §7 — Surgical Repair Contract.

    Produced by:
        classify_failure + surgical_repair

    Consumed by:
        retry_generation, QA
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    failure: str = Field(
        min_length=1,
        description="Classified failure type produced by classify_failure.",
    )

    target: str = Field(
        min_length=1,
        description="Pipeline stage to which the repair applies.",
    )

    changes: dict[str, Any] = Field(
        default_factory=dict,
        description="Specific, minimal parameter deltas for the repair.",
    )

    preserve: list[str] = Field(
        min_length=1,
        description=(
            "Upstream artifacts that must not be regenerated. "
            "Required for surgical repair."
        ),
    )


class RepairExecution(BaseModel):
    """
    Execution-side result for applying a RepairPlan.

    This represents the handoff between the decision-side
    RepairPlan and the actual repair execution.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    repair_plan: RepairPlan
    status: str = Field(min_length=1)
    resulting_asset_id: str | None = None
    error: str | None = None


class RepairResult(BaseModel):
    """
    Result of a completed repair operation.

    A successful repair must re-enter QA according to AVOS-06 §7.4.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    status: str = Field(min_length=1)
    resulting_asset_id: str | None = None
    qa_required: bool = True
    error: str | None = None
