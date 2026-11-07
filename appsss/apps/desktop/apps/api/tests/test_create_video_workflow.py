"""
Day 8 checklist (Temporal + Postgres, real servers):
  "workflow pauses at gate, does not proceed until approval endpoint is called"

Runs CreateVideoWorkflow on a real Temporal server with an in-process
worker on a unique task queue, against the test database.
"""

import asyncio
import uuid

import pytest
from temporalio.client import Client

from src.config.settings import settings
from src.domain.jobs.models import JobStatus
from src.repositories.human_gate_repository import HumanGateRepository
from src.repositories.job_repository import JobRepository
from src.repositories.project_repository import ProjectRepository
from src.services.human_gate_service import HumanGateService
from src.temporal.worker import build_worker
from src.temporal.workflows.create_video import CreateVideoInput, CreateVideoWorkflow
from tests.conftest import TEMPORAL_HOST, requires_temporal

pytestmark = requires_temporal


async def _setup(session):
    project = await ProjectRepository(session).create(
        name="Workflow test", topic="Rainbows", duration_seconds=24, aspect_ratio="9:16"
    )
    job = await JobRepository(session).create(project_id=project.id, job_type="video_generation")
    await session.commit()
    return project, job


async def _wait_for_pending_gate(session, project_id, timeout=15.0):
    repo = HumanGateRepository(session)
    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        session.expire_all()
        gate = await repo.get_pending_for_project(project_id)
        if gate is not None:
            return gate
        await asyncio.sleep(0.2)
    raise AssertionError("gate never opened")


async def _run(session, captured_events, monkeypatch, approve: bool):
    client = await Client.connect(TEMPORAL_HOST)
    # HumanGateService signals via src.temporal.client.get_client().
    monkeypatch.setattr("src.temporal.client.get_client", lambda: _ret(client))

    queue = f"test-{uuid.uuid4()}"
    project, job = await _setup(session)
    project_id = project.id  # plain values: ORM objects expire below
    workflow_id = f"video-generation-{job.id}"

    async with build_worker(client, task_queue=queue):
        handle = await client.start_workflow(
            CreateVideoWorkflow.run,
            CreateVideoInput(job_id=str(job.id), project_id=project_id),
            id=workflow_id,
            task_queue=queue,
        )

        gate = await _wait_for_pending_gate(session, project_id)
        gate_id = gate.id
        assert gate.workflow_id == workflow_id

        # --- paused: give it real time to (wrongly) proceed
        await asyncio.sleep(2)
        progress = await handle.query(CreateVideoWorkflow.progress)
        assert progress.stage == "awaiting_approval"
        session.expire_all()
        assert (await JobRepository(session).get_by_id(job.id)).status == JobStatus.RUNNING

        # --- human decides through the real service (same path as the API)
        await HumanGateService(session).decide(
            gate_id, approve=approve, decided_by="tester", comment=None
        )

        result = await asyncio.wait_for(handle.result(), timeout=180)

    session.expire_all()
    final_job = await JobRepository(session).get_by_id(job.id)
    final_project = await ProjectRepository(session).get(project_id)
    return result, final_job, final_project


async def _ret(value):
    return value


@pytest.mark.asyncio
async def test_workflow_pauses_at_gate_and_resumes_on_approval(
    db_session, clean_db, captured_events, monkeypatch
):
    result, job, project = await _run(db_session, captured_events, monkeypatch, approve=True)

    assert result["status"] == "COMPLETED"
    audio = result["audio"]
    assert audio["duration_seconds"] > 0
    assert audio["word_count"] > 0
    assert len(audio["sentences"]) >= 1
    assert len(audio["beats"]) == len(audio["sentences"])

    assert job.status == JobStatus.COMPLETED
    assert job.output_payload["audio"]["asset_id"] == audio["asset_id"]
    assert project.status == "complete"

    # Week 3: one ShotSpec per beat, each through the Blender stage
    # (physics before pixels) before the job completes.
    from src.services.shotspec_service import ShotSpecService

    assert len(result["shots"]) == len(audio["beats"])
    assert len(result["physics"]) == len(result["shots"])
    assert all(p["renderer"] == "MOCK" for p in result["physics"])
    shots = await ShotSpecService(db_session).list_shots(project.id)
    assert all(s.spec.physics_proxy_asset_id for s in shots)
    # Visuals stage: every shot generated (physics first, then pixels).
    # the QA agent checked every shot inside the workflow (v12): all mock frames pass, nothing needed repair
    assert [s.status for s in shots] == ["PASSED"] * len(audio["beats"])
    assert [q["status"] for q in result["qa"]] == ["PASS"] * len(audio["beats"])
    assert all(q["repairs"] == 0 for q in result["qa"])
    assert len(result["visuals"]) == len(result["shots"])

    # Final render: one playable MP4 covering the whole narration.
    final = result["final_video"]
    assert job.output_payload["final_video"]["asset_id"] == final["asset_id"]
    assert len(final["shot_sources"]) == len(result["shots"])
    assert final["duration_seconds"] >= audio["duration_seconds"]
    from uuid import UUID

    from src.core.assets.registry import AssetRegistry

    asset = await AssetRegistry(db_session).get(UUID(final["asset_id"]))
    assert asset.asset_type == "final_video" and asset.storage_path.endswith(".mp4")

    statuses = [e.payload.get("status") for e in captured_events.events
                if e.event_type.value == "PROJECT_STATUS_CHANGED"]
    assert "planning_shots" in statuses
    assert statuses.index("generating_visuals") < statuses.index("rendering_video")
    assert "VIDEO_ASSEMBLED" in captured_events.types()


@pytest.mark.asyncio
async def test_rejection_stops_workflow_without_audio(
    db_session, clean_db, captured_events, monkeypatch
):
    result, job, project = await _run(db_session, captured_events, monkeypatch, approve=False)

    assert result["status"] == "REJECTED"
    assert "audio" not in result
    assert job.status == JobStatus.CANCELLED
    assert project.status == "rejected"


def test_task_queue_setting_is_used_by_worker_module():
    from src.temporal import worker

    assert worker.TASK_QUEUE == settings.temporal_task_queue


@pytest.mark.asyncio
async def test_shots_review_gate_pauses_before_the_final_render(db_session, clean_db, captured_events, monkeypatch):
    """generation limits → review_shots: after QA the workflow opens a second gate and renders only on approval."""
    client = await Client.connect(TEMPORAL_HOST)
    monkeypatch.setattr("src.temporal.client.get_client", lambda: _ret(client))
    queue = f"test-{uuid.uuid4()}"
    project = await ProjectRepository(db_session).create(
        name="Review test", topic="Rainbows", duration_seconds=12, aspect_ratio="9:16",
        generation_policy={"review_shots": True})
    job = await JobRepository(db_session).create(project_id=project.id, job_type="video_generation")
    await db_session.commit()
    project_id, workflow_id = project.id, f"video-generation-{job.id}"
    async with build_worker(client, task_queue=queue):
        handle = await client.start_workflow(CreateVideoWorkflow.run, CreateVideoInput(job_id=str(job.id), project_id=project_id),
                                             id=workflow_id, task_queue=queue)
        script_gate = await _wait_for_pending_gate(db_session, project_id)
        script_gate_id = script_gate.id
        await HumanGateService(db_session).decide(script_gate_id, approve=True, decided_by="tester", comment=None)
        review = None
        for _ in range(300):
            db_session.expire_all()
            review = await HumanGateRepository(db_session).get_pending_for_project(project_id)
            if review is not None and review.id != script_gate_id:
                break
            await asyncio.sleep(0.2)
        assert review is not None and review.gate_type == "final_approval"
        review_id, payload = review.id, dict(review.payload)
        assert payload["kind"] == "shots_review" and payload["passed"] == payload["total"] > 0
        progress = await handle.query(CreateVideoWorkflow.progress)
        assert progress.stage == "awaiting_shots_review"
        db_session.expire_all()
        assert (await ProjectRepository(db_session).get(project_id)).status == "awaiting_review"
        await HumanGateService(db_session).decide(review_id, approve=True, decided_by="tester", comment=None)
        result = await asyncio.wait_for(handle.result(), timeout=180)
    assert result["status"] == "COMPLETED" and result["final_video"]["asset_id"]
    assert all(q["status"] == "PASS" for q in result["qa"])
