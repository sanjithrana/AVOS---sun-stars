"""
Week 3 Day 14 DoD - the repair ladder is real, bounded, and durable.

Real Postgres + the real audited Gateway path (dispatch_and_audit), same
pattern as test_physics_before_pixels.py / test_video_generation_idempotency.py.

Three forced QA FAILs (the qa_results row is seeded directly, exactly as
the EOD checklist asks: "force a deliberate QA FAIL in a test fixture")
must escalate MICRO -> MACRO -> HUMAN_REQUIRED on attempts 1/2/3 - never
earlier, never later - and the attempt counter must survive a killed and
restarted worker: it is derived fresh from committed repair_plans rows
every call (RepairRepository.count_for_shot), never held in process
memory, so a brand new AsyncSession/engine connection (standing in for a
new worker process) resumes with the exact right next attempt number.
"""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from agentic_core.tool_gateway.permissions import AgentRole
from packages.contracts.qa import QADimension, QADimensionResult, QAResult as QAResultContract, QAStatus
from packages.contracts.shotspec import ShotContent
from src.core.assets.registry import AssetRegistry
from src.core.assets.storage import LocalAssetStorage
from src.core.blender.client import MockBlenderClient
from src.database.models.audit import AuditRecord
from src.database.models.repair import RepairPlan
from src.repositories.project_repository import ProjectRepository
from src.repositories.qa_repository import QARepository
from src.repositories.repair_repository import RepairRepository
from src.repositories.shot_repository import ShotRepository
from src.repositories.video_generation_repository import VideoGenerationRepository
from src.services.blender_stage_service import BlenderStageService
from src.services.gateway_bridge import dispatch_and_audit
from src.services.repair_service import RepairService, RepairServiceError
from src.services.shotspec_service import ShotSpecService
from src.services.video_generation_service import VideoGenerationService
from tests.conftest import requires_db

pytestmark = requires_db


def _content() -> ShotContent:
    return ShotContent(
        beat_label="beat_1", start_time=0.0, end_time=3.0, narration="A character waves.",
        description="A cheerful character waves at the camera.",
        style="bright, friendly storybook illustration",
        environment={"location": "main setting", "time_of_day": "morning", "weather": "clear"},
    )


def _fail_result(shot_id: str, video_asset_id: str) -> QAResultContract:
    """A deliberately-forced FAIL: geometry scores below the 0.6 pass
    threshold, exactly what a real committee run produces for a stale
    physics scaffold (agentic_core/tests/test_qa_committee.py proves the
    pure scoring logic directly) - seeded here so the ladder can be
    tested without having to fight the mock renderer into disagreeing
    with itself."""
    return QAResultContract(
        shot_id=shot_id,
        video_asset_id=video_asset_id,
        status=QAStatus.FAIL,
        score=0.35,
        confidence=0.9,
        evidence={"failing_dimensions": ["geometry"]},
        recommended_action="repair",
        dimensions=[
            QADimensionResult(dimension=QADimension.VISUAL, score=1.0, confidence=1.0),
            QADimensionResult(dimension=QADimension.GEOMETRY, score=0.1, confidence=1.0),
            QADimensionResult(dimension=QADimension.TEMPORAL, score=1.0, confidence=0.5),
            QADimensionResult(dimension=QADimension.IDENTITY, score=1.0, confidence=0.5),
            QADimensionResult(dimension=QADimension.AUDIO, score=1.0, confidence=0.5),
            QADimensionResult(dimension=QADimension.PROMPT_ADHERENCE, score=1.0, confidence=0.5),
        ],
    )


async def _generated_shot(session, tmp_path):
    """A shot all the way through Blender + generation - the only state
    repair (MICRO/MACRO) can regenerate candidates against."""
    project = await ProjectRepository(session).create(
        name="Repair ladder", topic="Flowers", duration_seconds=6, aspect_ratio="9:16"
    )
    specs = ShotSpecService(session)
    shot, _, _ = await specs.create_shot_spec(project.id, _content(), shot_index=0)
    await specs.validate_shot_spec(shot.id)
    await session.commit()

    registry = AssetRegistry(session, storage=LocalAssetStorage(str(tmp_path)))
    stage = BlenderStageService(session, client=MockBlenderClient(), registry=registry)
    blender = await dispatch_and_audit(
        session, project_id=project.id, role=AgentRole.PHYSICS_AGENT, tool_name="run_blender_proxy",
        tool_input={"shot_id": shot.id}, executor=stage.tool_run_blender_proxy, agent_decision="x",
    )
    proxy_id = blender.result["physics_proxy_asset_id"]

    video = VideoGenerationService(session, registry=registry)
    await dispatch_and_audit(
        session, project_id=project.id, role=AgentRole.VIDEO_AGENT, tool_name="generate_video_shot",
        tool_input={"shot_id": shot.id, "physics_proxy_asset_id": proxy_id},
        executor=video.tool_generate_video_shot, agent_decision="x",
    )
    await session.commit()
    return project, shot, registry


async def _seed_failing_qa(session, shot_id: str) -> str:
    generation = await VideoGenerationRepository(session).get_latest_for_shot(
        shot_id, (await ShotRepository(session).get(shot_id)).current_version
    )
    video_asset_id = generation.candidates[0]["asset_id"]
    record = await QARepository(session).create(shot_id, generation.asset_id, _fail_result(shot_id, video_asset_id))
    await session.commit()
    return str(record.id)


@pytest.mark.asyncio
async def test_three_forced_failures_escalate_micro_macro_human_required(db_session, clean_db, captured_events, tmp_path):
    project, shot, registry = await _generated_shot(db_session, tmp_path)
    await _seed_failing_qa(db_session, shot.id)

    repair = RepairService(db_session, video=VideoGenerationService(db_session, registry=registry))

    attempt1 = await dispatch_and_audit(
        db_session, project_id=project.id, role=AgentRole.REPAIR_AGENT, tool_name="repair_shot",
        tool_input={"shot_id": shot.id}, executor=repair.tool_repair_shot, agent_decision="x",
    )
    assert attempt1.result["attempt"] == 1
    assert attempt1.result["rung"] == "MICRO"
    assert attempt1.result["applied"] is True
    assert attempt1.result["status"] == "QA_PENDING"  # regenerated, awaiting another QA pass

    attempt2 = await dispatch_and_audit(
        db_session, project_id=project.id, role=AgentRole.REPAIR_AGENT, tool_name="repair_shot",
        tool_input={"shot_id": shot.id}, executor=repair.tool_repair_shot, agent_decision="x",
    )
    assert attempt2.result["attempt"] == 2
    assert attempt2.result["rung"] == "MACRO"
    assert attempt2.result["applied"] is True

    attempt3 = await dispatch_and_audit(
        db_session, project_id=project.id, role=AgentRole.REPAIR_AGENT, tool_name="repair_shot",
        tool_input={"shot_id": shot.id}, executor=repair.tool_repair_shot, agent_decision="x",
    )
    assert attempt3.result["attempt"] == 3
    assert attempt3.result["rung"] == "HUMAN_REQUIRED"
    assert attempt3.result["applied"] is False  # nothing auto-applied once a human is required
    assert attempt3.result["status"] == "REPAIRING"

    # A 4th call (still no human action taken) stays HUMAN_REQUIRED - it
    # never invents a rung past it and never loops back to MICRO.
    attempt4 = await dispatch_and_audit(
        db_session, project_id=project.id, role=AgentRole.REPAIR_AGENT, tool_name="repair_shot",
        tool_input={"shot_id": shot.id}, executor=repair.tool_repair_shot, agent_decision="x",
    )
    assert attempt4.result["attempt"] == 4
    assert attempt4.result["rung"] == "HUMAN_REQUIRED"
    assert attempt4.result["applied"] is False

    plans = (await db_session.execute(
        select(RepairPlan).where(RepairPlan.shot_id == shot.id).order_by(RepairPlan.attempt)
    )).scalars().all()
    assert [p.attempt for p in plans] == [1, 2, 3, 4]
    assert [p.rung for p in plans] == ["MICRO", "MACRO", "HUMAN_REQUIRED", "HUMAN_REQUIRED"]

    # Every repair_shot dispatch is audited (4 calls -> 4 audit rows).
    audits = (await db_session.execute(
        select(AuditRecord).where(AuditRecord.project_id == project.id, AuditRecord.tool_name == "repair_shot")
    )).scalars().all()
    assert len(audits) == 4 and all(a.error is None for a in audits)


@pytest.mark.asyncio
async def test_repair_ladder_survives_a_worker_restart(db_session, clean_db, captured_events, tmp_path, test_engine):
    """The attempt counter is never held in memory - it's a count of
    committed repair_plans rows - so resuming from a brand new
    connection (standing in for a killed-and-restarted worker) picks up
    exactly where the last one left off, not from attempt 1 again."""
    project, shot, registry = await _generated_shot(db_session, tmp_path)
    await _seed_failing_qa(db_session, shot.id)

    repair = RepairService(db_session, video=VideoGenerationService(db_session, registry=registry))
    first = await repair.repair(shot.id)
    assert first["attempt"] == 1 and first["rung"] == "MICRO"
    await db_session.commit()

    # Fresh engine connection + fresh session + fresh service instances:
    # nothing here shares Python state with the session/service above.
    session_factory = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as restarted_session:
        restarted_repair = RepairService(
            restarted_session,
            video=VideoGenerationService(restarted_session, registry=AssetRegistry(restarted_session, storage=registry.storage)),
        )
        second = await restarted_repair.repair(shot.id)
        assert second["attempt"] == 2  # not 1 again, and not skipping to 3
        assert second["rung"] == "MACRO"
        await restarted_session.commit()

        third = await restarted_repair.repair(shot.id)
        assert third["attempt"] == 3
        assert third["rung"] == "HUMAN_REQUIRED"
        await restarted_session.commit()

    # A third, independent connection sees the same durable count.
    async with session_factory() as verify_session:
        count = await RepairRepository(verify_session).count_for_shot(shot.id)
        assert count == 3


@pytest.mark.asyncio
async def test_repair_is_rejected_without_a_failing_qa_result(db_session, clean_db, captured_events, tmp_path):
    project, shot, registry = await _generated_shot(db_session, tmp_path)
    repair = RepairService(db_session, video=VideoGenerationService(db_session, registry=registry))

    with pytest.raises(RepairServiceError, match="no failing QA result"):
        await repair.repair(shot.id)


@pytest.mark.asyncio
async def test_permissions_apply_to_qa_and_repair_tools(db_session, clean_db, captured_events, tmp_path):
    from agentic_core.tool_gateway.gateway import ToolPermissionDeniedError

    project, shot, registry = await _generated_shot(db_session, tmp_path)
    await _seed_failing_qa(db_session, shot.id)
    repair = RepairService(db_session, video=VideoGenerationService(db_session, registry=registry))

    with pytest.raises(ToolPermissionDeniedError):  # Director may not run repairs itself
        await dispatch_and_audit(
            db_session, project_id=project.id, role=AgentRole.DIRECTOR, tool_name="repair_shot",
            tool_input={"shot_id": shot.id}, executor=repair.tool_repair_shot, agent_decision="x",
        )


@pytest.mark.asyncio
async def test_unrelated_shots_have_independent_attempt_counters(db_session, clean_db, captured_events, tmp_path):
    project, shot_a, registry = await _generated_shot(db_session, tmp_path)
    await _seed_failing_qa(db_session, shot_a.id)

    specs = ShotSpecService(db_session)
    shot_b, _, _ = await specs.create_shot_spec(project.id, _content(), shot_index=1)
    await specs.validate_shot_spec(shot_b.id)
    await db_session.commit()
    stage = BlenderStageService(db_session, client=MockBlenderClient(), registry=registry)
    b = await dispatch_and_audit(
        db_session, project_id=project.id, role=AgentRole.PHYSICS_AGENT, tool_name="run_blender_proxy",
        tool_input={"shot_id": shot_b.id}, executor=stage.tool_run_blender_proxy, agent_decision="x",
    )
    video = VideoGenerationService(db_session, registry=registry)
    await dispatch_and_audit(
        db_session, project_id=project.id, role=AgentRole.VIDEO_AGENT, tool_name="generate_video_shot",
        tool_input={"shot_id": shot_b.id, "physics_proxy_asset_id": b.result["physics_proxy_asset_id"]},
        executor=video.tool_generate_video_shot, agent_decision="x",
    )
    await db_session.commit()
    await _seed_failing_qa(db_session, shot_b.id)

    repair = RepairService(db_session, video=video)
    a1 = await repair.repair(shot_a.id)
    b1 = await repair.repair(shot_b.id)
    a2 = await repair.repair(shot_a.id)

    assert (a1["attempt"], a1["rung"]) == (1, "MICRO")
    assert (b1["attempt"], b1["rung"]) == (1, "MICRO")  # shot_b starts fresh, unaffected by shot_a
    assert (a2["attempt"], a2["rung"]) == (2, "MACRO")
