import logging
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from packages.contracts.event import EventType
from packages.contracts.generation import GenerateRequest, GenerateResponse
from src.config.settings import settings
from src.core.events.factory import make_event
from src.core.events.outbox import commit_and_publish, discard_queued_events, queue_event
from src.domain.jobs.models import Job, JobStatus
from src.domain.projects.status import ProjectStatus
from src.errors import APIException
from src.repositories.job_repository import JobRepository
from src.repositories.project_repository import ProjectRepository
from src.services.project_service import ProjectNotFoundError, ProjectService

logger = logging.getLogger(__name__)

CREATE_VIDEO_JOB_TYPE = "video_generation"


def workflow_id_for(job_id: UUID | str) -> str:
    return f"video-generation-{job_id}"


class GenerationService:
    """
    POST /projects/{id}/generate.

    Starts the real CreateVideoWorkflow (Day 8 replaced HelloWorkflow):
        research -> script -> [human gate] -> audio

    Ordering fix: the Job row is committed *before* the workflow starts.
    Previously it was only flushed, so the worker's activity could run
    before the API committed, find no job, and leave it RUNNING forever.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.project_service = ProjectService(session)
        self.jobs = JobRepository(session)
        self.projects = ProjectRepository(session)

    @staticmethod
    def _response(job: Job, status: JobStatus | None = None) -> GenerateResponse:
        return GenerateResponse(
            job_id=str(job.id),
            project_id=str(job.project_id),
            status=(status or job.status).value,
            workflow_id=job.workflow_id or workflow_id_for(job.id),
        )

    async def generate(
        self,
        *,
        project_id: UUID | str,
        request: GenerateRequest,
    ) -> GenerateResponse:
        project_id = str(project_id)

        try:
            await self.project_service.get_project(project_id)
        except ProjectNotFoundError as exc:
            raise APIException(
                code="not_found",
                message="Project not found.",
                project_id=project_id,
                status_code=404,
            ) from exc

        if request.generation_type != "video":
            raise APIException(
                code="validation_error",
                message="Unsupported generation_type. Expected 'video'.",
                project_id=project_id,
                status_code=422,
            )

        # Idempotent: a double-click returns the job already in flight
        # instead of starting a second parallel pipeline.
        active = await self.jobs.get_active_for_project(project_id, CREATE_VIDEO_JOB_TYPE)
        if active is not None:
            return self._response(active)

        job = await self.jobs.create(
            project_id=project_id,
            job_type=CREATE_VIDEO_JOB_TYPE,
            input_payload={"generation_type": request.generation_type, "project_id": project_id},
        )
        workflow_id = workflow_id_for(job.id)
        await self.jobs.set_workflow_metadata(job.id, workflow_id=workflow_id, temporal_run_id=None)
        await self.projects.set_status(project_id, ProjectStatus.PLANNING.value)
        await self.session.commit()  # visible to the worker before it can run

        try:
            handle = await self._start_workflow(job_id=str(job.id), project_id=project_id)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to start CreateVideoWorkflow for job %s", job.id)
            discard_queued_events(self.session)
            await self.jobs.set_error(job.id, f"Failed to start workflow: {exc}")
            await self.projects.set_status(project_id, ProjectStatus.FAILED.value)
            await self.session.commit()
            raise APIException(
                code="internal_error",
                message="Failed to start generation workflow.",
                project_id=project_id,
                status_code=500,
            ) from exc

        await self.jobs.set_workflow_metadata(
            job.id, workflow_id=handle.id, temporal_run_id=handle.result_run_id
        )
        # Guarded transition: never overwrites a status the worker
        # already moved the job to.
        updated = await self.jobs.update_status(job.id, JobStatus.RUNNING)
        queue_event(
            self.session,
            make_event(
                event_type=EventType.JOB_STATUS_CHANGED,
                project_id=project_id,
                payload={"job_id": str(job.id), "status": updated.status.value},
            ),
        )
        await commit_and_publish(self.session)

        return self._response(updated)

    async def _start_workflow(self, *, job_id: str, project_id: str) -> Any:
        from src.temporal.client import get_client
        from src.temporal.workflows.create_video import CreateVideoInput, CreateVideoWorkflow

        client = await get_client()
        return await client.start_workflow(
            CreateVideoWorkflow.run,
            CreateVideoInput(job_id=job_id, project_id=project_id),
            id=workflow_id_for(job_id),
            task_queue=settings.temporal_task_queue,
        )
