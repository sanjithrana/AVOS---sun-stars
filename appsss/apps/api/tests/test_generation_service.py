"""POST /projects/{id}/generate failure paths and idempotency."""

import pytest

from packages.contracts.generation import GenerateRequest
from src.domain.jobs.models import JobStatus
from src.errors import APIException
from src.repositories.job_repository import JobRepository
from src.repositories.project_repository import ProjectRepository
from src.services.generation_service import GenerationService
from tests.conftest import requires_db

pytestmark = requires_db

VIDEO = GenerateRequest(generation_type="video")


class _Handle:
    def __init__(self, workflow_id: str) -> None:
        self.id = workflow_id
        self.result_run_id = "run-1"


async def _project(session):
    project = await ProjectRepository(session).create(
        name="p", topic="t", duration_seconds=10, aspect_ratio="9:16"
    )
    await session.commit()
    return project


@pytest.mark.asyncio
async def test_generate_commits_job_before_starting_workflow(db_session, clean_db, captured_events, monkeypatch):
    project = await _project(db_session)
    seen = {}

    async def fake_start(self, *, job_id, project_id):
        # The job must already be committed/visible when the worker could run.
        seen["job"] = await JobRepository(db_session).get_by_id(job_id)
        return _Handle(f"video-generation-{job_id}")

    monkeypatch.setattr(GenerationService, "_start_workflow", fake_start)

    response = await GenerationService(db_session).generate(project_id=project.id, request=VIDEO)

    assert seen["job"] is not None and seen["job"].status == JobStatus.QUEUED
    assert response.status == "running"
    assert response.workflow_id == f"video-generation-{response.job_id}"
    assert "JOB_STATUS_CHANGED" in captured_events.types()


@pytest.mark.asyncio
async def test_generate_is_idempotent_while_a_job_is_active(db_session, clean_db, captured_events, monkeypatch):
    project = await _project(db_session)
    starts = []

    async def fake_start(self, *, job_id, project_id):
        starts.append(job_id)
        return _Handle(f"video-generation-{job_id}")

    monkeypatch.setattr(GenerationService, "_start_workflow", fake_start)

    first = await GenerationService(db_session).generate(project_id=project.id, request=VIDEO)
    second = await GenerationService(db_session).generate(project_id=project.id, request=VIDEO)

    assert first.job_id == second.job_id
    assert len(starts) == 1


@pytest.mark.asyncio
async def test_temporal_unreachable_fails_job_and_project_cleanly(db_session, clean_db, captured_events, monkeypatch):
    project = await _project(db_session)

    async def broken_start(self, *, job_id, project_id):
        raise ConnectionError("temporal down")

    monkeypatch.setattr(GenerationService, "_start_workflow", broken_start)

    with pytest.raises(APIException) as exc_info:
        await GenerationService(db_session).generate(project_id=project.id, request=VIDEO)
    assert exc_info.value.status_code == 500

    jobs = await JobRepository(db_session).list_by_project(project.id)
    assert jobs[0].status == JobStatus.FAILED
    assert "temporal down" in jobs[0].error_message
    assert (await ProjectRepository(db_session).get(project.id)).status == "failed"


@pytest.mark.asyncio
async def test_unknown_project_is_404_and_bad_type_is_422(db_session, clean_db):
    service = GenerationService(db_session)

    with pytest.raises(APIException) as not_found:
        await service.generate(project_id="00000000-0000-0000-0000-000000000000", request=VIDEO)
    assert not_found.value.status_code == 404

    project = await _project(db_session)
    with pytest.raises(APIException) as bad_type:
        await service.generate(project_id=project.id, request=GenerateRequest(generation_type="image"))
    assert bad_type.value.status_code == 422
