from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class QAStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"


class QADimension(str, Enum):
    VISUAL = "visual"
    TEMPORAL = "temporal"
    GEOMETRY = "geometry"
    IDENTITY = "identity"
    AUDIO = "audio"
    PROMPT_ADHERENCE = "prompt_adherence"


class QARequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    shot_id: UUID
    video_asset_id: UUID


class QAIssue(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    issue_id: str = Field(min_length=1)
    issue_type: str = Field(min_length=1)
    severity: str = Field(min_length=1)
    shot_id: str | None = None
    description: str = Field(min_length=1)
    evidence: dict[str, Any] = Field(default_factory=dict)


class QADimensionResult(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    dimension: QADimension
    score: float
    confidence: float | None = None
    diagnostics: dict[str, Any] = Field(default_factory=dict)
    issues: list[QAIssue] = Field(default_factory=list)


class QAResult(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    shot_id: UUID
    video_asset_id: UUID
    status: QAStatus
    score: float
    confidence: float | None = None
    evidence: dict[str, Any] = Field(default_factory=dict)
    recommended_action: str | None = None
    dimensions: list[QADimensionResult] = Field(default_factory=list)
