from tool_gateway.schemas import ToolSchema


def ping_tool() -> ToolSchema:
    """
    Development-only fake tool declaration.

    The implementation is deliberately trivial.
    Its purpose is to prove the Gateway dispatch path.
    """
    return ToolSchema(
        name="ping_tool",
        description="Development test tool",
        schema={},
        permission="memory",
        timeout=5,
    )
