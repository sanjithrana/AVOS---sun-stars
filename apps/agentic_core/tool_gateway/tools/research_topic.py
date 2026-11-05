from pydantic import BaseModel, ConfigDict

from agentic_core.models.llm.base import LLMProvider
from agentic_core.models.llm.factory import get_llm_provider
from tool_gateway.schemas import ToolSchema

SYSTEM_PROMPT = (
    "You are the Research agent in an automated video production system. "
    "Given a topic, provide 3-5 short, factual, kid-appropriate bullet "
    "points that a scriptwriter could use. Respond with plain text only, "
    "one bullet per line, no preamble."
)


class ResearchTopicInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    topic: str


class ResearchTopicOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    topic: str
    notes: list[str]
    model: str


class ResearchTopicTool:
    """Tool Gateway tool: gathers research notes for a topic via the LLM."""

    schema = ToolSchema(
        name="research_topic",
        description="Research a topic and return factual notes for scriptwriting.",
        schema=ResearchTopicInput.model_json_schema(),
        permission="research",
        timeout=30,
    )

    def __init__(self, llm: LLMProvider | None = None) -> None:
        self.llm = llm or get_llm_provider()

    async def execute(self, arguments: dict) -> dict:
        request = ResearchTopicInput.model_validate(arguments)

        raw = await self.llm.complete(
            f"TASK: research\nTOPIC: {request.topic}",
            system=SYSTEM_PROMPT,
        )

        notes = [line.strip("- ").strip() for line in raw.splitlines() if line.strip()]

        result = ResearchTopicOutput(
            topic=request.topic,
            notes=notes or [f"General background on {request.topic}."],
            model=self.llm.name,
        )

        return result.model_dump(mode="json")
