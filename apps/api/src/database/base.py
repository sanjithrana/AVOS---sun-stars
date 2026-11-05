from datetime import datetime, timezone

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


def utcnow() -> datetime:
    """Timezone-aware 'now' for column defaults.

    datetime.utcnow() returns a *naive* datetime; written into a
    TIMESTAMPTZ column it is interpreted in the DB session's timezone
    and serialized without an offset, so API timestamps were
    inconsistent (some with 'Z', some without).
    """
    return datetime.now(timezone.utc)
