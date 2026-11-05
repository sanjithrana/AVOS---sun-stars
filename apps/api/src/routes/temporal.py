from uuid import uuid4

from fastapi import APIRouter

from src.config.settings import settings
from src.temporal.client import get_client
from src.temporal.workflows.hello import HelloWorkflow

router = APIRouter(
    prefix="/api/v1/internal/temporal",
    tags=["internal-temporal"],
)


@router.post("/hello")
async def temporal_hello() -> dict[str, str]:
    """Infrastructure smoke test: API -> Temporal -> worker -> back."""
    client = await get_client()

    result = await client.execute_workflow(
        HelloWorkflow.run,
        id=f"solunex-temporal-hello-{uuid4()}",
        task_queue=settings.temporal_task_queue,
    )

    # The workflow returns {"message": ...}; return it as-is (it used to
    # be wrapped again as {"message": {"message": ...}}).
    return result
