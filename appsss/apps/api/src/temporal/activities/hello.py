from temporalio import activity

from src.domain.jobs.models import JobStatus
from src.repositories.job_repository import JobRepository
from src.temporal.activities._session import activity_session

HELLO_MESSAGE = "Hello from solunex Temporal"


@activity.defn
async def hello_activity(job_id: str | None = None) -> dict[str, str]:
    """
    Day 4/5 Temporal proof. Kept as an infrastructure smoke test
    (POST /api/v1/internal/temporal/hello); real generation now runs
    CreateVideoWorkflow.
    """
    if job_id:
        async with activity_session() as session:
            repository = JobRepository(session)
            await repository.update_status(job_id, JobStatus.RUNNING)
            await repository.set_result(job_id, {"message": HELLO_MESSAGE})
            await session.commit()

    return {"message": HELLO_MESSAGE}
