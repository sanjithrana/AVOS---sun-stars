from dataclasses import dataclass, field
from typing import Any

from temporalio import activity

from src.services.job_lifecycle_service import JobLifecycleService
from src.temporal.activities._session import activity_session


@dataclass
class FinalizeInput:
    job_id: str
    project_id: str
    outcome: str  # completed | rejected | failed
    output: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@activity.defn
async def finalize_job_activity(inp: FinalizeInput) -> str:
    async with activity_session() as session:
        return await JobLifecycleService(session).finalize(
            job_id=inp.job_id,
            project_id=inp.project_id,
            outcome=inp.outcome,
            output=inp.output,
            error=inp.error,
        )
