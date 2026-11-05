from uuid import uuid4

import pytest

from agentic_core.graph import build_director_graph
from agentic_core.tool_gateway.gateway import (
    ToolNotFoundError,
    ToolPermissionDeniedError,
)
from agentic_core.tool_gateway.permissions import AgentRole


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


@pytest.fixture
def patched_tool(monkeypatch):
    from agentic_core.tool_gateway.tools.submit_video_generation import (
        SubmitVideoGenerationTool,
    )

    def factory(*args, **kwargs):
        return SubmitVideoGenerationTool(
            api_client=FakeGenerationAPIClient()
        )

    monkeypatch.setattr(
        "agentic_core.graph.SubmitVideoGenerationTool",
        factory,
    )


@pytest.mark.asyncio
async def test_valid_generate_intent_returns_agent_result(patched_tool):
    graph = build_director_graph()

    project_id = str(uuid4())

    result = await graph.ainvoke(
        {
            "intent": "generate project",
            "role": AgentRole.DIRECTOR,
            "arguments": {
                "project_id": project_id,
                "generation_type": "video",
            },
        }
    )

    assert result["tool_name"] == "submit_video_generation"
    assert result["agent_result"]["success"] is True
    assert result["agent_result"]["project_id"] == project_id
    assert result["agent_result"]["job_id"]


@pytest.mark.asyncio
async def test_invalid_schema_is_rejected(patched_tool):
    graph = build_director_graph()

    with pytest.raises(Exception) as exc_info:
        await graph.ainvoke(
            {
                "intent": "generate project",
                "role": AgentRole.DIRECTOR,
                "arguments": {
                    "project_id": "bad-id",
                },
            }
        )

    assert getattr(exc_info.value, "code", None) == (
        "SCHEMA_VALIDATION_ERROR"
    )


@pytest.mark.asyncio
async def test_unauthorized_tool_is_rejected(patched_tool):
    graph = build_director_graph()

    with pytest.raises(ToolPermissionDeniedError) as exc_info:
        await graph.ainvoke(
            {
                "intent": "generate project",
                "role": AgentRole.RESEARCH_AGENT,
                "arguments": {
                    "project_id": str(uuid4()),
                    "generation_type": "video",
                },
            }
        )

    assert exc_info.value.code == "PERMISSION_DENIED"


@pytest.mark.asyncio
async def test_unknown_tool_is_rejected():
    from agentic_core.tool_gateway.gateway import dispatch
    from agentic_core.tool_gateway.permissions import AgentRole
    from tool_gateway.registry import ToolRegistry

    async def executor(arguments):
        raise AssertionError("executor must not execute")

    with pytest.raises(ToolNotFoundError) as exc_info:
        await dispatch(
            registry=ToolRegistry(),
            role=AgentRole.DIRECTOR,
            tool_name="does_not_exist",
            tool_input={},
            executor=executor,
        )

    assert exc_info.value.code == "TOOL_NOT_FOUND"
