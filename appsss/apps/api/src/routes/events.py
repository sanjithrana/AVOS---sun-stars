import asyncio
import json

from fastapi import APIRouter, Query, Request
from sse_starlette.sse import EventSourceResponse

from src.core.events.event_bus import get_event_bus

router = APIRouter(
    prefix="/api/v1/events",
    tags=["events"],
)


@router.get("/stream")
async def stream_events(
    request: Request,
    project_id: str | None = Query(default=None),
):
    """
    Server-Sent Events stream of live AVOS events.

    Optionally scoped to a single project via ?project_id=. The
    frontend's lib/events.ts + hooks/useRealtime.ts consume this
    directly with the browser's native EventSource, so no client-side
    polling is needed once a subscription is open.
    """
    bus = get_event_bus()

    async def event_generator():
        # Initial comment so proxies/browsers flush the connection open
        # immediately instead of buffering until the first real event.
        yield {"event": "ping", "data": "connected"}

        async for event in bus.subscribe(project_id=project_id):
            if await request.is_disconnected():
                break

            yield {
                "event": event.event_type.value,
                "data": json.dumps(json.loads(event.model_dump_json())),
            }

    return EventSourceResponse(event_generator())
