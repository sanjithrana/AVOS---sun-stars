"""
Day 7 + Day 9 + Day 10 checklist, against a real Postgres:
  - ProjectSummary assembled from seeded DB data
  - research -> script -> a human_gates row with status=pending exists
  - every gateway dispatch produces exactly one audit_records row
  - budget_spent increments from audit costs; warning/exceeded events fire
"""

import pytest
from sqlalchemy import func, select

from src.database.models.audit import AuditRecord
from src.database.models.human_gate import HumanGate
from src.repositories.project_repository import ProjectRepository
from src.services.director_service import DirectorService, DirectorStoppedError
from tests.conftest import requires_db

pytestmark = requires_db


async def _seed_project(session, **overrides):
    project = await ProjectRepository(session).create(
        name=overrides.get("name", "Flowers for Kids"),
        topic=overrides.get("topic", "Flowers for Kids"),
        duration_seconds=overrides.get("duration_seconds", 30),
        aspect_ratio=overrides.get("aspect_ratio", "9:16"),
        budget_limit=overrides.get("budget_limit"),
    )
    await session.commit()
    return project


async def _audit_count(session, project_id: str) -> int:
    result = await session.execute(
        select(func.count()).select_from(AuditRecord).where(AuditRecord.project_id == project_id)
    )
    return result.scalar_one()


@pytest.mark.asyncio
async def test_project_summary_is_assembled_from_db(db_session, clean_db):
    project = await _seed_project(db_session, topic="Honey bees", duration_seconds=45, budget_limit=3.0)

    summary = await DirectorService(db_session).build_summary(project.id)

    assert summary.project_id == project.id
    assert summary.topic == "Honey bees"
    assert summary.duration_seconds == 45
    assert summary.aspect_ratio == "9:16"
    assert summary.status == "planning"
    assert summary.budget_limit == 3.0
    assert summary.budget_spent == 0


@pytest.mark.asyncio
async def test_research_then_script_opens_pending_gate(db_session, clean_db, captured_events):
    project = await _seed_project(db_session)
    service = DirectorService(db_session)

    notes = await service.research(project.id)
    assert len(notes) >= 1 and all(isinstance(n, str) for n in notes)

    gate = await service.write_script(project.id, research_notes=notes, workflow_id="wf-test-1")

    stored = await db_session.get(HumanGate, gate.id)
    assert stored.status == "pending"
    assert stored.gate_type == "script_approval"
    assert stored.payload["scenes"], "gate must carry the generated script"
    # Research notes are used as narration content, not leaked as a blob.
    assert "{" not in stored.payload["scenes"][0]["narration"]

    refreshed = await ProjectRepository(db_session).get(project.id)
    assert refreshed.status == "awaiting_approval"

    types = captured_events.types()
    assert "SCRIPT_GENERATED" in types
    assert "HUMAN_GATE_OPENED" in types
    assert types.index("SCRIPT_GENERATED") < types.index("HUMAN_GATE_OPENED")


@pytest.mark.asyncio
async def test_every_dispatch_writes_exactly_one_audit_row(db_session, clean_db, captured_events):
    project = await _seed_project(db_session)
    service = DirectorService(db_session)

    await service.research(project.id)  # search_memory + research_topic
    assert await _audit_count(db_session, project.id) == 2

    await service.write_script(project.id, research_notes=["a fact"], workflow_id="wf-audit")
    assert await _audit_count(db_session, project.id) == 3

    rows = (
        await db_session.execute(
            select(AuditRecord).where(AuditRecord.project_id == project.id).order_by(AuditRecord.created_at)
        )
    ).scalars().all()
    assert [r.tool_name for r in rows] == ["search_memory", "research_topic", "generate_script"]
    assert all(r.agent_decision for r in rows)
    assert captured_events.types().count("AGENT_ACTION_RECORDED") == 3


@pytest.mark.asyncio
async def test_write_script_is_idempotent_per_workflow(db_session, clean_db, captured_events):
    project = await _seed_project(db_session)
    service = DirectorService(db_session)

    first = await service.write_script(project.id, research_notes=[], workflow_id="wf-retry")
    second = await service.write_script(project.id, research_notes=[], workflow_id="wf-retry")

    assert first.id == second.id
    count = (
        await db_session.execute(select(func.count()).select_from(HumanGate).where(HumanGate.project_id == project.id))
    ).scalar_one()
    assert count == 1


@pytest.mark.asyncio
async def test_budget_increments_and_emits_warning_then_stops(db_session, clean_db, captured_events):
    # Each tool call costs 0.01 (placeholder). Limit 0.025 -> after the
    # 2nd call we're at 80% (warning), after the 3rd at >=100%.
    project = await _seed_project(db_session, budget_limit=0.025)
    service = DirectorService(db_session)

    await service.research(project.id)
    refreshed = await ProjectRepository(db_session).get(project.id)
    await db_session.refresh(refreshed)
    assert float(refreshed.budget_spent) == pytest.approx(0.02)
    assert "BUDGET_WARNING" in captured_events.types()

    await service.write_script(project.id, research_notes=[], workflow_id="wf-budget")
    assert "BUDGET_EXCEEDED" in captured_events.types()

    # The Director now refuses to spend more.
    with pytest.raises(DirectorStoppedError):
        await service.research(project.id)
