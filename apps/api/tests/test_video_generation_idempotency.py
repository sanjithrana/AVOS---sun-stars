"""
Week 3 Day 13 DoD (Engineer 1) - AVOS-03 v1.1 s9.5:

"Prove idempotency by firing the same generation request twice and
confirming the second call returns the cached result rather than
creating a new job/asset."

Real Postgres + the real audited Gateway path (dispatch_and_audit), same
as test_physics_before_pixels.py. generate_video_shot is physics-gated
(Day 12), so every call here first runs the Blender stage.
"""

import pytest
from sqlalchemy import func, select

from agentic_core.tool_gateway.permissions import AgentRole
from packages.contracts.shotspec import ShotContent
from src.core.assets.registry import AssetRegistry
from src.core.assets.storage import LocalAssetStorage
from src.core.blender.client import MockBlenderClient
from src.database.models.asset import Asset
from src.database.models.audit import AuditRecord
from src.database.models.video_generation import VideoGeneration
from src.repositories.project_repository import ProjectRepository
from src.repositories.shot_repository import ShotRepository
from src.services.blender_stage_service import BlenderStageService
from src.services.gateway_bridge import dispatch_and_audit
from src.services.shotspec_service import ShotSpecService
from src.services.video_generation_service import VideoGenerationError, VideoGenerationService
from tests.conftest import requires_db

pytestmark = requires_db


def _content(i: int = 0) -> ShotContent:
    return ShotContent(
        beat_label=f"beat_{i + 1}", start_time=i * 3.0, end_time=i * 3.0 + 3.0, narration=f"Line {i}.",
        description="A cheerful character waves at the camera.",
        style="bright, friendly storybook illustration",
        environment={"location": "main setting", "time_of_day": "morning", "weather": "clear"},
    )


async def _ready_shot(session, tmp_path, i: int = 0):
    """A shot whose Blender stage has completed - the only state
    generate_video_shot may run against."""
    project = await ProjectRepository(session).create(
        name="Generation", topic="Flowers", duration_seconds=12, aspect_ratio="9:16"
    )
    specs = ShotSpecService(session)
    shot, _, _ = await specs.create_shot_spec(project.id, _content(i), shot_index=i)
    await specs.validate_shot_spec(shot.id)
    await session.commit()
    stage = BlenderStageService(
        session, client=MockBlenderClient(),
        registry=AssetRegistry(session, storage=LocalAssetStorage(str(tmp_path))),
    )
    blender_result = await dispatch_and_audit(
        session, project_id=project.id, role=AgentRole.PHYSICS_AGENT, tool_name="run_blender_proxy",
        tool_input={"shot_id": shot.id}, executor=stage.tool_run_blender_proxy,
        agent_decision="Physics agent: blender proxy",
    )
    proxy_id = blender_result.result["physics_proxy_asset_id"]
    return project, shot, proxy_id, AssetRegistry(session, storage=LocalAssetStorage(str(tmp_path)))


async def _generate(session, project_id, executor, **tool_input):
    return await dispatch_and_audit(
        session, project_id=project_id, role=AgentRole.VIDEO_AGENT, tool_name="generate_video_shot",
        tool_input=tool_input, executor=executor, agent_decision="Video agent: generate 3 candidates",
    )


async def _counts(session):
    generations = (await session.execute(select(func.count()).select_from(VideoGeneration))).scalar_one()
    assets = (await session.execute(select(func.count()).select_from(Asset))).scalar_one()
    return generations, assets


@pytest.mark.asyncio
async def test_firing_the_same_request_twice_returns_the_cached_result(db_session, clean_db, captured_events, tmp_path):
    project, shot, proxy_id, registry = await _ready_shot(db_session, tmp_path)
    video = VideoGenerationService(db_session, registry=registry)

    first = await _generate(db_session, project.id, video.tool_generate_video_shot,
                             shot_id=shot.id, physics_proxy_asset_id=proxy_id)
    generations_after_1, assets_after_1 = await _counts(db_session)

    assert first.result["cached"] is False
    assert len(first.result["candidates"]) == 3
    assert first.result["status"] == "QA_PENDING"

    second = await _generate(db_session, project.id, video.tool_generate_video_shot,
                              shot_id=shot.id, physics_proxy_asset_id=proxy_id)
    generations_after_2, assets_after_2 = await _counts(db_session)

    # No new job (video_generations row) and no new assets on the repeat.
    assert generations_after_2 == generations_after_1
    assert assets_after_2 == assets_after_1
    assert second.result["cached"] is True
    assert second.result["video_generation_id"] == first.result["video_generation_id"]
    assert second.result["candidates"] == first.result["candidates"]
    assert second.result["idempotency_key"] == first.result["idempotency_key"]

    # Two dispatches -> two audit rows (every call is audited), even
    # though the second was a cache hit and did no generation work.
    rows = (await db_session.execute(
        select(AuditRecord).where(AuditRecord.project_id == project.id, AuditRecord.tool_name == "generate_video_shot")
    )).scalars().all()
    assert len(rows) == 2
    assert all(r.error is None for r in rows)


@pytest.mark.asyncio
async def test_explicit_idempotency_key_is_honored_across_two_calls(db_session, clean_db, captured_events, tmp_path):
    project, shot, proxy_id, registry = await _ready_shot(db_session, tmp_path)
    video = VideoGenerationService(db_session, registry=registry)
    key = "client-supplied-key-abc123"

    first = await _generate(db_session, project.id, video.tool_generate_video_shot,
                             shot_id=shot.id, physics_proxy_asset_id=proxy_id, idempotency_key=key)
    second = await _generate(db_session, project.id, video.tool_generate_video_shot,
                              shot_id=shot.id, physics_proxy_asset_id=proxy_id, idempotency_key=key)

    assert first.result["idempotency_key"] == key
    assert second.result["cached"] is True
    assert second.result["video_generation_id"] == first.result["video_generation_id"]


@pytest.mark.asyncio
async def test_two_different_shots_never_share_a_default_idempotency_key(db_session, clean_db, captured_events, tmp_path):
    project1, shot0, proxy0, registry = await _ready_shot(db_session, tmp_path, i=0)
    specs = ShotSpecService(db_session)
    shot1, _, _ = await specs.create_shot_spec(project1.id, _content(1), shot_index=1)
    await specs.validate_shot_spec(shot1.id)
    await db_session.commit()
    stage = BlenderStageService(db_session, client=MockBlenderClient(), registry=registry)
    b1 = await dispatch_and_audit(
        db_session, project_id=project1.id, role=AgentRole.PHYSICS_AGENT, tool_name="run_blender_proxy",
        tool_input={"shot_id": shot1.id}, executor=stage.tool_run_blender_proxy, agent_decision="x",
    )
    proxy1 = b1.result["physics_proxy_asset_id"]

    video = VideoGenerationService(db_session, registry=registry)
    r0 = await _generate(db_session, project1.id, video.tool_generate_video_shot, shot_id=shot0.id, physics_proxy_asset_id=proxy0)
    r1 = await _generate(db_session, project1.id, video.tool_generate_video_shot, shot_id=shot1.id, physics_proxy_asset_id=proxy1)

    assert r0.result["idempotency_key"] != r1.result["idempotency_key"]
    assert r0.result["video_generation_id"] != r1.result["video_generation_id"]
    assert {c["asset_id"] for c in r0.result["candidates"]}.isdisjoint({c["asset_id"] for c in r1.result["candidates"]})


@pytest.mark.asyncio
async def test_editing_a_shot_after_generation_gets_a_fresh_default_key(db_session, clean_db, captured_events, tmp_path):
    """A new physics proxy (from a ShotSpec edit) changes the *default*
    idempotency key, so re-generation after an edit is a fresh job, not
    a cache hit of the stale one - candidates must reflect the edit."""
    project, shot, old_proxy, registry = await _ready_shot(db_session, tmp_path)
    specs = ShotSpecService(db_session)
    video = VideoGenerationService(db_session, registry=registry)

    first = await _generate(db_session, project.id, video.tool_generate_video_shot,
                             shot_id=shot.id, physics_proxy_asset_id=old_proxy)

    edited = _content(0).model_copy(update={"description": "A different character bows deeply."})
    await specs.create_shot_spec(project.id, edited, shot_index=0)  # -> v2 DRAFT
    await specs.validate_shot_spec(shot.id)  # -> v2 PLANNED
    stage = BlenderStageService(db_session, client=MockBlenderClient(), registry=registry)
    b2 = await dispatch_and_audit(
        db_session, project_id=project.id, role=AgentRole.PHYSICS_AGENT, tool_name="run_blender_proxy",
        tool_input={"shot_id": shot.id}, executor=stage.tool_run_blender_proxy, agent_decision="x",
    )
    new_proxy = b2.result["physics_proxy_asset_id"]
    assert new_proxy != old_proxy

    second = await _generate(db_session, project.id, video.tool_generate_video_shot,
                              shot_id=shot.id, physics_proxy_asset_id=new_proxy)

    assert second.result["idempotency_key"] != first.result["idempotency_key"]
    assert second.result["video_generation_id"] != first.result["video_generation_id"]
    assert {c["asset_id"] for c in second.result["candidates"]}.isdisjoint(
        {c["asset_id"] for c in first.result["candidates"]}
    )


@pytest.mark.asyncio
async def test_mismatched_idempotency_key_reuse_across_shots_is_rejected(db_session, clean_db, captured_events, tmp_path):
    project, shot0, proxy0, registry = await _ready_shot(db_session, tmp_path, i=0)
    specs = ShotSpecService(db_session)
    shot1, _, _ = await specs.create_shot_spec(project.id, _content(1), shot_index=1)
    await specs.validate_shot_spec(shot1.id)
    await db_session.commit()
    stage = BlenderStageService(db_session, client=MockBlenderClient(), registry=registry)
    b1 = await dispatch_and_audit(
        db_session, project_id=project.id, role=AgentRole.PHYSICS_AGENT, tool_name="run_blender_proxy",
        tool_input={"shot_id": shot1.id}, executor=stage.tool_run_blender_proxy, agent_decision="x",
    )
    proxy1 = b1.result["physics_proxy_asset_id"]

    video = VideoGenerationService(db_session, registry=registry)
    await video.generate(shot0.id, physics_proxy_asset_id=proxy0, idempotency_key="shared-key")

    with pytest.raises(VideoGenerationError, match="already used for a different shot"):
        await video.generate(shot1.id, physics_proxy_asset_id=proxy1, idempotency_key="shared-key")


@pytest.mark.asyncio
async def test_generation_is_rejected_until_the_blender_stage_completes(db_session, clean_db, captured_events, tmp_path):
    from src.services.video_generation_service import VideoGenerationError

    project = await ProjectRepository(db_session).create(
        name="No proxy yet", topic="x", duration_seconds=6, aspect_ratio="9:16"
    )
    specs = ShotSpecService(db_session)
    shot, _, _ = await specs.create_shot_spec(project.id, _content(), shot_index=0)
    await specs.validate_shot_spec(shot.id)  # PLANNED, no proxy
    await db_session.commit()

    video = VideoGenerationService(db_session, registry=AssetRegistry(db_session, storage=LocalAssetStorage(str(tmp_path))))
    with pytest.raises(VideoGenerationError, match="does not match"):
        await video.generate(shot.id, physics_proxy_asset_id="00000000-0000-0000-0000-000000000000")
