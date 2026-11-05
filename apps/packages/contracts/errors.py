from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class ErrorCode(str, Enum):
    VALIDATION_ERROR = "VALIDATION_ERROR"
    AUTHENTICATION_ERROR = "AUTHENTICATION_ERROR"
    AUTHORIZATION_ERROR = "AUTHORIZATION_ERROR"

    PROJECT_NOT_FOUND = "PROJECT_NOT_FOUND"
    SHOT_NOT_FOUND = "SHOT_NOT_FOUND"
    JOB_NOT_FOUND = "JOB_NOT_FOUND"
    ASSET_NOT_FOUND = "ASSET_NOT_FOUND"
    APPROVAL_NOT_FOUND = "APPROVAL_NOT_FOUND"

    WORKER_ERROR = "WORKER_ERROR"
    TIMEOUT_ERROR = "TIMEOUT_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class ErrorDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: str | None = None
    message: str


class ErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    error: ErrorCode
    message: str
    details: list[ErrorDetail] = Field(default_factory=list)
    request_id: str