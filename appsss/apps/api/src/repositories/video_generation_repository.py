from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models.video_generation import VideoGeneration


class VideoGenerationRepository:
    """Idempotency-keyed video-generation attempts (Week 3 Day 13)."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_idempotency_key(self, idempotency_key: str) -> VideoGeneration | None:
        result = await self.session.execute(
            select(VideoGeneration).where(VideoGeneration.idempotency_key == idempotency_key)
        )
        return result.scalar_one_or_none()

    async def get_latest_for_shot(self, shot_id: str, version: int) -> VideoGeneration | None:
        result = await self.session.execute(
            select(VideoGeneration)
            .where(VideoGeneration.shot_id == str(shot_id), VideoGeneration.version == version)
            .order_by(VideoGeneration.created_at.desc())
        )
        return result.scalars().first()

    async def create(
        self,
        *,
        shot_id: str,
        version: int,
        idempotency_key: str,
        compiled_prompt: dict[str, Any],
        candidates: list[dict[str, Any]],
        asset_id: UUID,
        created_by: str,
        status: str = "COMPLETED",
    ) -> VideoGeneration:
        record = VideoGeneration(
            id=str(uuid4()),
            shot_id=str(shot_id),
            version=version,
            idempotency_key=idempotency_key,
            status=status,
            compiled_prompt=compiled_prompt,
            candidates=candidates,
            asset_id=asset_id,
            created_by=created_by,
            created_at=datetime.now(timezone.utc),
        )
        self.session.add(record)
        await self.session.flush()
        await self.session.refresh(record)
        return record
