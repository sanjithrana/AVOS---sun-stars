from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models.job import JobRecord
from src.domain.jobs.models import Job, JobStatus

TERMINAL_STATUSES = frozenset(
    {JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED}
)
ACTIVE_STATUSES = frozenset({JobStatus.QUEUED, JobStatus.RUNNING})


def _as_uuid(value: UUID | str) -> UUID:
    return value if isinstance(value, UUID) else UUID(str(value))


class JobRepository:
    """
    Persistence boundary for Jobs.

    Application services use the domain Job.
    SQLAlchemy JobRecord remains an internal persistence detail.

    Status changes go through _transition(), which refuses to move a job
    out of a terminal state - so a late "running" write can never
    overwrite "completed" (a real race between the API process and the
    Temporal worker).
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def _to_domain(record: JobRecord) -> Job:
        return Job(
            id=_as_uuid(record.id),
            project_id=UUID(record.project_id),
            job_type=record.job_type,
            status=JobStatus(record.status),
            workflow_id=record.workflow_id,
            temporal_run_id=record.temporal_run_id,
            input_payload=record.input_payload,
            output_payload=record.output_payload,
            error_message=record.error_message,
            created_at=record.created_at,
            started_at=record.started_at,
            completed_at=record.completed_at,
        )

    async def _get_record(self, job_id: UUID | str) -> JobRecord | None:
        result = await self.session.execute(
            select(JobRecord).where(JobRecord.id == _as_uuid(job_id))
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        *,
        project_id: UUID | str,
        job_type: str,
        input_payload: dict | None = None,
    ) -> Job:
        record = JobRecord(
            id=uuid4(),
            project_id=str(project_id),
            job_type=job_type,
            status=JobStatus.QUEUED.value,
            input_payload=input_payload,
            created_at=datetime.now(timezone.utc),
        )

        self.session.add(record)
        await self.session.flush()

        return self._to_domain(record)

    async def get_by_id(self, job_id: UUID | str) -> Job | None:
        record = await self._get_record(job_id)
        return None if record is None else self._to_domain(record)

    async def list_by_project(self, project_id: str, limit: int = 50) -> list[Job]:
        result = await self.session.execute(
            select(JobRecord)
            .where(JobRecord.project_id == str(project_id))
            .order_by(JobRecord.created_at.desc())
            .limit(limit)
        )
        return [self._to_domain(r) for r in result.scalars().all()]

    async def get_active_for_project(
        self,
        project_id: str,
        job_type: str,
    ) -> Job | None:
        result = await self.session.execute(
            select(JobRecord)
            .where(
                JobRecord.project_id == str(project_id),
                JobRecord.job_type == job_type,
                JobRecord.status.in_([s.value for s in ACTIVE_STATUSES]),
            )
            .order_by(JobRecord.created_at.desc())
        )
        record = result.scalars().first()
        return None if record is None else self._to_domain(record)

    async def _transition(
        self,
        record: JobRecord,
        status: JobStatus,
    ) -> bool:
        current = JobStatus(record.status)

        if current in TERMINAL_STATUSES:
            return False

        record.status = status.value
        now = datetime.now(timezone.utc)

        if status == JobStatus.RUNNING and record.started_at is None:
            record.started_at = now

        if status in TERMINAL_STATUSES:
            record.completed_at = now

        return True

    async def update_status(
        self,
        job_id: UUID | str,
        status: JobStatus,
    ) -> Job | None:
        record = await self._get_record(job_id)

        if record is None:
            return None

        await self._transition(record, status)
        await self.session.flush()

        return self._to_domain(record)

    async def set_workflow_metadata(
        self,
        job_id: UUID | str,
        *,
        workflow_id: str | None,
        temporal_run_id: str | None,
    ) -> Job | None:
        record = await self._get_record(job_id)

        if record is None:
            return None

        record.workflow_id = workflow_id
        record.temporal_run_id = temporal_run_id

        await self.session.flush()

        return self._to_domain(record)

    async def set_result(
        self,
        job_id: UUID | str,
        output_payload: dict,
        status: JobStatus = JobStatus.COMPLETED,
    ) -> Job | None:
        record = await self._get_record(job_id)

        if record is None:
            return None

        record.output_payload = output_payload
        await self._transition(record, status)
        await self.session.flush()

        return self._to_domain(record)

    async def set_error(
        self,
        job_id: UUID | str,
        error_message: str,
    ) -> Job | None:
        record = await self._get_record(job_id)

        if record is None:
            return None

        record.error_message = error_message[:4000]
        await self._transition(record, JobStatus.FAILED)
        await self.session.flush()

        return self._to_domain(record)
