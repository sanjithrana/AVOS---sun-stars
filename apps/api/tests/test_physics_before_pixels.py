"""
Week 3 Day 12 DoD - physics-before-pixels as a passing integration test.

Real Postgres + the real audited Gateway path (dispatch_and_audit):
generate_video_shot is rejected with MISSING_DEPENDENCY for a shot whose
Blender stage hasn't completed; the executor never runs; the rejection
is audited. After run_blender_proxy completes, the same call is allowed -
but only with that shot's own, current physics proxy.
"""

import uuid

import pytest
from sqlalchemy import select

from agentic_core.tool_gateway.constitution import MissingDependencyError
from agentic_core.tool_gateway.permissions import AgentRole
from packages.contracts.shotspec import ShotContent
from src.core.assets.registry import AssetRegistry
from src.core.assets.storage import LocalAssetStorage
from src.core.blender.client import MockBlenderClient
from src.database.models.audit import AuditRecord
from src.repositories.project_repository import ProjectRepository
from src.services.blender_stage_service import BlenderStageService
from src.services.gateway_bridge import dispatch_and_audit
from src.services.shotspec_service import ShotSpecService
from tests.conftest import requires_db

pytestmark = requires_db


class VideoExecutor:
    """Stand-in for the (Week 4) ComfyUI executor; records whether it ran."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def __call__(self, arguments: dict) -> dict:
        self.calls.append(arguments)
        return {"model": "test-video", "shot_id": arguments["shot_id"]}


def _content(i: int) -> ShotContent:
    return ShotContent(
        beat_label=f"beat_{i + 1}", start_time=i * 3.0, end_time=i * 3.0 + 3.0, narration=f"Line {i}.",
        style="bright, friendly storybook illustration",
        environment={"location": "main setting", "time_of_day": "morning", "weather": "clear"},
    )


async def _setup(session, tmp_path, n=2):
    project = await ProjectRepository(session).create(
        name="Physics", topic="Flowers", duration_seconds=12, aspect_ratio="9:16"
    )
    specs = ShotSpecService(session)
    shots = []
    for i in range(n):
        shot, _, _ = await specs.create_shot_spec(project.id, _content(i), shot_index=i)
        await specs.validate_shot_spec(shot.id)
        shots.append(shot)
    await session.commit()
    stage = BlenderStageService(
        session, client=MockBlenderClient(),
        registry=AssetRegistry(session, storage=LocalAssetStorage(str(tmp_path))),
    )
    return project, shots, specs, stage


async def _generate(session, project_id, executor, **tool_input):
    return await dispatch_and_audit(
        session, project_id=project_id, role=AgentRole.VIDEO_AGENT, tool_name="generate_video_shot",
        tool_input=tool_input, executor=executor, agent_decision="Video agent: render shot",
    )


async def _blender(session, project_id, stage, shot_id):
    result = await dispatch_and_audit(
        session, project_id=project_id, role=AgentRole.PHYSICS_AGENT, tool_name="run_blender_proxy",
        tool_input={"shot_id": shot_id}, executor=stage.tool_run_blender_proxy,
        agent_decision="Physics agent: blender proxy",
    )
    return result.result["physics_proxy_asset_id"]


async def _errors(session, project_id, tool_name="generate_video_shot"):
    rows = (await session.execute(
        select(AuditRecord).where(AuditRecord.project_id == project_id, AuditRecord.tool_name == tool_name)
        .order_by(AuditRecord.created_at)
    )).scalars().all()
    return [r.error for r in rows]


@pytest.mark.asyncio
async def test_generate_video_shot_rejected_before_blender_stage(db_session, clean_db, captured_events, tmp_path):
    project, (shot, _), _, _ = await _setup(db_session, tmp_path)
    video = VideoExecutor()

    # 1. No physics proxy named at all.
    with pytest.raises(MissingDependencyError) as info:
        await _generate(db_session, project.id, video, shot_id=shot.id)
    assert info.value.code == "MISSING_DEPENDENCY"

    # 2. A made-up proxy id for a shot whose Blender stage never ran.
    with pytest.raises(MissingDependencyError, match="before the Blender stage completed"):
        await _generate(db_session, project.id, video, shot_id=shot.id,
                        physics_proxy_asset_id=str(uuid.uuid4()))

    # 3. Unknown shot.
    with pytest.raises(MissingDependencyError, match="unknown shot"):
        await _generate(db_session, project.id, video, shot_id=str(uuid.uuid4()),
                        physics_proxy_asset_id=str(uuid.uuid4()))

    assert video.calls == []  # the executor never ran
    errors = await _errors(db_session, project.id)
    assert len(errors) == 3 and all("MISSING_DEPENDENCY" in e for e in errors)


@pytest.mark.asyncio
async def test_out_of_order_rejected_then_allowed_in_order(db_session, clean_db, captured_events, tmp_path):
    project, (s0, s1), specs, stage = await _setup(db_session, tmp_path)
    video = VideoExecutor()

    # Out of order: pixels first -> rejected.
    with pytest.raises(MissingDependencyError):
        await _generate(db_session, project.id, video, shot_id=s0.id)

    # In order: Blender stage, then pixels -> allowed.
    proxy0 = await _blender(db_session, project.id, stage, s0.id)
    result = await _generate(db_session, project.id, video, shot_id=s0.id, physics_proxy_asset_id=proxy0)
    assert result.status == "SUCCESS" and len(video.calls) == 1

    # Shot 1 can't borrow shot 0's proxy (Blender hasn't run for shot 1).
    with pytest.raises(MissingDependencyError):
        await _generate(db_session, project.id, video, shot_id=s1.id, physics_proxy_asset_id=proxy0)
    proxy1 = await _blender(db_session, project.id, stage, s1.id)
    # ...nor after it has - it must be its own proxy.
    with pytest.raises(MissingDependencyError, match="not the physics proxy"):
        await _generate(db_session, project.id, video, shot_id=s1.id, physics_proxy_asset_id=proxy0)
    await _generate(db_session, project.id, video, shot_id=s1.id, physics_proxy_asset_id=proxy1)
    assert len(video.calls) == 2

    errors = await _errors(db_session, project.id)
    assert [e is None for e in errors] == [False, True, False, False, True]


@pytest.mark.asyncio
async def test_editing_a_shot_invalidates_its_physics_proxy(db_session, clean_db, captured_events, tmp_path):
    """A ShotSpec edited after rendering needs a fresh Blender pass: the
    old proxy is stale for the new version."""
    project, (s0, _), specs, stage = await _setup(db_session, tmp_path)
    video = VideoExecutor()
    old_proxy = await _blender(db_session, project.id, stage, s0.id)

    edited = _content(0).model_copy(update={"narration": "Edited line."})
    await specs.create_shot_spec(project.id, edited, shot_index=0)  # -> v2, DRAFT
    with pytest.raises(MissingDependencyError):
        await _generate(db_session, project.id, video, shot_id=s0.id, physics_proxy_asset_id=old_proxy)

    await specs.validate_shot_spec(s0.id)  # v2 PLANNED
    new_proxy = await _blender(db_session, project.id, stage, s0.id)
    assert new_proxy != old_proxy
    with pytest.raises(MissingDependencyError, match="stale"):
        await _generate(db_session, project.id, video, shot_id=s0.id, physics_proxy_asset_id=old_proxy)
    await _generate(db_session, project.id, video, shot_id=s0.id, physics_proxy_asset_id=new_proxy)
    assert len(video.calls) == 1


@pytest.mark.asyncio
async def test_permissions_still_apply_to_the_pixel_and_blender_tools(db_session, clean_db, captured_events, tmp_path):
    from agentic_core.tool_gateway.gateway import ToolPermissionDeniedError

    project, (s0, _), _, stage = await _setup(db_session, tmp_path)
    with pytest.raises(ToolPermissionDeniedError):  # Director may not render pixels itself
        await dispatch_and_audit(
            db_session, project_id=project.id, role=AgentRole.DIRECTOR, tool_name="generate_video_shot",
            tool_input={"shot_id": s0.id}, executor=VideoExecutor(), agent_decision="x",
        )
    with pytest.raises(ToolPermissionDeniedError):  # Video agent may not run Blender
        await dispatch_and_audit(
            db_session, project_id=project.id, role=AgentRole.VIDEO_AGENT, tool_name="run_blender_proxy",
            tool_input={"shot_id": s0.id}, executor=stage.tool_run_blender_proxy, agent_decision="x",
        )
