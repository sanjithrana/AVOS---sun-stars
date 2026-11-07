"""
Event Bus (Day 6).

ADR: Redis pub/sub vs Postgres LISTEN/NOTIFY
----------------------------------------------
Chose Redis pub/sub because:
  1. Redis is already a required service in docker-compose.yml (was
     otherwise unused so far) - no new infrastructure.
  2. Postgres LISTEN/NOTIFY payloads are capped at 8000 bytes and don't
     survive connection pooling the way async SQLAlchemy pools work;
     Redis pub/sub has no such payload ceiling for our event sizes.
  3. We don't need NOTIFY's transactional-commit-coupling here - events
     are fire-and-forget fan-out to live UI subscribers, not a durable
     queue (Temporal already owns durable workflow state).

Trade-off accepted: Redis pub/sub does not persist/replay missed
messages to a client that (re)connects late. That's fine for this use
case (live SSE feed to an open browser tab); it is NOT used as a
system of record. Anything that must be durable is written to Postgres
directly (audit_records, human_gates, jobs) and read via normal REST.
"""

import logging
from collections.abc import AsyncGenerator

import redis.asyncio as redis

from packages.contracts.event import Event
from src.config.settings import settings

CHANNEL_PREFIX = "avos:events"

logger = logging.getLogger(__name__)


class EventBus:
    def __init__(self, redis_url: str | None = None) -> None:
        self._redis_url = redis_url or settings.redis_url
        self._client: redis.Redis | None = None

    def _get_client(self) -> redis.Redis:
        if self._client is None:
            self._client = redis.from_url(self._redis_url)
        return self._client

    @staticmethod
    def _channel(project_id: str | None) -> str:
        # A per-project channel lets SSE subscribers filter server-side
        # (only pay for events they asked for) while a global channel
        # (project_id=None) covers project-agnostic events.
        return f"{CHANNEL_PREFIX}:{project_id}" if project_id else CHANNEL_PREFIX

    async def publish(self, event: Event) -> bool:
        """
        Publish an event. Best-effort by design (see ADR above): the
        event bus is a live-UI fan-out channel, not a system of record,
        so a Redis outage must never fail the database write that
        produced the event. Returns False (and logs) on failure.
        """
        payload = event.model_dump_json()

        try:
            client = self._get_client()
            await client.publish(self._channel(event.project_id), payload)
            # Always also publish to the global channel so a client
            # listening across all projects (e.g. an admin view) sees
            # everything without subscribing per-project.
            if event.project_id:
                await client.publish(CHANNEL_PREFIX, payload)
        except Exception:  # noqa: BLE001 - logged, intentionally non-fatal
            logger.exception(
                "Event bus publish failed for %s (project=%s)",
                event.event_type.value,
                event.project_id,
            )
            return False

        return True

    async def subscribe(
        self,
        project_id: str | None = None,
    ) -> AsyncGenerator[Event, None]:
        client = self._get_client()
        pubsub = client.pubsub()

        try:
            await pubsub.subscribe(self._channel(project_id))

            async for message in pubsub.listen():
                if message["type"] != "message":
                    continue

                raw = message["data"]
                if isinstance(raw, bytes):
                    raw = raw.decode("utf-8")

                try:
                    event = Event.model_validate_json(raw)
                except ValueError:
                    # One malformed message must not kill a client's
                    # whole stream.
                    logger.warning("Dropping malformed event: %.200s", raw)
                    continue

                yield event
        finally:
            await pubsub.unsubscribe(self._channel(project_id))
            await pubsub.aclose()


_event_bus: EventBus | None = None


def get_event_bus() -> EventBus:
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus
