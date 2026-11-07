from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class JobStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class Job(BaseModel):
    """
    Canonical AVOS Job contract.

    Common language shared between:
        Temporal
        Workers
        Agents
        API
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    job_id: UUID

    project_id: UUID

    workflow_id: str = Field(
        min_length=1,
    )

    task_type: str = Field(
        min_length=1,
    )

    status: JobStatus = JobStatus.PENDING

    payload: dict[str, Any] = Field(
        default_factory=dict,
    )

    retry_count: int = Field(
        default=0,
        ge=0,
    )

    created_at: datetime

    updated_at: datetime
