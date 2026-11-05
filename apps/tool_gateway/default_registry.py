from tool_gateway.builtin_tools import ping_tool
from tool_gateway.registry import ToolRegistry


def create_default_registry() -> ToolRegistry:
    """
    Create the initial Tool Gateway registry.

    Only development-safe fake tools are registered here.
    """
    registry = ToolRegistry()

    registry.register(ping_tool())

    return registry
