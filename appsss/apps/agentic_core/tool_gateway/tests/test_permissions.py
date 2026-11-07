from tool_gateway.registry import ToolRegistry
from tool_gateway.schemas import ToolSchema

from agentic_core.tool_gateway.permissions import (
    AgentRole,
    PermissionResult,
    check_permission,
)


def make_tool(
    name: str,
    permission: str,
) -> ToolSchema:
    return ToolSchema(
        name=name,
        description=f"Test {name} tool",
        schema={},
        permission=permission,
        timeout=5,
    )


def test_authorized_role_is_allowed():
    registry = ToolRegistry()

    registry.register(
        make_tool(
            "memory.search",
            "memory",
        )
    )

    result = check_permission(
        registry,
        AgentRole.DIRECTOR,
        "memory.search",
    )

    assert result == PermissionResult.AUTHORIZED


def test_unauthorized_role_is_denied():
    registry = ToolRegistry()

    registry.register(
        make_tool(
            "blender.generate",
            "blender",
        )
    )

    result = check_permission(
        registry,
        AgentRole.DIRECTOR,
        "blender.generate",
    )

    assert result == PermissionResult.PERMISSION_DENIED


def test_unknown_tool_is_denied():
    registry = ToolRegistry()

    result = check_permission(
        registry,
        AgentRole.DIRECTOR,
        "unknown_tool",
    )

    assert result == PermissionResult.PERMISSION_DENIED


def test_learning_agent_can_use_memory():
    registry = ToolRegistry()

    registry.register(
        make_tool(
            "memory.search",
            "memory",
        )
    )

    result = check_permission(
        registry,
        AgentRole.LEARNING_AGENT,
        "memory.search",
    )

    assert result == PermissionResult.AUTHORIZED


def test_research_agent_cannot_use_script_tool():
    registry = ToolRegistry()

    registry.register(
        make_tool(
            "script.generate",
            "script",
        )
    )

    result = check_permission(
        registry,
        AgentRole.RESEARCH_AGENT,
        "script.generate",
    )

    assert result == PermissionResult.PERMISSION_DENIED
