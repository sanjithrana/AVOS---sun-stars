"""
Week 3 Day 14 - QA committee, end to end (Engineer 1 side).

Real Postgres + the real audited Gateway path: run_qa_committee reads the
candidate thumbnail and physics-proxy scene straight out of the Asset
Registry (not a description of them) and persists exactly one qa_results
row, moving the shot to PASSED or FAILED.
"""

import pytest
from sqlalchemy import select

from agentic_core.tool_gateway.permissions import AgentRole
from packages.contracts.shotspec import ShotContent
from src.core.assets.registry import AssetRegistry
from src.core.assets.storage import LocalAssetStorage
from src.core.blender.client import MockBlenderClient
from src.database.models.audit import AuditRecord
from src.repositories.project_repository import ProjectRepository
from src.services.blender_stage_service import BlenderStageService
from src.services.gateway_bridge import dispatch_and_audit
from src.services.qa_service import QACommitteeService, QAServiceError, qa_result_response, shot_qa_state
from src.services.shotspec_service import ShotSpecService
from src.services.video_generation_service import VideoGenerationService
from src.repositories.qa_repository import QARepository
from src.repositories.repair_repository import RepairRepository
from tests.conftest import requires_db

pytestmark = requires_db


def _content() -> ShotContent:
    return ShotContent(
        beat_label="beat_1", start_time=0.0, end_time=3.0, narration="A character waves.",
        description="A cheerful character waves at the camera.",
        style="bright, friendly storybook illustration",
        environment={"location": "main setting", "time_of_day": "morning", "weather": "clear"},
    )


async def _project_and_shot(session):
    project = await ProjectRepository(session).create(
        name="QA committee", topic="Flowers", duration_seconds=6, aspect_ratio="9:16"
    )
    specs = ShotSpecService(session)
    shot, _, _ = await specs.create_shot_spec(project.id, _content(), shot_index=0)
    await specs.validate_shot_spec(shot.id)
    await session.commit()
    return project, shot


@pytest.mark.asyncio
async def test_qa_committee_rejects_a_shot_with_no_candidates_yet(db_session, clean_db, captured_events, tmp_path):
    project, shot = await _project_and_shot(db_session)
    qa = QACommitteeService(db_session, registry=AssetRegistry(db_session, storage=LocalAssetStorage(str(tmp_path))))

    with pytest.raises(QAServiceError, match="no generated candidates"):
        await qa.run(shot.id)


@pytest.mark.asyncio
async def test_a_correctly_scaffolded_shot_passes_qa_and_the_row_is_persisted(db_session, clean_db, captured_events, tmp_path):
    project, shot = await _project_and_shot(db_session)
    registry = AssetRegistry(db_session, storage=LocalAssetStorage(str(tmp_path)))
    stage = BlenderStageService(db_session, client=MockBlenderClient(), registry=registry)
    blender = await dispatch_and_audit(
        db_session, project_id=project.id, role=AgentRole.PHYSICS_AGENT, tool_name="run_blender_proxy",
        tool_input={"shot_id": shot.id}, executor=stage.tool_run_blender_proxy, agent_decision="x",
    )
    video = VideoGenerationService(db_session, registry=registry)
    await dispatch_and_audit(
        db_session, project_id=project.id, role=AgentRole.VIDEO_AGENT, tool_name="generate_video_shot",
        tool_input={"shot_id": shot.id, "physics_proxy_asset_id": blender.result["physics_proxy_asset_id"]},
        executor=video.tool_generate_video_shot, agent_decision="x",
    )
    await db_session.commit()

    qa = QACommitteeService(db_session, registry=registry)
    result = await dispatch_and_audit(
        db_session, project_id=project.id, role=AgentRole.QA_AGENT, tool_name="run_qa_committee",
        tool_input={"shot_id": shot.id}, executor=qa.tool_run_qa_committee, agent_decision="x",
    )
    await db_session.commit()

    assert result.result["status"] == "PASS"
    assert result.result["score"] > 0.6

    row = await QARepository(db_session).get_latest_for_shot(shot.id)
    assert row is not None
    assert row.committee_verdict.value == "PASS"
    assert row.visual_pass is True and row.geometry_pass is True

    from src.repositories.shot_repository import ShotRepository
    refreshed = await ShotRepository(db_session).get(shot.id)
    assert refreshed.status == "PASSED"

    state = await shot_qa_state(QARepository(db_session), RepairRepository(db_session), shot.id)
    assert state.latest_result is not None
    assert state.latest_result.status == "PASS"
    assert state.repairs == []

    audits = (await db_session.execute(
        select(AuditRecord).where(AuditRecord.project_id == project.id, AuditRecord.tool_name == "run_qa_committee")
    )).scalars().all()
    assert len(audits) == 1 and audits[0].error is None


@pytest.mark.asyncio
async def test_qa_result_response_reconstructs_the_overall_score_from_dimensions(db_session, clean_db, captured_events, tmp_path):
    project, shot = await _project_and_shot(db_session)
    registry = AssetRegistry(db_session, storage=LocalAssetStorage(str(tmp_path)))
    stage = BlenderStageService(db_session, client=MockBlenderClient(), registry=registry)
    blender = await dispatch_and_audit(
        db_session, project_id=project.id, role=AgentRole.PHYSICS_AGENT, tool_name="run_blender_proxy",
        tool_input={"shot_id": shot.id}, executor=stage.tool_run_blender_proxy, agent_decision="x",
    )
    video = VideoGenerationService(db_session, registry=registry)
    await dispatch_and_audit(
        db_session, project_id=project.id, role=AgentRole.VIDEO_AGENT, tool_name="generate_video_shot",
        tool_input={"shot_id": shot.id, "physics_proxy_asset_id": blender.result["physics_proxy_asset_id"]},
        executor=video.tool_generate_video_shot, agent_decision="x",
    )
    await db_session.commit()
    qa = QACommitteeService(db_session, registry=registry)
    await qa.run(shot.id)

    row = await QARepository(db_session).get_latest_for_shot(shot.id)
    response = qa_result_response(row)
    assert len(response.dimensions) == 6
    assert response.score == pytest.approx(sum(d.score for d in response.dimensions) / 6, abs=1e-4)
