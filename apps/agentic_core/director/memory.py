async def search_memory(query: str, *, limit: int = 5) -> list[str]:
    """
    Search prior project memory relevant to `query`.

    Stub per the Week 2 plan: real pgvector-backed semantic search
    lands in Week 3+. This always returns an empty list today, but the
    Director calls it for real (see director_service.py) so the
    decision_trace entry and call site are already wired for when
    real memory is plugged in.
    """
    return []
