"""
ShotSpec builder (Week 3 Day 11; AVOS-06 s2, AVOS-03 v1.1 s8).

Turns the Week 2 audio-first output - semantic beats + sentence
timestamps of the approved script's narration - into ShotSpec drafts:
one shot per beat, timed to the narration, carrying full versioning
fields from the start (shot_id, shotspec_id, version, parent_version,
created_by, created_at, status, content_hash).

Pure and deterministic: no DB, no LLM, no clock unless you omit `now`.
Same inputs -> same shot ids and content hashes, so re-planning is
idempotent and changes are detectable by hash.
"""

import hashlib
import json
from datetime import datetime, timezone
from uuid import UUID, uuid5, NAMESPACE_URL

from packages.contracts.audio import SemanticBeat, SentenceTimestamp
from packages.contracts.script import ScriptScene
from packages.contracts.shotspec import (
    Camera,
    ShotContent,
    ShotSpec,
    ShotSpecDraft,
    ShotSpecStatus,
    ShotType,
)
from packages.contracts.world_state import WorldState

# Identity of this agent in ShotSpec.created_by (a UUID by contract).
SHOTSPEC_BUILDER_AGENT_ID: UUID = uuid5(NAMESPACE_URL, "avos:agent:shotspec_builder")

# Within a scene: establish wide, then alternate medium / close-up.
_SHOT_TYPE_CYCLE = [ShotType.MEDIUM, ShotType.CLOSE_UP]


class ShotSpecBuildError(ValueError):
    """Inputs can't produce a valid shot list."""


def content_hash(content: ShotContent) -> str:
    data = content.model_dump(mode="json")
    # fields added later are left out at their defaults, so existing shots keep their hash
    if not data.get("prompt"):
        data.pop("prompt", None)
    if not data.get("take"):
        data.pop("take", None)
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def shot_id_for(project_id: str, shot_index: int) -> UUID:
    """Stable id per (project, position) so re-planning maps onto the same shots."""
    return uuid5(NAMESPACE_URL, f"avos:{project_id}:shot:{shot_index}")


def make_spec(
    *,
    shot_id: UUID,
    content: ShotContent,
    version: int = 1,
    parent_version: int | None = None,
    created_by: UUID = SHOTSPEC_BUILDER_AGENT_ID,
    now: datetime | None = None,
    status: ShotSpecStatus = ShotSpecStatus.DRAFT,
) -> ShotSpec:
    """Versioned envelope for one piece of shot content."""
    digest = content_hash(content)
    return ShotSpec(
        shot_id=shot_id,
        shotspec_id=uuid5(NAMESPACE_URL, f"avos:shotspec:{shot_id}:v{version}:{digest}"),
        version=version,
        parent_version=parent_version,
        created_by=created_by,
        created_at=now or datetime.now(timezone.utc),
        status=status,
        content_hash=digest,
    )


def next_version(previous: ShotSpec, content: ShotContent, *, now: datetime | None = None,
                 created_by: UUID = SHOTSPEC_BUILDER_AGENT_ID) -> ShotSpec:
    """Envelope for an edited shot: version+1, parent_version=previous."""
    return make_spec(
        shot_id=previous.shot_id,
        content=content,
        version=previous.version + 1,
        parent_version=previous.version,
        created_by=created_by,
        now=now,
    )


def _scene_for_word_offset(scenes: list[ScriptScene], offset: int) -> ScriptScene | None:
    """Scene containing the narration word at `offset` (scenes are read
    back-to-back by TTS, so cumulative word counts locate them)."""
    start = 0
    for scene in scenes:
        count = len(scene.narration.split())
        if offset < start + count:
            return scene
        start += count
    return scenes[-1] if scenes else None


def build_shot_specs(
    *,
    project_id: str,
    beats: list[SemanticBeat],
    sentences: list[SentenceTimestamp],
    total_duration: float,
    scenes: list[ScriptScene] | None = None,
    world_state: WorldState | None = None,
    now: datetime | None = None,
) -> list[ShotSpecDraft]:
    """One ShotSpec draft per semantic beat, in narrative order."""
    if not beats:
        raise ShotSpecBuildError("No semantic beats to build shots from.")
    if total_duration <= 0:
        raise ShotSpecBuildError("Audio duration must be positive.")

    ordered = sorted(beats, key=lambda b: b.time)
    scenes = scenes or []
    world = world_state or WorldState(project_id=project_id)
    created_at = now or datetime.now(timezone.utc)

    drafts: list[ShotSpecDraft] = []
    word_offset = 0
    previous_scene: int | None = None
    shot_in_scene = 0

    for index, beat in enumerate(ordered):
        start = beat.time
        end = ordered[index + 1].time if index + 1 < len(ordered) else total_duration
        if end <= start:
            raise ShotSpecBuildError(f"Beat {beat.label} has no duration ({start} -> {end}).")

        sentence = sentences[index] if index < len(sentences) else None
        scene = _scene_for_word_offset(scenes, word_offset)
        if sentence:
            word_offset += sentence.word_count

        scene_index = scene.index if scene else None
        new_scene = scene_index != previous_scene
        shot_in_scene = 0 if new_scene else shot_in_scene + 1
        previous_scene = scene_index

        shot_type = (
            ShotType.WIDE if shot_in_scene == 0 else _SHOT_TYPE_CYCLE[(shot_in_scene - 1) % 2]
        )

        content = ShotContent(
            beat_label=beat.label,
            start_time=round(start, 3),
            end_time=round(end, 3),
            narration=sentence.text if sentence else "",
            scene_index=scene_index,
            description=scene.visual_description if scene else "",
            camera=Camera(
                shot_type=shot_type,
                lens_mm={ShotType.WIDE: 24, ShotType.MEDIUM: 35, ShotType.CLOSE_UP: 85}.get(shot_type, 35),
            ),
            style=world.style,
            characters={k: v.model_copy() for k, v in world.characters.items()},
            objects={k: v.model_copy() for k, v in world.objects.items()},
            environment=world.environment.model_copy(),
            # A later scene may move location / time; the first can't.
            scene_change=new_scene and index > 0,
        )

        drafts.append(
            ShotSpecDraft(
                shot_index=index,
                spec=make_spec(shot_id=shot_id_for(project_id, index), content=content, now=created_at),
                content=content,
            )
        )

    return drafts


def initial_world_state(
    project_id: str,
    *,
    style: str = "bright, friendly storybook illustration",
    location: str = "main setting",
    time_of_day: str = "morning",
) -> WorldState:
    """Starting world before any shot. Week 3's Character/World agents
    will populate characters, objects and locations from the script."""
    return WorldState(
        project_id=project_id,
        version=0,
        style=style,
        environment={"location": location, "time_of_day": time_of_day, "weather": "clear"},
    )
