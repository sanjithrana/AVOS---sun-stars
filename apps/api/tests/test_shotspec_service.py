"""
Week 3 Day 11 (real Postgres):
  - create_shot_spec persists a versioned ShotSpec row correctly
  - editing creates version N+1 with parent_version N; identical content is a no-op
  - validate_shot_spec flags continuity violations against the world *before* the shot
  - get_world_state / world advances once per accepted shot
  - the three tools are Gateway-callable and audited
  - planning from beats creates one shot per beat and never reverts edits
"""

import pytest
from sqlalchemy import func, select

from agentic_core.shotspec.builder import SHOTSPEC_BUILDER_AGENT_ID, content_hash, shot_id_for
from agentic_core.tool_gateway.permissions import AgentRole
from packages.contracts.shotspec import ShotContent
from packages.contracts.world_state import CharacterState
from src.database.models.audit import AuditRecord
from src.database.models.human_gate import HumanGate
from src.database.models.job import JobRecord
from src.database.models.shot_version import ShotVersion
from src.database.models.world_state import WorldStateRecord
from src.repositories.project_repository import ProjectRepository
from src.services.gateway_bridge import dispatch_and_audit
from src.services.shot_planning_service import ShotPlanningPrerequisiteError, ShotPlanningService
from src.services.shotspec_service import ShotSpecService
from tests.conftest import requires_db

pytestmark = requires_db


async def _project(session):
    project = await ProjectRepository(session).create(
        name="Shots", topic="Flowers", duration_seconds=12, aspect_ratio="9:16"
    )
    await session.commit()
    return project


def _content(**kw) -> ShotContent:
    base = dict(
        beat_label="beat_1", start_time=0.0, end_time=3.0, narration="Hello flowers.",
        style="bright, friendly storybook illustration",
        environment={"location": "main setting", "time_of_day": "morning", "weather": "clear"},
    )
    base.update(kw)
    return ShotContent(**base)


async def _count(session, model, *where):
    return (await session.execute(select(func.count()).select_from(model).where(*where))).scalar_one()


@pytest.mark.asyncio
async def test_create_shot_spec_persists_versioned_row(db_session, clean_db, captured_events):
    project = await _project(db_session)
    content = _content()

    shot, row, created = await ShotSpecService(db_session).create_shot_spec(project.id, content)
    from src.core.events.outbox import commit_and_publish

    await commit_and_publish(db_session)
    assert captured_events.types() == ["SHOT_CREATED"]

    assert created is True
    assert shot.id == str(shot_id_for(project.id, 0))
    assert (shot.shot_index, shot.current_version, shot.status) == (0, 1, "DRAFT")
    assert (shot.start_time, shot.end_time, shot.beat_label) == (0.0, 3.0, "beat_1")

    stored = await db_session.get(ShotVersion, row.id)
    assert stored.version == 1
    assert stored.parent_version is None
    assert stored.status == "DRAFT"
    assert stored.content_hash == content_hash(content)
    assert stored.created_by == str(SHOTSPEC_BUILDER_AGENT_ID)
    assert ShotContent.model_validate(stored.content) == content


@pytest.mark.asyncio
async def test_edit_creates_new_version_and_identical_content_is_noop(db_session, clean_db, captured_events):
    project = await _project(db_session)
    service = ShotSpecService(db_session)
    shot, v1, _ = await service.create_shot_spec(project.id, _content(), shot_index=0)

    same_shot, same_row, created = await service.create_shot_spec(project.id, _content(), shot_index=0)
    assert created is False and same_row.id == v1.id

    _, v2, created = await service.create_shot_spec(project.id, _content(narration="Edited."), shot_index=0)
    assert created is True
    assert (v2.version, v2.parent_version) == (2, 1)
    assert v2.content_hash != v1.content_hash
    assert shot.current_version == 2
    assert await _count(db_session, ShotVersion, ShotVersion.shot_id == shot.id) == 2


@pytest.mark.asyncio
async def test_validate_flags_violation_and_advances_world_only_on_pass(db_session, clean_db, captured_events):
    project = await _project(db_session)
    service = ShotSpecService(db_session)

    s0, _, _ = await service.create_shot_spec(
        project.id, _content(characters={"Milo": CharacterState(clothing="yellow shirt")}), shot_index=0
    )
    report0 = await service.validate_shot_spec(s0.id)
    assert report0.passed  # NEW_CHARACTER warning only
    assert s0.status == "PLANNED"
    world = await service.get_world_state(project.id)
    assert world.version == 1 and world.state.characters["Milo"].clothing == "yellow shirt"

    s1, _, _ = await service.create_shot_spec(
        project.id,
        _content(beat_label="beat_2", start_time=3.0, end_time=6.0,
                 characters={"Milo": CharacterState(clothing="red jacket")}),
        shot_index=1,
    )
    report1 = await service.validate_shot_spec(s1.id)
    assert not report1.passed
    assert [v.code for v in report1.errors] == ["CHARACTER_CLOTHING_MISMATCH"]
    assert s1.status == "FAILED"
    assert (await service.get_world_state(project.id)).version == 1  # failed shots don't advance

    stored = (await service.get_shot(s1.id)).spec.continuity
    assert stored is not None and stored.passed is False

    # Re-validating shot 0 later compares against the world *before* it,
    # not the newest world, and doesn't duplicate history.
    assert (await service.validate_shot_spec(s0.id)).passed
    assert await _count(db_session, WorldStateRecord, WorldStateRecord.project_id == project.id) == 2


@pytest.mark.asyncio
async def test_tools_are_gateway_callable_and_audited(db_session, clean_db, captured_events):
    project = await _project(db_session)
    service = ShotSpecService(db_session)

    created = await dispatch_and_audit(
        db_session, project_id=project.id, role=AgentRole.DIRECTOR, tool_name="create_shot_spec",
        tool_input={"project_id": project.id, "content": _content().model_dump(mode="json")},
        executor=service.tool_create_shot_spec, agent_decision="test create",
    )
    validated = await dispatch_and_audit(
        db_session, project_id=project.id, role=AgentRole.DIRECTOR, tool_name="validate_shot_spec",
        tool_input={"shot_id": created.result["shot_id"]},
        executor=service.tool_validate_shot_spec, agent_decision="test validate",
    )
    world = await dispatch_and_audit(
        db_session, project_id=project.id, role=AgentRole.DIRECTOR, tool_name="get_world_state",
        tool_input={"project_id": project.id},
        executor=service.tool_get_world_state, agent_decision="test world",
    )

    assert created.result["version"] == 1
    assert validated.result["passed"] is True
    assert world.result["version"] == 1
    assert await _count(db_session, AuditRecord, AuditRecord.project_id == project.id) == 3


@pytest.mark.asyncio
async def test_gateway_rejects_bad_input_and_wrong_role(db_session, clean_db, captured_events):
    from agentic_core.tool_gateway.gateway import ToolPermissionDeniedError
    from tool_gateway.validation import ToolValidationError

    project = await _project(db_session)
    service = ShotSpecService(db_session)

    with pytest.raises(ToolValidationError):
        await dispatch_and_audit(
            db_session, project_id=project.id, role=AgentRole.DIRECTOR, tool_name="create_shot_spec",
            tool_input={"project_id": project.id}, executor=service.tool_create_shot_spec,
            agent_decision="missing content",
        )
    with pytest.raises(ToolPermissionDeniedError):
        await dispatch_and_audit(
            db_session, project_id=project.id, role=AgentRole.RESEARCH_AGENT, tool_name="create_shot_spec",
            tool_input={"project_id": project.id, "content": _content().model_dump(mode="json")},
            executor=service.tool_create_shot_spec, agent_decision="wrong role",
        )


async def _seed_completed_audio(session, project_id: str) -> None:
    script = {
        "project_id": project_id, "topic": "Flowers", "model": "mock", "total_estimated_seconds": 6,
        "scenes": [
            {"index": 0, "narration": "Hello flowers. Look here.", "visual_description": "Garden.",
             "estimated_seconds": 3},
            {"index": 1, "narration": "Grow tall.", "visual_description": "Sunflower.",
             "estimated_seconds": 3},
        ],
    }
    session.add(HumanGate(id=__import__("uuid").uuid4(), project_id=project_id, gate_type="script_approval",
                          status="approved", payload=script))
    session.add(JobRecord(
        id=__import__("uuid").uuid4(), project_id=project_id, job_type="video_generation", status="completed",
        output_payload={"audio": {
            "duration_seconds": 6.0,
            "sentences": [
                {"text": "Hello flowers.", "start": 0.0, "end": 2.0, "word_count": 2},
                {"text": "Look here.", "start": 2.0, "end": 4.0, "word_count": 2},
                {"text": "Grow tall.", "start": 4.0, "end": 6.0, "word_count": 2},
            ],
            "beats": [{"time": 0.0, "label": "beat_1"}, {"time": 2.0, "label": "beat_2"},
                      {"time": 4.0, "label": "beat_3"}],
        }},
    ))
    await session.commit()


@pytest.mark.asyncio
async def test_plan_shots_from_beats_and_never_revert_edits(db_session, clean_db, captured_events):
    project = await _project(db_session)
    planner = ShotPlanningService(db_session)

    with pytest.raises(ShotPlanningPrerequisiteError):
        await planner.plan_shots(project.id)

    await _seed_completed_audio(db_session, project.id)
    summaries = await planner.plan_shots(project.id)

    assert [s["shot_index"] for s in summaries] == [0, 1, 2]
    assert all(s["continuity_passed"] for s in summaries)
    shots = await ShotSpecService(db_session).list_shots(project.id)
    # Week 3 Day 13: plan_shots now also runs the generation stage, so a
    # fully-planned shot lands on QA_PENDING (3 candidates), not just
    # BLENDER_READY.
    assert [s.status for s in shots] == ["QA_PENDING"] * 3
    assert all(s.spec.physics_proxy_asset_id for s in shots)
    assert all(s.spec.video_generation_asset_id for s in shots)
    assert all(len(s.spec.video_generation.candidates) == 3 for s in shots)
    assert [s.spec.content.scene_index for s in shots] == [0, 0, 1]

    # 4 audited tool calls per shot: create, validate, run_blender_proxy,
    # generate_video_shot.
    assert await _count(db_session, AuditRecord, AuditRecord.project_id == project.id) == 12

    # Human edit survives re-planning.
    edited = shots[1].spec.content.model_copy(update={"narration": "Human edit."})
    await ShotSpecService(db_session).create_shot_spec(project.id, edited, shot_index=1)
    again = await planner.plan_shots(project.id)
    assert all(s["skipped"] for s in again)
    after = await ShotSpecService(db_session).list_shots(project.id)
    assert after[1].spec.content.narration == "Human edit."
