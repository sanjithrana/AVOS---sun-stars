from tool_gateway.builtin_tools import ping_tool
from tool_gateway.registry import ToolRegistry


def test_ping_tool_is_registered():
    registry = ToolRegistry()

    tool = ping_tool()

    registry.register(tool)

    assert registry.exists("ping_tool")
    assert registry.get("ping_tool") == tool


def test_ping_tool_metadata():
    tool = ping_tool()

    assert tool.name == "ping_tool"
    assert tool.description == "Development test tool"
    assert tool.schema == {}
    assert tool.permission == "memory"
    assert tool.timeout == 5
