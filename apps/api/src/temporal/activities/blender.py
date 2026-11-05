from dataclasses import dataclass
from typing import Any

from temporalio import activity

from src.core.events.outbox import commit_and_publish
from src.services.shot_planning_service import ShotPlanningService
from src.temporal.activities._session import activity_session


@dataclass
class BlenderInput:
    project_id: str


@activity.defn
async def blender_activity(inp: BlenderInput) -> list[dict[str, Any]]:
    """Week 3 Day 12: Blender stage for every PLANNED shot (Physics agent,
    run_blender_proxy through the Gateway). Registers physics_proxy +
    depth/normal/canny/mask assets with lineage and marks each shot
    BLENDER_READY. Uses the deterministic MOCK renderer unless
    BLENDER_SERVICE_URL points at a real headless Blender service.
    Idempotent, so Temporal retries are safe."""
    async with activity_session() as session:
        rendered = await ShotPlanningService(session).run_blender_stage(inp.project_id)
        await commit_and_publish(session)
        return rendered
