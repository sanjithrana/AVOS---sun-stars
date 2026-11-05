import pytest

from agentic_core.tool_gateway.dispatchers import get_executor
from agentic_core.tool_gateway.gateway import dispatch
from agentic_core.tool_gateway.permissions import AgentRole
from tool_gateway.registry import ToolRegistry
from agentic_core.tool_gateway.tools.submit_video_generation import (
    SubmitVideoGenerationTool,
)


class FakeGenerationAPIClient:
    async def generate(
        self,
        *,
        project_id: str,
        generation_type: str,
    ) -> dict:
        return {
            "job_id": "22222222-2222-2222-2222-222222222222",
            "project_id": project_id,
            "status": "running",
            "workflow_id": "video-generation-test-job-001",
        }


@pytest.mark.asyncio
async def test_submit_video_generation_tool_calls_generation_api():
    tool = SubmitVideoGenerationTool(
        api_client=FakeGenerationAPIClient()
    )

    result = await tool.execute(
        {
            "project_id": "11111111-1111-1111-1111-111111111111",
            "generation_type": "video",
        }
    )

    assert result == {
        "job_id": "22222222-2222-2222-2222-222222222222",
        "project_id": "11111111-1111-1111-1111-111111111111",
        "status": "running",
        "workflow_id": "video-generation-test-job-001",
    }


@pytest.mark.asyncio
async def test_agent_can_dispatch_submit_video_generation():
    registry = ToolRegistry()
    registry.register(SubmitVideoGenerationTool.schema)

    async def fake_executor(arguments: dict) -> dict:
        return {
            "job_id": "job-123",
            "project_id": arguments["project_id"],
            "status": "running",
        }

    result = await dispatch(
        registry=registry,
        role=AgentRole.DIRECTOR,
        tool_name="submit_video_generation",
        tool_input={
            "project_id": "project-123",
            "generation_type": "video",
        },
        executor=fake_executor,
    )

    assert result.status == "SUCCESS"
    assert result.tool_name == "submit_video_generation"
    assert result.result["project_id"] == "project-123"


def test_submit_video_generation_executor_is_registered():
    executor = get_executor("submit_video_generation")

    assert executor is not None


@pytest.mark.asyncio
async def test_submit_video_generation_rejects_wrong_generation_type():
    registry = ToolRegistry()
    registry.register(SubmitVideoGenerationTool.schema)

    async def executor(arguments: dict) -> dict:
        raise AssertionError("executor must not run")

    from tool_gateway.validation import ToolValidationError

    with pytest.raises(ToolValidationError) as exc_info:
        await dispatch(
            registry=registry,
            role=AgentRole.DIRECTOR,
            tool_name="submit_video_generation",
            tool_input={
                "project_id": "project-123",
                "generation_type": "image",
            },
            executor=executor,
        )

    assert exc_info.value.code == "SCHEMA_VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_submit_video_generation_rejects_extra_argument():
    registry = ToolRegistry()
    registry.register(SubmitVideoGenerationTool.schema)

    async def executor(arguments: dict) -> dict:
        raise AssertionError("executor must not run")

    from tool_gateway.validation import ToolValidationError

    with pytest.raises(ToolValidationError):
        await dispatch(
            registry=registry,
            role=AgentRole.DIRECTOR,
            tool_name="submit_video_generation",
            tool_input={
                "project_id": "project-123",
                "generation_type": "video",
                "unexpected": "value",
            },
            executor=executor,
        )
