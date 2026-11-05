from uuid import uuid4

import pytest

from agentic_core.tool_gateway.gateway import dispatch
from agentic_core.tool_gateway.permissions import AgentRole
from agentic_core.tool_gateway.tools.submit_video_generation import (
    SubmitVideoGenerationTool,
)
from tool_gateway.registry import ToolRegistry
from tool_gateway.validation import ToolValidationError


class FakeGenerationAPIClient:
    async def generate(
        self,
        *,
        project_id: str,
        generation_type: str,
    ) -> dict:
        return {
            "job_id": str(uuid4()),
            "project_id": project_id,
            "status": "running",
            "workflow_id": "video-generation-test",
        }


@pytest.mark.asyncio
async def test_valid_call_returns_job_id():
    tool = SubmitVideoGenerationTool(
        api_client=FakeGenerationAPIClient()
    )

    result = await tool.execute(
        {
            "project_id": str(uuid4()),
            "generation_type": "video",
        }
    )

    assert result["job_id"]
    assert result["status"] == "running"


@pytest.mark.asyncio
async def test_invalid_schema_returns_schema_validation_error():
    registry = ToolRegistry()
    registry.register(SubmitVideoGenerationTool.schema)

    async def executor(arguments):
        raise AssertionError("must not execute")

    with pytest.raises(ToolValidationError) as exc_info:
        await dispatch(
            registry=registry,
            role=AgentRole.DIRECTOR,
            tool_name="submit_video_generation",
            tool_input={
                "project_id": "bad-id",
            },
            executor=executor,
        )

    assert exc_info.value.code == "SCHEMA_VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_unauthorized_call_returns_permission_denied():
    registry = ToolRegistry()
    registry.register(SubmitVideoGenerationTool.schema)

    async def executor(arguments):
        raise AssertionError("must not execute")

    from agentic_core.tool_gateway.gateway import (
        ToolPermissionDeniedError,
    )

    with pytest.raises(ToolPermissionDeniedError) as exc_info:
        await dispatch(
            registry=registry,
            role=AgentRole.RESEARCH_AGENT,
            tool_name="submit_video_generation",
            tool_input={
                "project_id": str(uuid4()),
                "generation_type": "video",
            },
            executor=executor,
        )

    assert exc_info.value.code == "PERMISSION_DENIED"
