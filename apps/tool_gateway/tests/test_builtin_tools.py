from tool_gateway import (
    create_default_registry,
    ping_tool,
)

# ping_tool's permission is "memory" (changed from the Day-3 draft value
# "development") so the Director role - whose AVOS-05 scopes include
# "memory" - can actually dispatch it through the Gateway. No role has a
# "development" scope, so that value made the tool undispatchable.


def test_ping_tool_metadata():
    tool = ping_tool()

    assert tool.name == "ping_tool"
    assert tool.description == "Development test tool"
    assert tool.schema == {}
    assert tool.permission == "memory"
    assert tool.timeout == 5


def test_ping_tool_is_registered():
    registry = create_default_registry()

    assert registry.exists("ping_tool")

    tool = registry.get("ping_tool")

    assert tool.name == "ping_tool"
    assert tool.description == "Development test tool"
    assert tool.schema == {}
    assert tool.permission == "memory"
    assert tool.timeout == 5


def test_default_registry_contains_ping_tool():
    registry = create_default_registry()

    tools = registry.list()

    assert len(tools) == 1
    assert tools[0].name == "ping_tool"
