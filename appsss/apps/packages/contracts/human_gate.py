from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from packages.contracts.common import UUIDStr


class HumanGateType(str, Enum):
    SCRIPT_APPROVAL = "script_approval"
    SHOT_APPROVAL = "shot_approval"
    FINAL_APPROVAL = "final_approval"


class HumanGateStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class HumanGateDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    comment: str | None = None
    decided_by: str = Field(default="anonymous", min_length=1)


class HumanGateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: UUIDStr
    project_id: str
    gate_type: HumanGateType
    status: HumanGateStatus
    payload: dict
    comment: str | None
    decided_by: str | None
    created_at: datetime
    decided_at: datetime | None
