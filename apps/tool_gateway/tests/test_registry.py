
import pytest

from tool_gateway.registry import ToolRegistry
from tool_gateway.schemas import ToolSchema
from tool_gateway.validation import (
    validate_registry,
    validate_tool,
)


def make_ping_tool() -> ToolSchema:
    return ToolSchema(
        name="ping_tool",
        description="Simple connectivity test tool.",
        schema={},
        permission="development",
        timeout=5,
    )


def test_register_and_get():
    registry = ToolRegistry()

    tool = make_ping_tool()

    registry.register(tool)

    assert registry.get("ping_tool") == tool


def test_list_returns_registered_tools():
    registry = ToolRegistry()

    ping_tool = make_ping_tool()

    registry.register(ping_tool)

    tools = registry.list()

    assert len(tools) == 1
    assert tools[0] == ping_tool


def test_exists_returns_false_for_unknown_tool():
    registry = ToolRegistry()

    assert registry.exists("unknown_tool") is False


def test_get_unknown_tool_raises_key_error():
    registry = ToolRegistry()

    with pytest.raises(KeyError):
        registry.get("unknown_tool")


def test_duplicate_registration_is_rejected():
    registry = ToolRegistry()

    tool = make_ping_tool()

    registry.register(tool)

    with pytest.raises(ValueError):
        registry.register(tool)


def test_registry_can_be_initialized_with_tools():
    tool = make_ping_tool()

    registry = ToolRegistry([tool])

    assert registry.exists("ping_tool")
    assert registry.get("ping_tool") == tool


def test_validate_tool():
    tool = make_ping_tool()

    validated_tool = validate_tool(tool)

    assert validated_tool == tool


def test_validate_registry():
    registry = ToolRegistry()

    registry.register(make_ping_tool())

    # Validation succeeds without raising an exception.
    validate_registry(registry)

