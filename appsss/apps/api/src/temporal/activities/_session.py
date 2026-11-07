from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.events.outbox import discard_queued_events
from src.database.async_session import AsyncSessionLocal


@asynccontextmanager
async def activity_session() -> AsyncIterator[AsyncSession]:
    """One DB session per activity attempt; rolls back (and drops any
    queued events) if the attempt fails, so a retry starts clean."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except BaseException:
            discard_queued_events(session)
            await session.rollback()
            raise
