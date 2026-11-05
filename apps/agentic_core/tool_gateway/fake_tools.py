async def execute_ping(
    tool_input: dict,
) -> dict:
    """
    Fake tool implementation.

    No backend work is performed.
    """
    return {
        "message": "pong",
    }
