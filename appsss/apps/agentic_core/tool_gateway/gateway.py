import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from tool_gateway.registry import ToolRegistry
from tool_gateway.validation import (
    ToolValidationError,
    validate_tool_call,
)

from agentic_core.tool_gateway.permissions import (
    AgentRole,
    PermissionResult,
    check_permission,
)


class ToolGatewayError(RuntimeError):
    """Base error for Tool Gateway failures."""


class ToolNotFoundError(ToolGatewayError):
    code = "TOOL_NOT_FOUND"

    def __init__(self, tool_name: str) -> None:
        self.tool_name = tool_name
        super().__init__(f"Tool not found: '{tool_name}'")

    def to_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "message": str(self),
            "tool_name": self.tool_name,
        }


class ToolPermissionDeniedError(ToolGatewayError):
    """
    Raised when an agent is not authorized to invoke a tool.
    """

    code = "PERMISSION_DENIED"

    def __init__(
        self,
        *,
        role: AgentRole,
        tool_name: str,
    ) -> None:
        self.role = role
        self.tool_name = tool_name

        super().__init__(
            f"Permission denied for role "
            f"'{role}' to invoke tool '{tool_name}'."
        )

    def to_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "message": str(self),
            "tool_name": self.tool_name,
        }


class ToolTimeoutError(ToolGatewayError):
    code = "TOOL_TIMEOUT"


class ToolResult:
    def __init__(
        self,
        *,
        tool_name: str,
        status: str,
        result: Any = None,
        error: str | None = None,
    ) -> None:
        self.tool_name = tool_name
        self.status = status
        self.result = result
        self.error = error

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "status": self.status,
            "result": self.result,
            "error": self.error,
        }


ToolExecutor = Callable[
    [dict[str, Any]],
    Any | Awaitable[Any],
]


async def dispatch(
    *,
    registry: ToolRegistry,
    role: AgentRole,
    tool_name: str,
    tool_input: dict[str, Any],
    executor: ToolExecutor,
    constitution_check: Callable[[str, dict[str, Any]], None | Awaitable[None]] | None = None,
) -> ToolResult:

    # 1. Find Tool
    try:
        registry.get(tool_name)
    except KeyError as exc:
        raise ToolNotFoundError(tool_name) from exc

    # 2. Schema Validation
    validated_input = validate_tool_call(
        registry=registry,
        tool_name=tool_name,
        tool_input=tool_input,
    )

    # 3. Permission Validation
    permission = check_permission(
        registry=registry,
        role=role,
        tool_name=tool_name,
    )

    if permission != PermissionResult.AUTHORIZED:
        # IMPORTANT:
        # Return/raise here BEFORE executor is ever called.
        raise ToolPermissionDeniedError(
            role=role,
            tool_name=tool_name,
        )

    # 4. Constitution check (optional; Day 10). Runs after permission,
    # before execution — a hard rule violation blocks dispatch even for
    # an otherwise-authorized caller. May be async (Day 12: the api's
    # physics-before-pixels check reads the shot's Blender state from
    # the database).
    if constitution_check is not None:
        check = constitution_check(tool_name, validated_input)
        if isinstance(check, Awaitable):
            await check

    # 5. Timeout / Execution Policy
    tool = registry.get(tool_name)

    try:
        execution = executor(validated_input)

        if isinstance(execution, Awaitable):
            result = await asyncio.wait_for(
                execution,
                timeout=tool.timeout,
            )
        else:
            result = execution

    except asyncio.TimeoutError as exc:
        raise ToolTimeoutError(
            f"Tool '{tool_name}' exceeded "
            f"timeout of {tool.timeout} seconds."
        ) from exc

    # 6. Result
    return ToolResult(
        tool_name=tool_name,
        status="SUCCESS",
        result=result,
    )
