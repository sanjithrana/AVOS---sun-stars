"""
ShotSpec persistence + continuity (Week 3 Day 11, Engineer 1).

One service backs both the REST API (humans, Storyboard/ShotEditor) and
the Gateway tools create_shot_spec / validate_shot_spec /
get_world_state (agents). Pure logic stays in agentic_core:
builder.make_spec/next_version and continuity.validate/apply.
"""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from agentic_core.styles import get_style
from agentic_core.shotspec.builder import (
    SHOTSPEC_BUILDER_AGENT_ID,
    initial_world_state,
    make_spec,
    next_version,
    shot_id_for,
)
from agentic_core.world_state.continuity import apply_shot, validate_continuity
from packages.contracts.event import EventType
from packages.contracts.shot_api import (
    ShotAssetResponse,
    ShotDetailResponse,
    ShotResponse,
    ShotVersionResponse,
    VideoGenerationResponse,
)
from packages.contracts.shotspec import (
    ContinuityReport,
    ShotContent,
    ShotSpec,
    ShotSpecStatus,
)
from packages.contracts.world_state import WorldState, WorldStateResponse
from src.core.events.factory import make_event
from src.core.events.outbox import queue_event
from src.database.models.shot import Shot
from src.database.models.shot_version import ShotVersion
from src.errors import APIException
from src.repositories.project_repository import ProjectRepository
from src.repositories.shot_repository import ShotRepository
from src.repositories.video_generation_repository import VideoGenerationRepository
from src.repositories.world_state_repository import WorldStateRepository


def _not_found(what: str) -> APIException:
    return APIException(code="not_found", message=f"{what} not found.", status_code=404)


def video_generation_response(record) -> VideoGenerationResponse:
    return VideoGenerationResponse(
        video_generation_id=record.id,
        idempotency_key=record.idempotency_key,
        status=record.status,
        candidates=record.candidates,
    )


def version_response(row: ShotVersion, generation=None) -> ShotVersionResponse:
    return ShotVersionResponse(
        shotspec_id=row.id,
        version=row.version,
        parent_version=row.parent_version,
        status=row.status,
        content=ShotContent.model_validate(row.content),
        content_hash=row.content_hash,
        created_by=row.created_by,
        created_at=row.created_at,
        continuity=ContinuityReport.model_validate(row.continuity) if row.continuity else None,
        physics_proxy_asset_id=row.physics_proxy_asset_id,
        video_generation_asset_id=row.video_generation_asset_id,
        video_generation=video_generation_response(generation) if generation else None,
    )


def shot_response(shot: Shot, current: ShotVersion, generation=None) -> ShotResponse:
    return ShotResponse(
        id=shot.id,
        project_id=shot.project_id,
        shot_index=shot.shot_index,
        status=shot.status,
        current_version=shot.current_version,
        beat_label=shot.beat_label,
        start_time=shot.start_time,
        end_time=shot.end_time,
        created_at=shot.created_at,
        updated_at=shot.updated_at,
        spec=version_response(current, generation),
    )


class ShotSpecService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.shots = ShotRepository(session)
        self.worlds = WorldStateRepository(session)
        self.projects = ProjectRepository(session)
        self.generations = VideoGenerationRepository(session)

    async def _require_project(self, project_id: str) -> None:
        if await self.projects.get(project_id) is None:
            raise APIException(
                code="not_found", message="Project not found.", project_id=project_id, status_code=404
            )

    # -- WorldState ----------------------------------------------------------

    async def _initial_world(self, project_id: str):
        """Version-0 world in the project's style preset's look."""
        project = await self.projects.get(project_id)
        return initial_world_state(
            project_id, style=get_style(project.style_preset if project else None).visual_style
        )

    async def get_world_state(self, project_id: str) -> WorldStateResponse:
        """Current world; creates version 0 on first use."""
        await self._require_project(project_id)
        record = await self.worlds.get_current(project_id)
        if record is None:
            record = await self.worlds.append(await self._initial_world(project_id))
        return WorldStateResponse(
            project_id=project_id,
            version=record.version,
            state=WorldState.model_validate(record.state),
            source_shot_id=record.source_shot_id,
        )

    async def _world_before(self, shot: Shot) -> WorldState:
        record = await self.worlds.get_before_shot(shot.project_id, shot.shot_index)
        if record is None:
            record = await self.worlds.append(await self._initial_world(shot.project_id))
        return WorldState.model_validate(record.state)

    # -- create_shot_spec ------------------------------------------------------

    async def create_shot_spec(
        self,
        project_id: str,
        content: ShotContent,
        *,
        shot_index: int | None = None,
        created_by: str | None = None,
    ) -> tuple[Shot, ShotVersion, bool]:
        """
        Persist a versioned ShotSpec.

        - no shot at shot_index -> new shot, version 1
        - shot exists            -> new version (parent_version = current)
        - identical content      -> no-op, returns the current version

        Returns (shot, version_row, created).
        """
        await self._require_project(project_id)
        index = shot_index if shot_index is not None else await self.shots.next_index(project_id)
        author = created_by or str(SHOTSPEC_BUILDER_AGENT_ID)

        shot = await self.shots.get_by_index(project_id, index)

        if shot is None:
            spec = make_spec(shot_id=shot_id_for(project_id, index), content=content, created_by=author)
            shot, row = await self.shots.create_shot(
                project_id=project_id, shot_index=index, spec=spec, content=content
            )
            created = True
        else:
            current = await self.shots.current_version(shot)
            candidate = make_spec(shot_id=shot_id_for(project_id, index), content=content)
            if current is not None and current.content_hash == candidate.content_hash:
                return shot, current, False  # idempotent: nothing changed

            previous = ShotSpec(
                shot_id=shot.id,
                shotspec_id=current.id,
                version=current.version,
                parent_version=current.parent_version,
                created_by=current.created_by,
                created_at=current.created_at,
                status=ShotSpecStatus(current.status),
                content_hash=current.content_hash,
            )
            spec = next_version(previous, content, created_by=author)
            row = await self.shots.add_version(shot, spec, content)
            created = True

        queue_event(
            self.session,
            make_event(
                event_type=EventType.SHOT_CREATED,
                project_id=project_id,
                payload={"shot_id": shot.id, "shot_index": index, "version": row.version},
            ),
        )
        return shot, row, created

    # -- validate_shot_spec ----------------------------------------------------

    async def validate_shot_spec(
        self,
        shot_id: str,
        *,
        version: int | None = None,
        advance_world_state: bool = True,
    ) -> ContinuityReport:
        """
        Continuity-check a ShotSpec version against the world as it stands
        right before this shot. Passing -> PLANNED (and, by default, the
        WorldState advances by this shot). Failing -> FAILED with the
        violations stored on the version.
        """
        shot = await self.shots.get(shot_id)
        if shot is None:
            raise _not_found("Shot")
        row = await self.shots.get_version(shot.id, version or shot.current_version)
        if row is None:
            raise _not_found("Shot version")

        content = ShotContent.model_validate(row.content)
        world = await self._world_before(shot)
        report = validate_continuity(content, world)

        status = ShotSpecStatus.PLANNED if report.passed else ShotSpecStatus.FAILED
        # Never downgrade a version that has already moved past planning
        # (e.g. BLENDER_READY) just because it was re-validated.
        if row.status in (ShotSpecStatus.DRAFT.value, ShotSpecStatus.PLANNED.value, ShotSpecStatus.FAILED.value):
            await self.shots.set_version_status(shot, row, status.value, report.model_dump(mode="json"))
        else:
            row.continuity = report.model_dump(mode="json")

        if report.passed and advance_world_state:
            await self._advance_world(shot, apply_shot(world, content))

        queue_event(
            self.session,
            make_event(
                event_type=EventType.CONTINUITY_CHECKED,
                project_id=shot.project_id,
                payload={
                    "shot_id": shot.id,
                    "version": row.version,
                    "passed": report.passed,
                    "violations": [v.code for v in report.violations],
                },
            ),
        )
        await self.session.flush()
        return report

    async def _advance_world(self, shot: Shot, new_world: WorldState) -> None:
        """Append the post-shot world - unless this shot already produced
        an identical one (re-validating unchanged shots must not grow the
        world_states history)."""
        existing = await self.worlds.latest_for_shot(shot.id)
        if existing is not None:
            previous = WorldState.model_validate(existing.state).model_dump(exclude={"version"})
            if previous == new_world.model_dump(exclude={"version"}):
                return
        await self.worlds.append(new_world, source_shot_id=shot.id)

    # -- reads -------------------------------------------------------------------

    async def _generation_for(self, shot_id: str, version: int):
        if version is None:
            return None
        return await self.generations.get_latest_for_shot(shot_id, version)

    async def list_shots(self, project_id: str) -> list[ShotResponse]:
        await self._require_project(project_id)
        responses = []
        for shot in await self.shots.list_by_project(project_id):
            current = await self.shots.current_version(shot)
            if current is not None:
                generation = await self._generation_for(shot.id, current.version)
                responses.append(shot_response(shot, current, generation))
        return responses

    async def get_shot(self, shot_id: str) -> ShotDetailResponse:
        shot = await self.shots.get(shot_id)
        if shot is None:
            raise _not_found("Shot")
        versions = await self.shots.list_versions(shot.id)
        current = next(v for v in versions if v.version == shot.current_version)
        current_generation = await self._generation_for(shot.id, current.version)
        base = shot_response(shot, current, current_generation)
        version_responses = []
        for v in versions:
            generation = current_generation if v.version == current.version else await self._generation_for(shot.id, v.version)
            version_responses.append(version_response(v, generation))
        return ShotDetailResponse(
            **base.model_dump(),
            versions=version_responses,
            physics_assets=await self._physics_assets(current),
        )

    async def _physics_assets(self, version: ShotVersion) -> list[ShotAssetResponse]:
        """Blender-stage assets for this version: the physics proxy plus
        every pass whose parent_asset is that proxy (Day 12)."""
        if version.physics_proxy_asset_id is None:
            return []
        from sqlalchemy import or_, select

        from src.database.models.asset import Asset

        proxy_id = version.physics_proxy_asset_id
        result = await self.session.execute(
            select(Asset)
            .where(or_(Asset.asset_id == proxy_id, Asset.parent_asset == proxy_id))
            .order_by(Asset.asset_type)
        )
        return [
            ShotAssetResponse(
                asset_id=a.asset_id,
                asset_type=a.asset_type,
                content_hash=a.content_hash,
                parent_asset=a.parent_asset,
                metadata=a.asset_metadata,
            )
            for a in result.scalars().all()
        ]

    # -- Gateway executors (agent-facing) -----------------------------------------

    async def tool_create_shot_spec(self, arguments: dict[str, Any]) -> dict[str, Any]:
        content = ShotContent.model_validate(arguments["content"])
        shot, row, created = await self.create_shot_spec(
            arguments["project_id"], content, shot_index=arguments.get("shot_index")
        )
        return {
            "shot_id": shot.id,
            "shot_index": shot.shot_index,
            "shotspec_id": row.id,
            "version": row.version,
            "parent_version": row.parent_version,
            "content_hash": row.content_hash,
            "created": created,
            "model": "shotspec-builder",
        }

    async def tool_validate_shot_spec(self, arguments: dict[str, Any]) -> dict[str, Any]:
        report = await self.validate_shot_spec(
            arguments["shot_id"],
            version=arguments.get("version"),
            advance_world_state=arguments.get("advance_world_state", True),
        )
        return {**report.model_dump(mode="json"), "model": "continuity-validator"}

    async def tool_get_world_state(self, arguments: dict[str, Any]) -> dict[str, Any]:
        world = await self.get_world_state(arguments["project_id"])
        return {**world.model_dump(mode="json"), "model": "world-state"}
