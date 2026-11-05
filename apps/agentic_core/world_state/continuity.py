"""
Continuity validator (Week 3 Day 11; AVOS-06 s3.2).

Compares a proposed shot (ShotContent) against the current WorldState
and reports violations. Intentional changes are declared on the shot
(`state_changes`) and are not violations; a new scene (`scene_change`)
may change location and time of day.

    validate_continuity(shot, world) -> ContinuityReport   (read-only)
    apply_shot(world, shot)          -> WorldState          (version + 1)

Rules (error = blocks the shot, warning = informational):
  CHARACTER_CLOTHING_MISMATCH   error    clothing changed, not declared
  CHARACTER_PROPS_MISMATCH      warning  props changed, not declared
  NEW_CHARACTER                 warning  character not yet in the world
  OBJECT_STATE_MISMATCH         error    object state changed, not declared
  LOCATION_MISMATCH             error    location changed mid-scene
  TIME_OF_DAY_REGRESSION        error    time went backwards mid-scene
  WEATHER_CHANGED               warning  weather changed mid-scene
  STYLE_MISMATCH                error    visual style differs from the world's
  DECLARED_CHANGE_NOT_REFLECTED error    a declared change isn't in the shot
  UNKNOWN_CHANGE_TARGET         warning  declared change for unknown entity
"""

from typing import Any

from packages.contracts.shotspec import (
    ContinuityReport,
    ContinuitySeverity,
    ContinuityViolation,
    ShotContent,
)
from packages.contracts.world_state import TIME_OF_DAY_ORDER, WorldState

ERROR = ContinuitySeverity.ERROR
WARNING = ContinuitySeverity.WARNING


def _declared(shot: ShotContent, entity_type: str, entity: str | None, field: str) -> bool:
    return any(
        c.entity_type == entity_type and c.entity == entity and c.field == field
        for c in shot.state_changes
    )


def _v(code, severity, message, entity=None, field=None, expected=None, actual=None) -> ContinuityViolation:
    return ContinuityViolation(
        code=code, severity=severity, message=message,
        entity=entity, field=field, expected=expected, actual=actual,
    )


def _time_index(value: str | None) -> int | None:
    return TIME_OF_DAY_ORDER.index(value) if value in TIME_OF_DAY_ORDER else None


def validate_continuity(shot: ShotContent, world: WorldState) -> ContinuityReport:
    violations: list[ContinuityViolation] = []

    # -- characters -------------------------------------------------------
    for name, state in shot.characters.items():
        known = world.characters.get(name)
        if known is None:
            violations.append(_v("NEW_CHARACTER", WARNING,
                                 f"'{name}' appears for the first time.", entity=name))
            continue

        if (known.clothing and state.clothing and known.clothing != state.clothing
                and not _declared(shot, "character", name, "clothing")):
            violations.append(_v(
                "CHARACTER_CLOTHING_MISMATCH", ERROR,
                f"'{name}' was wearing '{known.clothing}' but this shot shows '{state.clothing}'.",
                entity=name, field="clothing", expected=known.clothing, actual=state.clothing,
            ))

        if (known.props and sorted(known.props) != sorted(state.props)
                and not _declared(shot, "character", name, "props")):
            violations.append(_v(
                "CHARACTER_PROPS_MISMATCH", WARNING,
                f"'{name}' props changed from {known.props} to {state.props}.",
                entity=name, field="props", expected=known.props, actual=state.props,
            ))

    # -- objects ----------------------------------------------------------
    for name, state in shot.objects.items():
        known = world.objects.get(name)
        if (known and known.state and state.state and known.state != state.state
                and not _declared(shot, "object", name, "state")):
            violations.append(_v(
                "OBJECT_STATE_MISMATCH", ERROR,
                f"'{name}' was '{known.state}' but this shot shows '{state.state}'.",
                entity=name, field="state", expected=known.state, actual=state.state,
            ))

    # -- environment (mid-scene only; a new scene may move on) -----------
    env, known_env = shot.environment, world.environment
    if not shot.scene_change:
        if (known_env.location and env.location and known_env.location != env.location
                and not _declared(shot, "environment", None, "location")):
            violations.append(_v(
                "LOCATION_MISMATCH", ERROR,
                f"Location jumped from '{known_env.location}' to '{env.location}' within a scene.",
                field="location", expected=known_env.location, actual=env.location,
            ))

        before, after = _time_index(known_env.time_of_day), _time_index(env.time_of_day)
        if (before is not None and after is not None and after < before
                and not _declared(shot, "environment", None, "time_of_day")):
            violations.append(_v(
                "TIME_OF_DAY_REGRESSION", ERROR,
                f"Time went backwards from '{known_env.time_of_day}' to '{env.time_of_day}'.",
                field="time_of_day", expected=known_env.time_of_day, actual=env.time_of_day,
            ))

        if (known_env.weather and env.weather and known_env.weather != env.weather
                and not _declared(shot, "environment", None, "weather")):
            violations.append(_v(
                "WEATHER_CHANGED", WARNING,
                f"Weather changed from '{known_env.weather}' to '{env.weather}' mid-scene.",
                field="weather", expected=known_env.weather, actual=env.weather,
            ))

    # -- style ------------------------------------------------------------
    if (world.style and shot.style and world.style != shot.style
            and not _declared(shot, "environment", None, "style")):
        violations.append(_v(
            "STYLE_MISMATCH", ERROR,
            f"Visual style '{shot.style}' differs from the project's '{world.style}'.",
            field="style", expected=world.style, actual=shot.style,
        ))

    # -- declared changes must be real and reflected ----------------------
    for change in shot.state_changes:
        actual: Any
        if change.entity_type == "character":
            if change.entity not in world.characters and change.entity not in shot.characters:
                violations.append(_v("UNKNOWN_CHANGE_TARGET", WARNING,
                                     f"Declared change for unknown character '{change.entity}'.",
                                     entity=change.entity, field=change.field))
                continue
            target = shot.characters.get(change.entity)
            actual = getattr(target, change.field, None) if target else None
        elif change.entity_type == "object":
            if change.entity not in world.objects and change.entity not in shot.objects:
                violations.append(_v("UNKNOWN_CHANGE_TARGET", WARNING,
                                     f"Declared change for unknown object '{change.entity}'.",
                                     entity=change.entity, field=change.field))
                continue
            target = shot.objects.get(change.entity)
            actual = getattr(target, change.field, None) if target else None
        else:
            actual = shot.style if change.field == "style" else getattr(shot.environment, change.field, None)

        if actual != change.value:
            violations.append(_v(
                "DECLARED_CHANGE_NOT_REFLECTED", ERROR,
                f"Shot declares {change.entity_type} {change.entity or ''} {change.field}="
                f"{change.value!r} but shows {actual!r}.".replace("  ", " "),
                entity=change.entity, field=change.field, expected=change.value, actual=actual,
            ))

    return ContinuityReport(
        passed=not any(v.severity == ERROR for v in violations),
        world_state_version=world.version,
        violations=violations,
    )


def apply_shot(world: WorldState, shot: ShotContent) -> WorldState:
    """WorldState after this shot: shot values win where set; version + 1."""
    characters = {k: v.model_copy() for k, v in world.characters.items()}
    for name, state in shot.characters.items():
        merged = characters.get(name)
        updates = {k: v for k, v in state.model_dump().items() if v not in (None, [])}
        characters[name] = merged.model_copy(update=updates) if merged else state.model_copy()

    objects = {k: v.model_copy() for k, v in world.objects.items()}
    for name, state in shot.objects.items():
        merged = objects.get(name)
        updates = {k: v for k, v in state.model_dump().items() if v is not None}
        objects[name] = merged.model_copy(update=updates) if merged else state.model_copy()

    env_updates = {k: v for k, v in shot.environment.model_dump().items() if v is not None}
    style = world.style or shot.style
    if _declared(shot, "environment", None, "style"):
        style = shot.style

    return WorldState(
        project_id=world.project_id,
        version=world.version + 1,
        characters=characters,
        objects=objects,
        environment=world.environment.model_copy(update=env_updates),
        style=style,
    )
