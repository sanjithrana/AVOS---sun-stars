from dataclasses import dataclass
from typing import Any

from temporalio import activity
from temporalio.exceptions import ApplicationError

from src.core.events.outbox import commit_and_publish
from src.domain.projects.status import ProjectStatus
from src.services.director_service import DirectorService
from src.services.final_render_service import FinalRenderError, FinalRenderService
from src.services.shot_planning_service import ShotPlanningService
from src.temporal.activities._session import activity_session


@dataclass
class VisualsInput:
    project_id: str


@dataclass
class ShotVisualInput:
    project_id: str
    shot_id: str


@dataclass
class FinalRenderInput:
    project_id: str
    audio: dict[str, Any]


@activity.defn
async def start_visuals_activity(inp: VisualsInput) -> list[str]:
    """Mark the project as generating visuals and return the shot ids
    that still need images/clips, so the workflow can run (and retry)
    one shot at a time."""
    async with activity_session() as session:
        await DirectorService(session)._set_project_status(inp.project_id, ProjectStatus.GENERATING_VISUALS)
        planner = ShotPlanningService(session)
        pending: list[str] = []
        for shot in await planner.shotspecs.shots.list_by_project(inp.project_id):
            current = await planner.shotspecs.shots.current_version(shot)
            if (
                current is not None
                and current.physics_proxy_asset_id is not None
                and current.video_generation_asset_id is None
            ):
                pending.append(shot.id)
        await commit_and_publish(session)
        return pending


@activity.defn
async def visual_concurrency_activity(inp: VisualsInput) -> int:
    """How many shots to generate at once. VISUAL_CONCURRENCY=<n> fixes it; "auto" (default) uses two per online
    GPU worker (one shot's clip overlaps the next shot's pictures), at least 2 and at most 8, or 4 with hosted APIs
    only (fal.ai and the free services take requests in parallel)."""
    import os

    from agentic_core.model_fabric import workers

    raw = (os.getenv("VISUAL_CONCURRENCY") or "auto").strip().lower()
    if raw.isdigit():
        return max(1, min(16, int(raw)))
    online = [s for s in await workers.statuses() if s.online]
    return max(2, min(8, 2 * len(online))) if online else 4


@activity.defn
async def generate_shot_visual_activity(inp: ShotVisualInput) -> dict[str, Any]:
    """Image candidates + (when the project picked a video provider) the
    AI clip for ONE shot, through the Gateway's generate_video_shot.
    Committed per shot, so a failure on shot 5 keeps shots 1-4, and a
    retry is idempotent."""
    async with activity_session() as session:
        planner = ShotPlanningService(session)
        shot = await planner.shotspecs.shots.get(inp.shot_id)
        if shot is None:
            raise ApplicationError(f"Shot {inp.shot_id} not found.", non_retryable=True)
        try:
            results = await planner.run_generation_stage(inp.project_id, only_shot_id=inp.shot_id)
        except ValueError as exc:
            # Misconfiguration (e.g. REPLICATE_API_TOKEN / COMFYUI_URL
            # unset): retrying won't help, say so straight away.
            raise ApplicationError(str(exc), non_retryable=True) from exc
        await commit_and_publish(session)
        return results[0] if results else {"shot_id": inp.shot_id, "skipped": True}


@activity.defn
async def render_final_video_activity(inp: FinalRenderInput) -> dict[str, Any]:
    """Stitch every shot + narration + captions into the final MP4."""
    async with activity_session() as session:
        await DirectorService(session)._set_project_status(inp.project_id, ProjectStatus.RENDERING_VIDEO)
        await commit_and_publish(session)

    async with activity_session() as session:
        try:
            summary = await FinalRenderService(session).render_through_gateway(inp.project_id, inp.audio)
        except FinalRenderError as exc:
            raise ApplicationError(str(exc), non_retryable=True) from exc
        await commit_and_publish(session)
        return summary
