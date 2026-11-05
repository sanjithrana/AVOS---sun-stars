from typing import Any

from temporalio.client import Client, WorkflowHandle

from src.config.settings import settings


_client: Client | None = None


async def connect() -> Client:
    """
    Create and cache a reusable Temporal client connection.
    """
    global _client

    if _client is None:
        _client = await Client.connect(settings.temporal_host)

    return _client


async def get_client() -> Client:
    """
    Return the shared Temporal client.
    """
    return await connect()


async def start_workflow(
    workflow: Any,
    *,
    workflow_id: str,
    task_queue: str,
    args: list[Any] | None = None,
) -> WorkflowHandle:
    """
    Start a workflow using the shared Temporal client.
    """
    client = await get_client()

    return await client.start_workflow(
        workflow,
        *(args or []),
        id=workflow_id,
        task_queue=task_queue,
    )


async def get_result(handle: WorkflowHandle) -> Any:
    """
    Wait for and return the workflow result.
    """
    return await handle.result()
