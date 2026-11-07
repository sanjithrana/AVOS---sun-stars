import pytest

from agentic_core.tool_gateway.constitution import (
    ConstitutionViolationError,
    check_constitution,
)
from agentic_core.tool_gateway.gateway import dispatch
from agentic_core.tool_gateway.permissions import AgentRole
from tool_gateway.registry import ToolRegistry
from tool_gateway.schemas import ToolSchema


def _video_shot_tool() -> ToolSchema:
    return ToolSchema(
        name="generate_video_shot",
        description="Render a shot.",
        schema={},
        permission="comfyui",
        timeout=30,
    )


def test_check_constitution_blocks_shot_without_physics_proxy():
    with pytest.raises(ConstitutionViolationError):
        check_constitution("generate_video_shot", {})


def test_check_constitution_allows_shot_with_physics_proxy():
    check_constitution(
        "generate_video_shot",
        {"physics_proxy_asset_id": "asset-123"},
    )  # should not raise


def test_check_constitution_ignores_unrelated_tools():
    check_constitution("research_topic", {})  # should not raise


@pytest.mark.asyncio
async def test_dispatch_without_constitution_check_is_unaffected():
    """Backward compatibility: existing callers that don't pass
    constitution_check keep working exactly as before."""
    registry = ToolRegistry()
    registry.register(_video_shot_tool())

    async def executor(tool_input: dict) -> dict:
        return {"ok": True}

    result = await dispatch(
        registry=registry,
        role=AgentRole.VIDEO_AGENT,
        tool_name="generate_video_shot",
        tool_input={},
        executor=executor,
    )
    assert result.status == "SUCCESS"


@pytest.mark.asyncio
async def test_dispatch_with_constitution_check_blocks_ungrounded_shot():
    registry = ToolRegistry()
    registry.register(_video_shot_tool())

    async def executor(tool_input: dict) -> dict:
        raise AssertionError("executor must not run when constitution blocks it")

    with pytest.raises(ConstitutionViolationError):
        await dispatch(
            registry=registry,
            role=AgentRole.VIDEO_AGENT,
            tool_name="generate_video_shot",
            tool_input={},
            executor=executor,
            constitution_check=check_constitution,
        )


def test_missing_physics_proxy_is_a_missing_dependency():
    from agentic_core.tool_gateway.constitution import MissingDependencyError

    with pytest.raises(MissingDependencyError) as info:
        check_constitution("generate_video_shot", {"shot_id": "s1"})
    assert info.value.code == "MISSING_DEPENDENCY"
    assert info.value.to_dict()["dependency"] == "run_blender_proxy"
    assert isinstance(info.value, ConstitutionViolationError)


@pytest.mark.asyncio
async def test_dispatch_awaits_async_constitution_check():
    """Day 12: the api's physics gate is async (DB-backed); dispatch must
    await it and never reach the executor when it raises."""
    registry = ToolRegistry()
    registry.register(_video_shot_tool().model_copy(update={"schema": {"type": "object"}}))
    calls: list[str] = []

    async def async_check(tool_name: str, tool_input: dict) -> None:
        calls.append(tool_name)
        raise ConstitutionViolationError("blocked", tool_name=tool_name)

    async def executor(tool_input: dict) -> dict:
        raise AssertionError("executor must not run")

    with pytest.raises(ConstitutionViolationError):
        await dispatch(
            registry=registry, role=AgentRole.VIDEO_AGENT, tool_name="generate_video_shot",
            tool_input={"physics_proxy_asset_id": "x"}, executor=executor,
            constitution_check=async_check,
        )
    assert calls == ["generate_video_shot"]

    async def passing_check(tool_name: str, tool_input: dict) -> None:
        return None

    async def ok(tool_input: dict) -> dict:
        return {"ok": True}

    result = await dispatch(
        registry=registry, role=AgentRole.VIDEO_AGENT, tool_name="generate_video_shot",
        tool_input={}, executor=ok, constitution_check=passing_check,
    )
    assert result.status == "SUCCESS"
