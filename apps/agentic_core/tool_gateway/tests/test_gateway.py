import asyncio

import pytest

from agentic_core.tool_gateway.gateway import (
    ToolGatewayError,
    ToolNotFoundError,
    ToolPermissionDeniedError,
    ToolTimeoutError,
    dispatch,
)
from agentic_core.tool_gateway.permissions import AgentRole
from tool_gateway.registry import ToolRegistry
from tool_gateway.schemas import ToolSchema
from tool_gateway.validation import ToolValidationError


def make_memory_tool() -> ToolSchema:
    return ToolSchema(
        name="memory.search",
        description="Test memory search tool",
        schema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                },
            },
            "required": ["query"],
            "additionalProperties": False,
        },
        permission="memory",
        timeout=5,
    )


async def fake_memory_executor(
    tool_input: dict,
) -> dict:
    return {
        "echo": tool_input["query"],
    }


@pytest.mark.asyncio
async def test_gateway_dispatches_authorized_tool():
    registry = ToolRegistry()
    registry.register(make_memory_tool())

    result = await dispatch(
        registry=registry,
        role=AgentRole.DIRECTOR,
        tool_name="memory.search",
        tool_input={
            "query": "flowers",
        },
        executor=fake_memory_executor,
    )

    assert result.tool_name == "memory.search"
    assert result.status == "SUCCESS"
    assert result.result == {
        "echo": "flowers",
    }


@pytest.mark.asyncio
async def test_gateway_rejects_invalid_input_before_dispatch():
    registry = ToolRegistry()
    registry.register(make_memory_tool())

    executor_called = False

    async def executor(tool_input: dict) -> dict:
        nonlocal executor_called
        executor_called = True
        return {}

    with pytest.raises(ToolValidationError):
        await dispatch(
            registry=registry,
            role=AgentRole.DIRECTOR,
            tool_name="memory.search",
            tool_input={},
            executor=executor,
        )

    assert executor_called is False


@pytest.mark.asyncio
async def test_gateway_rejects_unauthorized_tool_before_dispatch():
    registry = ToolRegistry()
    registry.register(make_memory_tool())

    executor_called = False

    async def executor(tool_input: dict) -> dict:
        nonlocal executor_called
        executor_called = True
        return {}

    with pytest.raises(ToolPermissionDeniedError):
        await dispatch(
            registry=registry,
            role=AgentRole.NARRATIVE_AGENT,
            tool_name="memory.search",
            tool_input={
                "query": "flowers",
            },
            executor=executor,
        )

    assert executor_called is False


@pytest.mark.asyncio
async def test_gateway_enforces_timeout():
    tool = ToolSchema(
        name="slow.memory",
        description="Slow test tool",
        schema={},
        permission="memory",
        timeout=1,
    )

    registry = ToolRegistry()
    registry.register(tool)

    async def slow_executor(tool_input: dict) -> str:
        await asyncio.sleep(2)
        return "done"

    with pytest.raises(ToolTimeoutError):
        await dispatch(
            registry=registry,
            role=AgentRole.DIRECTOR,
            tool_name="slow.memory",
            tool_input={},
            executor=slow_executor,
        )


@pytest.mark.asyncio
async def test_gateway_rejects_unknown_tool():
    registry = ToolRegistry()

    async def executor(tool_input: dict) -> dict:
        return {}

    with pytest.raises(ToolNotFoundError):
        await dispatch(
            registry=registry,
            role=AgentRole.DIRECTOR,
            tool_name="does.not.exist",
            tool_input={},
            executor=executor,
        )


@pytest.mark.asyncio
async def test_permission_denied_before_execution():
    registry = ToolRegistry()
    registry.register(make_memory_tool())

    executor_called = False

    async def executor(tool_input: dict) -> dict:
        nonlocal executor_called
        executor_called = True
        return {
            "danger": "this must never happen",
        }

    with pytest.raises(ToolPermissionDeniedError) as exc_info:
        await dispatch(
            registry=registry,
            role=AgentRole.NARRATIVE_AGENT,
            tool_name="memory.search",
            tool_input={
                "query": "flowers",
            },
            executor=executor,
        )

    assert exc_info.value.code == "PERMISSION_DENIED"
    assert exc_info.value.tool_name == "memory.search"
    assert exc_info.value.role == AgentRole.NARRATIVE_AGENT

    # Security invariant:
    # unauthorized tools must NEVER execute.
    assert executor_called is False
