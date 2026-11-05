from uuid import UUID

from packages.contracts.generation import JobResponse
from src.errors import APIException
from src.repositories.job_repository import JobRepository


class JobService:
    def __init__(self, session) -> None:
        self.repository = JobRepository(session)

    async def get_job(
        self,
        job_id: UUID,
    ) -> JobResponse:
        job = await self.repository.get_by_id(job_id)

        if job is None:
            raise APIException(
                code="not_found",
                message="Job not found.",
                status_code=404,
            )

        return self._to_response(job)

    async def list_for_project(self, project_id: str) -> list[JobResponse]:
        jobs = await self.repository.list_by_project(project_id)
        return [self._to_response(job) for job in jobs]

    @staticmethod
    def _to_response(job) -> JobResponse:
        return JobResponse(
            id=str(job.id),
            project_id=str(job.project_id),
            job_type=job.job_type,
            status=job.status.value,
            workflow_id=job.workflow_id,
            created_at=job.created_at,
            started_at=job.started_at,
            completed_at=job.completed_at,
            output=job.output_payload,
            error_message=job.error_message,
        )
