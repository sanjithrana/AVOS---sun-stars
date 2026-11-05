from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ExperienceRecord(BaseModel):
    """
    AVOS-06 §10 — Experience Record.

    Captures the outcome of a published video for later analysis.

    AVOS-06 defines the role and lifecycle of the Experience Record,
    but does not define a complete field-by-field schema. Therefore,
    the record payload remains structured but extensible until the
    detailed Experience schema is formally specified.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    data: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Structured experience data captured after publication. "
            "The detailed field schema is not defined by AVOS-06 §10."
        ),
    )
