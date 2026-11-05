from dataclasses import dataclass
from typing import Any

from temporalio import activity
from temporalio.exceptions import ApplicationError

from src.core.events.outbox import commit_and_publish
from src.domain.projects.status import ProjectStatus
from src.services.director_service import DirectorService
from src.services.shot_planning_service import ShotPlanningPrerequisiteError, ShotPlanningService
from src.temporal.activities._session import activity_session


@dataclass
class PlanShotsInput:
    project_id: str
    audio: dict[str, Any]


@activity.defn
async def plan_shots_activity(inp: PlanShotsInput) -> list[dict[str, Any]]:
    """Week 3 Day 11/12: Director builds one ShotSpec per semantic beat
    (create_shot_spec + validate_shot_spec through the Gateway). Pixels
    are not touched; the Blender stage is the next activity."""
    async with activity_session() as session:
        await DirectorService(session)._set_project_status(inp.project_id, ProjectStatus.PLANNING_SHOTS)
        try:
            summaries = await ShotPlanningService(session).plan_shots(
                inp.project_id, audio=inp.audio, run_blender=False
            )
        except ShotPlanningPrerequisiteError as exc:
            raise ApplicationError(str(exc), non_retryable=True) from exc
        await commit_and_publish(session)
        # GPU Scheduler: start loading the project's models on the GPUs now, while the physics stage runs.
        from src.repositories.project_repository import ProjectRepository
        from src.services.fabric_service import prewarm_project

        project = await ProjectRepository(session).get(inp.project_id)
        if project is not None:
            await prewarm_project(project)
        return summaries
