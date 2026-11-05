from collections.abc import Awaitable, Callable
from typing import Any

from agentic_core.tool_gateway.tools.submit_video_generation import (
    execute_submit_video_generation,
)


ToolExecutor = Callable[
    [dict[str, Any]],
    Any | Awaitable[Any],
]


def get_executor(tool_name: str) -> ToolExecutor:
    executors: dict[str, ToolExecutor] = {
        "submit_video_generation": execute_submit_video_generation,
    }

    try:
        return executors[tool_name]
    except KeyError as exc:
        raise ValueError(
            f"No executor registered for tool '{tool_name}'"
        ) from exc
