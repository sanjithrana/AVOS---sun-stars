import pytest

from agentic_core.tool_gateway.gateway import (
    ToolPermissionDeniedError,
    ToolTimeoutError,
    dispatch,
)
from agentic_core.tool_gateway.permissions import AgentRole
from tool_gateway.registry import ToolRegistry
from tool_gateway.schemas import ToolSchema
from tool_gateway.validation import ToolValidationError


def make_registry() -> ToolRegistry:
    registry = ToolRegistry()

    registry.register(
        ToolSchema(
            name="memory.search",
            description="Registry integration test tool",
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
    )

    return registry


@pytest.mark.asyncio
async def test_gateway_uses_registry_metadata():
    registry = make_registry()

    async def executor(tool_input: dict) -> dict:
        return {
            "received": tool_input["query"],
        }

    result = await dispatch(
        registry=registry,
        role=AgentRole.DIRECTOR,
        tool_name="memory.search",
        tool_input={
            "query": "flowers",
        },
        executor=executor,
    )

    assert result.tool_name == "memory.search"
    assert result.status == "SUCCESS"
    assert result.result == {
        "received": "flowers",
    }


@pytest.mark.asyncio
async def test_gateway_uses_registry_schema():
    registry = make_registry()

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
async def test_gateway_uses_registry_permission():
    registry = make_registry()

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
async def test_gateway_uses_registry_timeout():
    registry = ToolRegistry()

    registry.register(
        ToolSchema(
            name="slow.memory",
            description="Registry timeout test tool",
            schema={},
            permission="memory",
            timeout=1,
        )
    )

    async def slow_executor(tool_input: dict) -> str:
        import asyncio

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
