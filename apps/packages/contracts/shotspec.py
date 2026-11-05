from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ShotSpecStatus(str, Enum):
    DRAFT = "DRAFT"
    PLANNED = "PLANNED"
    BLENDER_READY = "BLENDER_READY"
    GENERATING = "GENERATING"
    QA_PENDING = "QA_PENDING"
    PASSED = "PASSED"
    FAILED = "FAILED"
    REPAIRING = "REPAIRING"
    APPROVED = "APPROVED"


class ShotSpec(BaseModel):
    """
    Canonical AVOS ShotSpec contract.

    This is the versioned production artifact shared across:
        Narrative -> Blender -> ComfyUI -> QA -> Repair
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    shot_id: UUID
    shotspec_id: UUID

    version: int = Field(
        ge=1,
    )

    parent_version: int | None = Field(
        default=None,
        ge=1,
    )

    created_by: UUID

    created_at: datetime

    status: ShotSpecStatus = ShotSpecStatus.DRAFT

    content_hash: str = Field(
        min_length=1,
    )

# ---------------------------------------------------------------------------
# Week 3 Day 11: shot content + continuity.
#
# ShotSpec above is the versioned *envelope* (ids, version lineage, status,
# content hash) and is locked by tests. The creative/technical payload it
# versions lives in ShotContent. A ShotSpecDraft pairs the two - that is
# what the ShotSpec builder produces and what shot_versions rows store.
# ---------------------------------------------------------------------------

from enum import Enum as _Enum  # noqa: E402
from typing import Any as _Any  # noqa: E402

from packages.contracts.world_state import (  # noqa: E402
    CharacterState,
    EnvironmentState,
    ObjectState,
)


class ShotType(str, _Enum):
    WIDE = "wide"
    MEDIUM = "medium"
    CLOSE_UP = "close_up"
    INSERT = "insert"


class Camera(BaseModel):
    model_config = ConfigDict(extra="forbid")

    shot_type: ShotType = ShotType.MEDIUM
    angle: str = "eye_level"
    movement: str = "static"
    lens_mm: int = Field(default=35, gt=0)


class Lighting(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str = "soft daylight"
    mood: str = "warm"


class StateChange(BaseModel):
    """An *intentional* change to the world made by this shot (e.g. the
    character puts on a hat). Declared changes are not continuity
    violations; they advance the WorldState instead."""

    model_config = ConfigDict(extra="forbid")

    entity_type: str = Field(pattern="^(character|object|environment)$")
    entity: str | None = None  # character/object name; None for environment
    field: str = Field(min_length=1)
    value: _Any = None
    reason: str = ""


class ShotContent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Timing (from the Week 2 audio beats)
    beat_label: str = Field(min_length=1)
    start_time: float = Field(ge=0)
    end_time: float = Field(gt=0)
    narration: str = ""
    scene_index: int | None = Field(default=None, ge=0)

    # What we see
    description: str = ""
    camera: Camera = Field(default_factory=Camera)
    lighting: Lighting = Field(default_factory=Lighting)
    style: str | None = None
    characters: dict[str, CharacterState] = Field(default_factory=dict)
    objects: dict[str, ObjectState] = Field(default_factory=dict)
    environment: EnvironmentState = Field(default_factory=EnvironmentState)

    # Continuity controls
    state_changes: list[StateChange] = Field(default_factory=list)
    # A new scene may legitimately change location / reset time of day.
    scene_change: bool = False
    # Physics-before-pixels: shots with physical interaction must get a
    # Blender physics proxy before any pixels are generated (Day 12+).
    requires_physics: bool = False

    # Written by a person in the Studio: the exact prompt for this shot (replaces the compiled one), and a take
    # counter so "regenerate" with nothing else changed still gets a fresh version and new seeds.
    prompt: str | None = None
    take: int = Field(default=0, ge=0)

    @property
    def duration_seconds(self) -> float:
        return round(self.end_time - self.start_time, 3)


class ShotSpecDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    shot_index: int = Field(ge=0)
    spec: ShotSpec
    content: ShotContent


class ContinuitySeverity(str, _Enum):
    ERROR = "error"
    WARNING = "warning"


class ContinuityViolation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    severity: ContinuitySeverity
    entity: str | None = None
    field: str | None = None
    expected: _Any = None
    actual: _Any = None
    message: str


class ContinuityReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    passed: bool
    world_state_version: int
    violations: list[ContinuityViolation] = Field(default_factory=list)

    @property
    def errors(self) -> list[ContinuityViolation]:
        return [v for v in self.violations if v.severity == ContinuitySeverity.ERROR]
