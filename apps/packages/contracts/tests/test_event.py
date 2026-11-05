from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from packages.contracts.event import Event, EventType


def valid_event() -> Event:
    return Event(
        event_id="event-001",
        event_type=EventType.PROJECT_CREATED,
        timestamp=datetime.now(timezone.utc),
        organization_id="org-001",
        correlation_id="corr-001",
        payload={},
    )


def test_valid_event_is_accepted():
    event = valid_event()

    assert event.event_type == EventType.PROJECT_CREATED
    assert event.organization_id == "org-001"


def test_invalid_event_type_is_rejected():
    with pytest.raises(ValidationError):
        Event(
            event_id="event-001",
            event_type="NOT_A_REAL_EVENT",
            timestamp=datetime.now(timezone.utc),
            organization_id="org-001",
            correlation_id="corr-001",
        )


def test_missing_correlation_id_is_rejected():
    with pytest.raises(ValidationError):
        Event(
            event_id="event-001",
            event_type=EventType.PROJECT_CREATED,
            timestamp=datetime.now(timezone.utc),
            organization_id="org-001",
        )
