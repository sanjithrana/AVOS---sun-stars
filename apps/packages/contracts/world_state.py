"""
WorldState contract (AVOS-03 v1.1 s8, AVOS-06 s3.2).

The running "truth" of the story world at a point in the shot sequence:
who wears what, where things are, where/when we are, and the visual
style. Every accepted ShotSpec advances it by one version; the
continuity validator compares each new shot against it.
"""

from pydantic import BaseModel, ConfigDict, Field


class CharacterState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    clothing: str | None = None
    position: str | None = None  # e.g. "left", "center", "right"
    emotion: str | None = None
    props: list[str] = Field(default_factory=list)


class ObjectState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: str | None = None  # e.g. "open", "closed", "blooming"
    position: str | None = None


class EnvironmentState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    location: str | None = None
    time_of_day: str | None = None  # see TIME_OF_DAY_ORDER
    weather: str | None = None


# Forward order of time within one continuous sequence. Going backwards
# (evening -> morning) without a declared time jump is a violation.
TIME_OF_DAY_ORDER = ["dawn", "morning", "noon", "afternoon", "evening", "dusk", "night"]


class WorldState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: str
    version: int = Field(default=0, ge=0)
    characters: dict[str, CharacterState] = Field(default_factory=dict)
    objects: dict[str, ObjectState] = Field(default_factory=dict)
    environment: EnvironmentState = Field(default_factory=EnvironmentState)
    style: str | None = None


class WorldStateResponse(BaseModel):
    """GET /projects/{id}/world-state"""

    model_config = ConfigDict(extra="forbid")

    project_id: str
    version: int
    state: WorldState
    source_shot_id: str | None = None
