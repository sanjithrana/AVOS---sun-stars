from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from packages.contracts.event import Event, EventType

DEFAULT_ORGANIZATION_ID = "default"


def make_event(
    *,
    event_type: EventType,
    project_id: str | None = None,
    correlation_id: str | None = None,
    causation_id: str | None = None,
    payload: dict[str, Any] | None = None,
    organization_id: str = DEFAULT_ORGANIZATION_ID,
) -> Event:
    return Event(
        event_id=str(uuid4()),
        event_type=event_type,
        timestamp=datetime.now(timezone.utc),
        organization_id=organization_id,
        project_id=project_id,
        correlation_id=correlation_id or str(uuid4()),
        causation_id=causation_id,
        payload=payload or {},
    )
