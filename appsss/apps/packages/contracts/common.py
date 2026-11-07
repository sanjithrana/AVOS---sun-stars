from typing import Annotated
from uuid import UUID

from pydantic import BeforeValidator


def _coerce_to_str(value: object) -> object:
    """UUID -> str; anything else passes through so normal str
    validation still rejects genuinely wrong types."""
    if isinstance(value, UUID):
        return str(value)
    return value


# Use for any response field read from a SQLAlchemy
# PGUUID(as_uuid=True) column but exposed to clients as a string id.
#
# A plain `id: str` does NOT accept a uuid.UUID instance: Pydantic v2
# raises `string_type` on model_validate(orm_row), because
# from_attributes controls attribute access, not type coercion. That
# bug made every gate endpoint (POST /plan, GET /gates/...) return 500.
UUIDStr = Annotated[str, BeforeValidator(_coerce_to_str)]
