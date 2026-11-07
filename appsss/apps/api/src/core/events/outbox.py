"""
Commit-then-publish helper.

Services used to publish events *before* committing the database
transaction that produced them. A browser receiving the event would
immediately re-fetch (e.g. GET /agents/trace) and not see the new rows
yet - or see an event for work that was then rolled back.

Usage in any service/activity that writes + emits:

    queue_event(session, make_event(...))
    ...
    await commit_and_publish(session)

Events are only published after the commit succeeds, in the order they
were queued.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from packages.contracts.event import Event
from src.core.events.event_bus import get_event_bus

_KEY = "avos_pending_events"


def queue_event(session: AsyncSession, event: Event) -> None:
    session.info.setdefault(_KEY, []).append(event)


async def commit_and_publish(session: AsyncSession) -> None:
    await session.commit()
    events: list[Event] = session.info.pop(_KEY, [])

    bus = get_event_bus()
    for event in events:
        await bus.publish(event)


def discard_queued_events(session: AsyncSession) -> None:
    """Call after a rollback so stale events are never published."""
    session.info.pop(_KEY, None)
