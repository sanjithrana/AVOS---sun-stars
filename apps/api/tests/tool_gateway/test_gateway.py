import pytest

from agentic_core.tool_gateway.fake_tools import execute_ping
from agentic_core.tool_gateway.gateway import (
    ToolPermissionDeniedError,
    dispatch,
)
from agentic_core.tool_gateway.permissions import AgentRole
from tool_gateway.builtin_tools import ping_tool
from tool_gateway.registry import ToolRegistry
from tool_gateway.schemas import ToolSchema
from tool_gateway.validation import ToolValidationError


def test_authorized_ping_tool_dispatch_succeeds():
    registry = ToolRegistry()
    registry.register(ping_tool())

    result = __import__(
        "asyncio"
    ).run(
        dispatch(
            registry=registry,
            role=AgentRole.DIRECTOR,
            tool_name="ping_tool",
            tool_input={},
            executor=execute_ping,
        )
    )

    assert result.status == "SUCCESS"
    assert result.tool_name == "ping_tool"
    assert result.result == {
        "message": "pong",
    }


def test_unauthorized_tool_is_denied_before_execution():
    registry = ToolRegistry()

    registry.register(
        ToolSchema(
            name="blender_tool",
            description="Restricted test tool",
            schema={},
            permission="blender",
            timeout=5,
        )
    )

    executor_called = False

    async def executor(tool_input: dict) -> dict:
        nonlocal executor_called
        executor_called = True

        return {
            "message": "must not execute",
        }

    async def run():
        with pytest.raises(ToolPermissionDeniedError) as exc_info:
            from agentic_core.tool_gateway.gateway import dispatch

            await dispatch(
                registry=registry,
                role=AgentRole.DIRECTOR,
                tool_name="blender_tool",
                tool_input={},
                executor=executor,
            )

        assert exc_info.value.code == "PERMISSION_DENIED"

    __import__("asyncio").run(run())

    assert executor_called is False


def test_invalid_schema_is_rejected_before_execution():
    registry = ToolRegistry()

    registry.register(
        ToolSchema(
            name="echo_tool",
            description="Schema test tool",
            schema={
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                    },
                },
                "required": ["message"],
                "additionalProperties": False,
            },
            permission="memory",
            timeout=5,
        )
    )

    executor_called = False

    async def executor(tool_input: dict) -> dict:
        nonlocal executor_called
        executor_called = True
        return {}

    async def run():
        with pytest.raises(ToolValidationError) as exc_info:
            from agentic_core.tool_gateway.gateway import dispatch

            await dispatch(
                registry=registry,
                role=AgentRole.DIRECTOR,
                tool_name="echo_tool",
                tool_input={},
                executor=executor,
            )

        assert exc_info.value.code == "SCHEMA_VALIDATION_ERROR"

    __import__("asyncio").run(run())

    assert executor_called is False
