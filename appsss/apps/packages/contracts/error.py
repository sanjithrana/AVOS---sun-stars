from pydantic import BaseModel, ConfigDict, Field


class APIError(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    project_id: str | None = None


class APIErrorResponse(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    error: APIError
