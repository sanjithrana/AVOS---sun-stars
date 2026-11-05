"""Day 11: continuity validator - pass case + distinct violation cases."""

from agentic_core.world_state.continuity import apply_shot, validate_continuity
from packages.contracts.shotspec import ShotContent, StateChange
from packages.contracts.world_state import (
    CharacterState,
    EnvironmentState,
    ObjectState,
    WorldState,
)

WORLD = WorldState(
    project_id="p1",
    version=3,
    characters={"Milo": CharacterState(clothing="yellow shirt", position="left", emotion="happy")},
    objects={"door": ObjectState(state="closed")},
    environment=EnvironmentState(location="garden", time_of_day="afternoon", weather="clear"),
    style="storybook",
)


def shot(**kw) -> ShotContent:
    base = dict(
        beat_label="beat_4", start_time=6.0, end_time=9.0, style="storybook",
        characters={"Milo": CharacterState(clothing="yellow shirt", position="right", emotion="curious")},
        objects={"door": ObjectState(state="closed")},
        environment=EnvironmentState(location="garden", time_of_day="afternoon", weather="clear"),
    )
    base.update(kw)
    return ShotContent(**base)


def codes(report):
    return [v.code for v in report.violations]


def test_consistent_shot_passes():
    report = validate_continuity(shot(), WORLD)
    assert report.passed
    assert report.violations == []  # moving and emotions are allowed
    assert report.world_state_version == 3


def test_clothing_change_is_a_violation():
    s = shot(characters={"Milo": CharacterState(clothing="red jacket")})
    report = validate_continuity(s, WORLD)
    assert not report.passed
    v = report.errors[0]
    assert (v.code, v.entity, v.expected, v.actual) == (
        "CHARACTER_CLOTHING_MISMATCH", "Milo", "yellow shirt", "red jacket")


def test_location_jump_mid_scene_is_a_violation():
    report = validate_continuity(shot(environment=EnvironmentState(location="kitchen")), WORLD)
    assert not report.passed and codes(report) == ["LOCATION_MISMATCH"]


def test_time_going_backwards_is_a_violation():
    s = shot(environment=EnvironmentState(location="garden", time_of_day="morning"))
    report = validate_continuity(s, WORLD)
    assert not report.passed and "TIME_OF_DAY_REGRESSION" in codes(report)


def test_object_state_change_is_a_violation():
    report = validate_continuity(shot(objects={"door": ObjectState(state="open")}), WORLD)
    assert not report.passed and codes(report) == ["OBJECT_STATE_MISMATCH"]


def test_style_mismatch_is_a_violation():
    report = validate_continuity(shot(style="photoreal"), WORLD)
    assert not report.passed and codes(report) == ["STYLE_MISMATCH"]


def test_new_scene_may_change_location_and_time():
    s = shot(scene_change=True,
             environment=EnvironmentState(location="kitchen", time_of_day="morning", weather="rain"))
    assert validate_continuity(s, WORLD).passed


def test_declared_change_is_allowed_and_must_be_reflected():
    change = StateChange(entity_type="character", entity="Milo", field="clothing", value="red jacket",
                         reason="puts on a jacket")
    ok = shot(characters={"Milo": CharacterState(clothing="red jacket")}, state_changes=[change])
    assert validate_continuity(ok, WORLD).passed

    lying = shot(state_changes=[change])  # declares a jacket, still shows the shirt
    report = validate_continuity(lying, WORLD)
    assert not report.passed and codes(report) == ["DECLARED_CHANGE_NOT_REFLECTED"]


def test_new_character_is_only_a_warning():
    s = shot(characters={**shot().characters, "Bee": CharacterState(clothing="stripes")})
    report = validate_continuity(s, WORLD)
    assert report.passed and codes(report) == ["NEW_CHARACTER"]


def test_multiple_violations_are_all_reported():
    s = shot(characters={"Milo": CharacterState(clothing="red jacket")},
             objects={"door": ObjectState(state="open")},
             environment=EnvironmentState(location="kitchen"))
    assert set(codes(validate_continuity(s, WORLD))) == {
        "CHARACTER_CLOTHING_MISMATCH", "OBJECT_STATE_MISMATCH", "LOCATION_MISMATCH"}


def test_apply_shot_advances_world_state():
    change = StateChange(entity_type="object", entity="door", field="state", value="open")
    s = shot(objects={"door": ObjectState(state="open")}, state_changes=[change],
             characters={"Milo": CharacterState(position="right"), "Bee": CharacterState(clothing="stripes")})
    new = apply_shot(WORLD, s)
    assert new.version == 4
    assert new.objects["door"].state == "open"
    assert new.characters["Milo"].clothing == "yellow shirt"  # untouched fields kept
    assert new.characters["Milo"].position == "right"
    assert "Bee" in new.characters
    assert WORLD.objects["door"].state == "closed"  # original not mutated
