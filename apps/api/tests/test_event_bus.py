"""Day 6: publishing via event_bus.publish() is received by a subscriber."""

import asyncio
import os

import pytest

from packages.contracts.event import EventType
from src.core.events.event_bus import EventBus
from src.core.events.factory import make_event
from src.core.events.outbox import commit_and_publish, discard_queued_events, queue_event
from tests.conftest import REDIS_URL, requires_db, requires_redis


@requires_redis
@pytest.mark.asyncio
async def test_published_event_reaches_project_and_global_subscribers():
    bus = EventBus(redis_url=REDIS_URL)
    project_id = f"proj-{os.getpid()}"
    received_project: list = []
    received_global: list = []

    async def listen(target: list, pid: str | None) -> None:
        async for event in bus.subscribe(project_id=pid):
            target.append(event)
            return

    tasks = [
        asyncio.create_task(listen(received_project, project_id)),
        asyncio.create_task(listen(received_global, None)),
    ]
    await asyncio.sleep(0.3)  # let SUBSCRIBE land before publishing

    sent = make_event(event_type=EventType.PROJECT_CREATED, project_id=project_id, payload={"n": 1})
    assert await bus.publish(sent) is True

    await asyncio.wait_for(asyncio.gather(*tasks), timeout=5)

    assert received_project[0].event_id == sent.event_id
    assert received_global[0].event_id == sent.event_id
    assert received_project[0].payload == {"n": 1}


@pytest.mark.asyncio
async def test_publish_is_best_effort_when_redis_is_down():
    bus = EventBus(redis_url="redis://127.0.0.1:1/0")  # nothing listens here
    ok = await bus.publish(make_event(event_type=EventType.PROJECT_CREATED, project_id="p"))
    assert ok is False  # logged, not raised


@requires_db
@pytest.mark.asyncio
async def test_outbox_publishes_only_after_commit(db_session, captured_events):
    queue_event(db_session, make_event(event_type=EventType.PROJECT_CREATED, project_id="p"))
    assert captured_events.events == []

    await commit_and_publish(db_session)
    assert captured_events.types() == ["PROJECT_CREATED"]


@requires_db
@pytest.mark.asyncio
async def test_outbox_discard_drops_events_after_rollback(db_session, captured_events):
    queue_event(db_session, make_event(event_type=EventType.PROJECT_CREATED, project_id="p"))
    discard_queued_events(db_session)
    await commit_and_publish(db_session)
    assert captured_events.events == []
