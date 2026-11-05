import pytest

from agentic_core.models.llm.mock_provider import MockLLMProvider
from agentic_core.pipelines.script.generator import (
    ScriptGenerationError,
    generate_script,
)
from agentic_core.pipelines.script.validator import (
    has_blocking_errors,
    validate_script,
)


@pytest.mark.asyncio
async def test_generate_script_returns_validated_script_object():
    script = await generate_script(
        project_id="proj-1",
        topic="how bees make honey",
        duration_seconds=32,
        llm=MockLLMProvider(),
    )

    assert script.project_id == "proj-1"
    assert script.scenes  # at least one scene
    assert script.total_estimated_seconds > 0
    assert script.model == "mock"

    issues = validate_script(script, target_duration_seconds=32)
    assert not has_blocking_errors(issues)


@pytest.mark.asyncio
async def test_generate_script_scales_scene_count_with_duration():
    short = await generate_script(
        project_id="p", topic="x", duration_seconds=8, llm=MockLLMProvider()
    )
    long = await generate_script(
        project_id="p", topic="x", duration_seconds=64, llm=MockLLMProvider()
    )

    assert len(long.scenes) > len(short.scenes)


@pytest.mark.asyncio
async def test_generate_script_raises_on_unparseable_llm_response():
    class BrokenProvider:
        name = "broken"

        async def complete(self, prompt, *, system=None, max_tokens=1024, temperature=0.7):
            return "not json at all"

    with pytest.raises(ScriptGenerationError):
        await generate_script(
            project_id="p",
            topic="x",
            duration_seconds=30,
            llm=BrokenProvider(),
        )


def test_validate_script_flags_empty_narration():
    from packages.contracts.script import Script, ScriptScene

    script = Script(
        project_id="p",
        topic="x",
        model="mock",
        total_estimated_seconds=5,
        scenes=[
            ScriptScene(
                index=0, narration="  ", visual_description="a", estimated_seconds=5
            )
        ],
    )

    issues = validate_script(script)
    assert has_blocking_errors(issues)
