from pydantic import BaseModel, ConfigDict, Field

from agentic_core.director.memory import search_memory
from tool_gateway.schemas import ToolSchema


class SearchMemoryInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1)
    limit: int = Field(default=5, ge=1, le=50)


class SearchMemoryTool:
    """
    Tool Gateway tool: search prior project memory (AVOS-04 section 6).

    Dispatched by the Director before script generation so the lookup
    appears in the audit trail / decision trace (Day 9). The underlying
    search is still the Week 2 stub (always empty); real pgvector search
    replaces agentic_core.director.memory.search_memory in Week 3+.
    """

    schema = ToolSchema(
        name="search_memory",
        description="Search prior project memory relevant to a query.",
        schema=SearchMemoryInput.model_json_schema(),
        permission="memory",
        timeout=10,
    )

    async def execute(self, arguments: dict) -> dict:
        request = SearchMemoryInput.model_validate(arguments)
        results = await search_memory(request.query, limit=request.limit)
        return {"query": request.query, "results": results, "model": "memory-stub"}
