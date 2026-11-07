from pydantic import BaseModel, ConfigDict, Field

from agentic_core.models.llm.base import LLMProvider
from agentic_core.pipelines.script.generator import generate_script
from tool_gateway.schemas import ToolSchema


class GenerateScriptInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: str
    topic: str
    duration_seconds: int = Field(gt=0)
    aspect_ratio: str = "9:16"
    research_notes: list[str] = Field(default_factory=list)
    # Week 4: the project's style preset's writing instructions.
    style_guidance: str = ""


class GenerateScriptTool:
    """Tool Gateway tool: generates a full Script via the LLM pipeline."""

    schema = ToolSchema(
        name="generate_script",
        description="Generate a scene-by-scene script for a project.",
        schema=GenerateScriptInput.model_json_schema(),
        permission="script",
        timeout=60,
    )

    def __init__(self, llm: LLMProvider | None = None) -> None:
        self.llm = llm

    async def execute(self, arguments: dict) -> dict:
        request = GenerateScriptInput.model_validate(arguments)

        # Research notes go to the prompt as their own section. (They used
        # to be appended to the topic string, which leaked the whole
        # research blob into every line of narration.)
        script = await generate_script(
            project_id=request.project_id,
            topic=request.topic,
            research_notes=request.research_notes,
            duration_seconds=request.duration_seconds,
            aspect_ratio=request.aspect_ratio,
            llm=self.llm,
            style_guidance=request.style_guidance,
        )

        return script.model_dump(mode="json")
