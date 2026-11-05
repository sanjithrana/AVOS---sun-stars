from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from agentic_core.clients.generation_api_client import (
    GenerationAPIClient,
)
from tool_gateway.schemas import ToolSchema


class SubmitVideoGenerationInput(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    project_id: UUID
    generation_type: Literal["video"]


class SubmitVideoGenerationOutput(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    job_id: UUID
    project_id: UUID
    status: str
    workflow_id: str


class SubmitVideoGenerationTool:
    schema = ToolSchema(
        name="submit_video_generation",
        description="Submit a video generation job for a project.",
        schema=SubmitVideoGenerationInput.model_json_schema(),
        permission="planning",
        timeout=30,
    )

    def __init__(
        self,
        api_client: GenerationAPIClient | None = None,
    ) -> None:
        self.api_client = api_client or GenerationAPIClient()

    async def execute(
        self,
        arguments: dict,
    ) -> dict:
        request = SubmitVideoGenerationInput.model_validate(
            arguments
        )

        response = await self.api_client.generate(
            project_id=str(request.project_id),
            generation_type=request.generation_type,
        )

        result = SubmitVideoGenerationOutput.model_validate(
            response
        )

        return result.model_dump(mode="json")


async def execute_submit_video_generation(
    arguments: dict,
) -> dict:
    tool = SubmitVideoGenerationTool()
    return await tool.execute(arguments)
