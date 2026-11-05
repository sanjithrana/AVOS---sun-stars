from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from packages.contracts.event import EventType
from src.core.events.factory import make_event
from src.core.events.outbox import commit_and_publish, queue_event
from src.domain.jobs.models import JobStatus
from src.domain.projects.status import ProjectStatus
from src.repositories.job_repository import JobRepository
from src.repositories.project_repository import ProjectRepository

# Workflow outcome -> (job status, project status)
OUTCOMES: dict[str, tuple[JobStatus, ProjectStatus]] = {
    "completed": (JobStatus.COMPLETED, ProjectStatus.COMPLETE),
    "rejected": (JobStatus.CANCELLED, ProjectStatus.REJECTED),
    "failed": (JobStatus.FAILED, ProjectStatus.FAILED),
}


class JobLifecycleService:
    """Final state of a CreateVideoWorkflow run -> jobs + projects rows."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.jobs = JobRepository(session)
        self.projects = ProjectRepository(session)

    async def finalize(
        self,
        *,
        job_id: str,
        project_id: str,
        outcome: str,
        output: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> str:
        job_status, project_status = OUTCOMES[outcome]

        if outcome == "failed":
            job = await self.jobs.set_error(job_id, error or "Workflow failed.")
            if job is not None and output:
                await self.jobs.set_result(job_id, output, status=JobStatus.FAILED)
        else:
            job = await self.jobs.set_result(job_id, output or {}, status=job_status)

        await self.projects.set_status(project_id, project_status.value)

        final_status = job.status.value if job is not None else job_status.value
        queue_event(
            self.session,
            make_event(
                event_type=EventType.JOB_STATUS_CHANGED,
                project_id=project_id,
                payload={"job_id": job_id, "status": final_status, "error": error},
            ),
        )
        queue_event(
            self.session,
            make_event(
                event_type=EventType.PROJECT_STATUS_CHANGED,
                project_id=project_id,
                payload={"status": project_status.value},
            ),
        )
        await commit_and_publish(self.session)
        return final_status
