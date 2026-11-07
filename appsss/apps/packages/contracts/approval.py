from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class ApprovalType(str, Enum):
    CREATIVE = "creative"
    QUALITY = "quality"
    REGULATORY = "regulatory"
    FINAL = "final"


class ApprovalDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: ApprovalStatus
    comment: str | None = None
    decided_by: str | None = None
    decided_at: datetime | None = None


class Approval(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    version: int = Field(default=1, ge=1)

    project_id: str
    shot_id: str | None = None
    job_id: str | None = None

    approval_type: ApprovalType
    status: ApprovalStatus = ApprovalStatus.PENDING

    requested_by: str
    approver_id: str | None = None

    decision: ApprovalDecision | None = None

    metadata: dict[str, object] = Field(default_factory=dict)

    created_at: datetime
    updated_at: datetime