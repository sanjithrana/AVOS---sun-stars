from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.contracts.shotspec import ShotContent, ShotSpec
from src.database.models.shot import Shot
from src.database.models.shot_version import ShotVersion


class ShotRepository:
    """Shots (stable identity) + shot_versions (immutable ShotSpecs)."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # -- reads -------------------------------------------------------------

    async def get(self, shot_id: str) -> Shot | None:
        return await self.session.get(Shot, str(shot_id))

    async def get_by_index(self, project_id: str, shot_index: int) -> Shot | None:
        result = await self.session.execute(
            select(Shot).where(Shot.project_id == project_id, Shot.shot_index == shot_index)
        )
        return result.scalar_one_or_none()

    async def list_by_project(self, project_id: str) -> list[Shot]:
        result = await self.session.execute(
            select(Shot).where(Shot.project_id == project_id).order_by(Shot.shot_index)
        )
        return list(result.scalars().all())

    async def next_index(self, project_id: str) -> int:
        result = await self.session.execute(
            select(func.max(Shot.shot_index)).where(Shot.project_id == project_id)
        )
        current = result.scalar_one_or_none()
        return 0 if current is None else current + 1

    async def get_version(self, shot_id: str, version: int) -> ShotVersion | None:
        result = await self.session.execute(
            select(ShotVersion).where(ShotVersion.shot_id == str(shot_id), ShotVersion.version == version)
        )
        return result.scalar_one_or_none()

    async def current_version(self, shot: Shot) -> ShotVersion | None:
        return await self.get_version(shot.id, shot.current_version)

    async def list_versions(self, shot_id: str) -> list[ShotVersion]:
        result = await self.session.execute(
            select(ShotVersion).where(ShotVersion.shot_id == str(shot_id)).order_by(ShotVersion.version)
        )
        return list(result.scalars().all())

    # -- writes ------------------------------------------------------------

    def _version_row(self, spec: ShotSpec, content: ShotContent) -> ShotVersion:
        return ShotVersion(
            id=str(spec.shotspec_id),
            shot_id=str(spec.shot_id),
            version=spec.version,
            parent_version=spec.parent_version,
            status=spec.status.value,
            content=content.model_dump(mode="json"),
            content_hash=spec.content_hash,
            created_by=str(spec.created_by),
            created_at=spec.created_at,
        )

    async def create_shot(
        self,
        *,
        project_id: str,
        shot_index: int,
        spec: ShotSpec,
        content: ShotContent,
    ) -> tuple[Shot, ShotVersion]:
        shot = Shot(
            id=str(spec.shot_id),
            project_id=project_id,
            shot_index=shot_index,
            current_version=spec.version,
            status=spec.status.value,
            beat_label=content.beat_label,
            start_time=content.start_time,
            end_time=content.end_time,
        )
        self.session.add(shot)
        await self.session.flush()

        version = self._version_row(spec, content)
        self.session.add(version)
        await self.session.flush()
        return shot, version

    async def add_version(self, shot: Shot, spec: ShotSpec, content: ShotContent) -> ShotVersion:
        version = self._version_row(spec, content)
        self.session.add(version)

        shot.current_version = spec.version
        shot.status = spec.status.value
        shot.beat_label = content.beat_label
        shot.start_time = content.start_time
        shot.end_time = content.end_time

        await self.session.flush()
        return version

    async def set_version_status(
        self,
        shot: Shot,
        version: ShotVersion,
        status: str,
        continuity: dict | None = None,
    ) -> None:
        version.status = status
        if continuity is not None:
            version.continuity = continuity
        if version.version == shot.current_version:
            shot.status = status
        await self.session.flush()
