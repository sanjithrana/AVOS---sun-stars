import asyncio
import logging

from temporalio.worker import Worker

from src.config.settings import settings
from src.temporal.activities.audio import generate_audio_activity
from src.temporal.activities.blender import blender_activity
from src.temporal.activities.hello import hello_activity
from src.temporal.activities.lifecycle import finalize_job_activity
from src.temporal.activities.render import (
    generate_shot_visual_activity,
    render_final_video_activity,
    start_visuals_activity,
    visual_concurrency_activity,
)
from src.temporal.activities.qa import qa_repair_activity, qa_settings_activity, shots_review_gate_activity
from src.temporal.activities.research import research_activity
from src.temporal.activities.script import generate_script_activity
from src.temporal.activities.shots import plan_shots_activity
from src.temporal.client import get_client
from src.temporal.workflows.create_video import CreateVideoWorkflow
from src.temporal.workflows.hello import HelloWorkflow

TASK_QUEUE = settings.temporal_task_queue

WORKFLOWS = [HelloWorkflow, CreateVideoWorkflow]
ACTIVITIES = [
    hello_activity,
    research_activity,
    generate_script_activity,
    generate_audio_activity,
    plan_shots_activity,
    blender_activity,
    start_visuals_activity,
    visual_concurrency_activity,
    generate_shot_visual_activity,
    render_final_video_activity,
    finalize_job_activity,
    qa_settings_activity,
    qa_repair_activity,
    shots_review_gate_activity,
]


def build_worker(client, task_queue: str = TASK_QUEUE) -> Worker:
    return Worker(client, task_queue=task_queue, workflows=WORKFLOWS, activities=ACTIVITIES)


async def run_worker() -> None:
    # Temporal can take a while to accept connections after
    # `docker compose up`; retry instead of crash-looping.
    for attempt in range(1, 31):
        try:
            client = await get_client()
            break
        except Exception as exc:  # noqa: BLE001
            logging.warning("Temporal not reachable yet (attempt %s): %s", attempt, exc)
            await asyncio.sleep(2)
    else:
        raise RuntimeError(f"Could not connect to Temporal at {settings.temporal_host}")

    worker = build_worker(client)
    print(f"Temporal worker started on task queue: {TASK_QUEUE}", flush=True)
    await worker.run()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_worker())
