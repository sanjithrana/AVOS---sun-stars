"""Request/response shapes for the QA + repair API (Week 3 Day 14).

Kept separate from the locked packages/contracts/qa.py and repair.py
(whose shapes are fixed by existing tests) - these describe what the
routes hand back to the frontend, not the AVOS-06 QA/repair contracts
themselves.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from packages.contracts.common import UUIDStr


class QADimensionScoreResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dimension: str
    score: float
    confidence: float | None = None
    diagnostics: dict = Field(default_factory=dict)
    issues: list[dict] = Field(default_factory=list)


class QAResultResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUIDStr
    shot_id: str
    status: str  # PASS | FAIL
    score: float
    confidence: float | None = None
    evidence: dict = Field(default_factory=dict)
    dimensions: list[QADimensionScoreResponse] = Field(default_factory=list)
    evaluated_at: datetime


class RepairPlanResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUIDStr
    shot_id: str
    attempt: int
    rung: str  # MICRO | MACRO | HUMAN_REQUIRED
    failure_type: str
    target_stage: str
    changes: dict = Field(default_factory=dict)
    preserve: list[str] = Field(default_factory=list)
    applied_at: datetime | None = None
    resulting_asset_id: UUIDStr | None = None


class ShotQAStateResponse(BaseModel):
    """GET /shots/{id}/qa: the QA/repair history a QADashboard row needs
    in one call - latest verdict plus every repair attempt so far."""

    model_config = ConfigDict(extra="forbid")

    shot_id: str
    latest_result: QAResultResponse | None = None
    repairs: list[RepairPlanResponse] = Field(default_factory=list)
