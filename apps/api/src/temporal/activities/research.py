from dataclasses import dataclass

from temporalio import activity
from temporalio.exceptions import ApplicationError

from src.services.director_service import DirectorService, DirectorStoppedError
from src.services.project_service import ProjectNotFoundError
from src.temporal.activities._session import activity_session


@dataclass
class ResearchInput:
    job_id: str
    project_id: str


@activity.defn
async def research_activity(inp: ResearchInput) -> list[str]:
    """Thin Temporal wrapper: memory lookup + research via the Director."""
    async with activity_session() as session:
        try:
            return await DirectorService(session).research(inp.project_id, job_id=inp.job_id)
        except (ProjectNotFoundError, DirectorStoppedError) as exc:
            raise ApplicationError(str(exc), non_retryable=True) from exc
