"""Day 7: POST /gates/{id}/approve|reject update backend state."""

import pytest

from src.errors import APIException
from src.repositories.human_gate_repository import HumanGateRepository
from src.repositories.project_repository import ProjectRepository
from src.services.human_gate_service import HumanGateService
from tests.conftest import requires_db

pytestmark = requires_db


async def _gate(session, workflow_id=None):
    project = await ProjectRepository(session).create(
        name="p", topic="t", duration_seconds=10, aspect_ratio="9:16"
    )
    gate = await HumanGateRepository(session).create(
        project_id=project.id,
        gate_type="script_approval",
        payload={"scenes": []},
        workflow_id=workflow_id,
    )
    await session.commit()
    return project, gate


@pytest.mark.asyncio
async def test_approve_updates_gate_project_and_events(db_session, clean_db, captured_events):
    project, gate = await _gate(db_session)

    decided = await HumanGateService(db_session).decide(
        gate.id, approve=True, decided_by="alice", comment="looks good"
    )

    assert decided.status == "approved"
    assert decided.decided_by == "alice"
    assert decided.decided_at is not None
    assert (await ProjectRepository(db_session).get(project.id)).status == "generating_audio"
    assert {"HUMAN_GATE_DECIDED", "SCRIPT_APPROVED"} <= set(captured_events.types())


@pytest.mark.asyncio
async def test_reject_marks_project_rejected(db_session, clean_db, captured_events):
    project, gate = await _gate(db_session)

    decided = await HumanGateService(db_session).decide(
        gate.id, approve=False, decided_by="bob", comment="too long"
    )

    assert decided.status == "rejected"
    assert (await ProjectRepository(db_session).get(project.id)).status == "rejected"
    assert "SCRIPT_APPROVED" not in captured_events.types()


@pytest.mark.asyncio
async def test_second_decision_is_a_409(db_session, clean_db, captured_events):
    _, gate = await _gate(db_session)
    service = HumanGateService(db_session)
    await service.decide(gate.id, approve=True, decided_by="a", comment=None)

    with pytest.raises(APIException) as exc_info:
        await service.decide(gate.id, approve=False, decided_by="b", comment=None)
    assert exc_info.value.status_code == 409


@pytest.mark.asyncio
async def test_decision_survives_unreachable_workflow(db_session, clean_db, captured_events, monkeypatch):
    """A Temporal hiccup after the commit must not turn into a 500."""

    async def broken_client():
        raise ConnectionError("temporal down")

    monkeypatch.setattr("src.temporal.client.get_client", broken_client)
    _, gate = await _gate(db_session, workflow_id="wf-that-does-not-exist")

    decided = await HumanGateService(db_session).decide(
        gate.id, approve=True, decided_by="a", comment=None
    )
    assert decided.status == "approved"
