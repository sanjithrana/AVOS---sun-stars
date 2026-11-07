from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.contracts.world_state import WorldState
from src.database.models.shot import Shot
from src.database.models.world_state import WorldStateRecord


class WorldStateRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_current(self, project_id: str) -> WorldStateRecord | None:
        result = await self.session.execute(
            select(WorldStateRecord)
            .where(WorldStateRecord.project_id == project_id)
            .order_by(WorldStateRecord.version.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_before_shot(self, project_id: str, shot_index: int) -> WorldStateRecord | None:
        """Latest world state produced by the initial world (no source
        shot) or by a shot *earlier* in the sequence - i.e. the world as
        it stands when `shot_index` begins. Validating a shot against the
        project's newest state would wrongly include later shots."""
        result = await self.session.execute(
            select(WorldStateRecord)
            .outerjoin(Shot, Shot.id == WorldStateRecord.source_shot_id)
            .where(
                WorldStateRecord.project_id == project_id,
                (WorldStateRecord.source_shot_id.is_(None)) | (Shot.shot_index < shot_index),
            )
            .order_by(WorldStateRecord.version.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def latest_for_shot(self, shot_id: str) -> WorldStateRecord | None:
        result = await self.session.execute(
            select(WorldStateRecord)
            .where(WorldStateRecord.source_shot_id == shot_id)
            .order_by(WorldStateRecord.version.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def append(
        self,
        state: WorldState,
        *,
        source_shot_id: str | None = None,
    ) -> WorldStateRecord:
        current = await self.get_current(state.project_id)
        version = 0 if current is None else current.version + 1
        stored = state.model_copy(update={"version": version})

        record = WorldStateRecord(
            id=str(uuid4()),
            project_id=state.project_id,
            version=version,
            state=stored.model_dump(mode="json"),
            source_shot_id=source_shot_id,
        )
        self.session.add(record)
        await self.session.flush()
        return record
