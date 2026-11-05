from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class PolicyStatus(str, Enum):
    ACTIVE = "ACTIVE"
    CANDIDATE = "CANDIDATE"
    REJECTED = "REJECTED"
    SUPERSEDED = "SUPERSEDED"


class PolicyVersion(BaseModel):
    """
    AVOS-06 §9 — Creative Policy Contract.

    Policies are versioned creative guidance used by the
    Policy Engine and Director.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    version: int = Field(
        ge=1,
        description="Monotonically increasing policy version identifier.",
    )

    rule: str = Field(
        min_length=1,
        description="Specific, scoped creative rule.",
    )

    evidence: str = Field(
        min_length=1,
        description="Quantified support for the rule.",
    )

    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Numeric confidence score for the policy.",
    )

    status: PolicyStatus = PolicyStatus.CANDIDATE
