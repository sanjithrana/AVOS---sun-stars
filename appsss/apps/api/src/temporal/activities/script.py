from dataclasses import dataclass, field

from temporalio import activity
from temporalio.exceptions import ApplicationError

from src.services.director_service import (
    DirectorService,
    DirectorStoppedError,
    ScriptRejectedByValidatorError,
)
from src.services.project_service import ProjectNotFoundError
from src.temporal.activities._session import activity_session


@dataclass
class ScriptInput:
    project_id: str
    workflow_id: str
    research_notes: list[str] = field(default_factory=list)


@activity.defn
async def generate_script_activity(inp: ScriptInput) -> str:
    """Thin Temporal wrapper: script generation + opening the approval
    gate (tagged with this workflow's id so approval can signal it).
    Returns the gate id."""
    async with activity_session() as session:
        try:
            gate = await DirectorService(session).write_script(
                inp.project_id,
                research_notes=inp.research_notes,
                workflow_id=inp.workflow_id,
            )
        except (
            ProjectNotFoundError,
            DirectorStoppedError,
            ScriptRejectedByValidatorError,
        ) as exc:
            raise ApplicationError(str(exc), non_retryable=True) from exc
        return str(gate.id)
