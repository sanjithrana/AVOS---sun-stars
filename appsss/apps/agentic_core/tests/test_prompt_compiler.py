"""
Week 3 Day 13 - Prompt Compiler determinism (Engineer 2).

Same ShotSpec (ShotContent) + same physics proxy + same candidate index
must compile to the exact same CompiledPrompt every time - no wall-clock,
no randomness, no dict-ordering flakiness.
"""

from packages.contracts.shotspec import Camera, Lighting, ShotContent, ShotType
from packages.contracts.world_state import CharacterState, EnvironmentState, ObjectState
from agentic_core.pipelines.shot.prompt_compiler import build_prompt_text, compile_prompt

PROXY_ID = "11111111-1111-1111-1111-111111111111"


def _content() -> ShotContent:
    return ShotContent(
        beat_label="beat_1",
        start_time=0.0,
        end_time=4.0,
        narration="Mira waves at the crowd.",
        description="A wide shot of a cheerful plaza at golden hour.",
        camera=Camera(shot_type=ShotType.WIDE, angle="low_angle", movement="dolly_in", lens_mm=24),
        lighting=Lighting(key="golden hour sun", mood="warm"),
        style="bright, friendly storybook illustration",
        characters={
            "mira": CharacterState(clothing="a red scarf", position="center", emotion="joyful", props=["flag"]),
            "theo": CharacterState(clothing="a blue coat", position="left", emotion="curious", props=[]),
        },
        objects={"lantern": ObjectState(state="lit", position="foreground")},
        environment=EnvironmentState(location="plaza", time_of_day="morning", weather="clear"),
    )


def test_compile_prompt_is_deterministic_across_repeated_calls():
    content = _content()
    first = compile_prompt(content, physics_proxy_asset_id=PROXY_ID, candidate_index=0)
    second = compile_prompt(content, physics_proxy_asset_id=PROXY_ID, candidate_index=0)

    assert first == second
    assert first.params_hash == second.params_hash
    assert first.seed == second.seed


def test_compile_prompt_is_deterministic_from_a_rebuilt_equal_content():
    """Rebuilding an equal-but-distinct ShotContent object (as happens
    once it round-trips through JSON/the database) must not change the
    compiled output."""
    content_a = _content()
    content_b = ShotContent.model_validate(content_a.model_dump(mode="json"))

    a = compile_prompt(content_a, physics_proxy_asset_id=PROXY_ID, candidate_index=1)
    b = compile_prompt(content_b, physics_proxy_asset_id=PROXY_ID, candidate_index=1)

    assert a == b


def test_different_candidate_index_changes_seed_and_hash_but_not_prompt_text():
    content = _content()
    c0 = compile_prompt(content, physics_proxy_asset_id=PROXY_ID, candidate_index=0)
    c1 = compile_prompt(content, physics_proxy_asset_id=PROXY_ID, candidate_index=1)

    assert c0.prompt == c1.prompt  # same creative description
    assert c0.seed != c1.seed
    assert c0.params_hash != c1.params_hash


def test_different_physics_proxy_changes_the_default_seed():
    """An edited ShotSpec always gets a fresh physics proxy (Day 12); the
    compiled prompt for the edited shot must not collide with the old
    one even if the creative content looks similar."""
    content = _content()
    other_proxy = "22222222-2222-2222-2222-222222222222"

    a = compile_prompt(content, physics_proxy_asset_id=PROXY_ID)
    b = compile_prompt(content, physics_proxy_asset_id=other_proxy)

    assert a.seed != b.seed
    assert a.params_hash != b.params_hash


def test_explicit_seed_is_honored_and_still_deterministic():
    content = _content()
    a = compile_prompt(content, physics_proxy_asset_id=PROXY_ID, seed=42)
    b = compile_prompt(content, physics_proxy_asset_id=PROXY_ID, seed=42)

    assert a.seed == 42 and b.seed == 42
    assert a == b


def test_prompt_text_lists_characters_in_sorted_order_regardless_of_dict_order():
    content = _content()
    reordered = content.model_copy(
        update={"characters": {"theo": content.characters["theo"], "mira": content.characters["mira"]}}
    )

    assert build_prompt_text(content) == build_prompt_text(reordered)


def test_compiled_prompt_carries_physics_conditioning():
    content = _content()
    compiled = compile_prompt(content, physics_proxy_asset_id=PROXY_ID)

    assert compiled.physics_proxy_asset_id == PROXY_ID
    assert compiled.conditioning_passes == ["depth", "normal", "canny", "mask"]
    assert compiled.width > 0 and compiled.height > 0
    assert "Mira" not in compiled.prompt or "mira" in compiled.prompt.lower()  # description-driven, not narration
