import warnings
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

# `schema` is the agreed contract field name (AVOS-05 s3.2); Pydantic
# warns that it shadows the deprecated BaseModel.schema() classmethod.
# Harmless here - silence it so API/worker logs stay clean.
warnings.filterwarnings(
    "ignore",
    message='Field name "schema" in "ToolSchema" shadows an attribute',
    category=UserWarning,
)


class ToolSchema(BaseModel):
    """
    Day-3 Tool Gateway metadata contract.

    Every registered tool declares:
    - name
    - description
    - schema
    - permission
    - timeout
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    name: str = Field(
        min_length=1,
        description="Unique tool name exposed to the Agentic Core.",
    )

    description: str = Field(
        min_length=1,
        description="Human-readable description of the tool capability.",
    )

    schema: dict[str, Any] = Field(
        default_factory=dict,
        description="Structured declaration of accepted tool inputs.",
    )

    permission: str = Field(
        min_length=1,
        description="Permission required to invoke the tool.",
    )

    timeout: int = Field(
        gt=0,
        description="Maximum allowed execution time in seconds.",
    )
