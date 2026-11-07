from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class GenerateRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    generation_type: str = Field(
        min_length=1,
    )


class GenerateResponse(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    job_id: str
    project_id: str
    status: str
    workflow_id: str


class JobResponse(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    id: str
    project_id: str
    job_type: str
    status: str
    workflow_id: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    output: dict | None = None
    error_message: str | None = None
