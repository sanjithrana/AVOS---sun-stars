from datetime import datetime, timezone

import pytest

from agentic_core.shotspec.builder import (
    SHOTSPEC_BUILDER_AGENT_ID,
    ShotSpecBuildError,
    build_shot_specs,
    content_hash,
    initial_world_state,
    next_version,
)
from packages.contracts.audio import SemanticBeat, SentenceTimestamp
from packages.contracts.script import ScriptScene
from packages.contracts.shotspec import ShotSpecStatus, ShotType

NOW = datetime(2026, 9, 28, tzinfo=timezone.utc)

SENTENCES = [
    SentenceTimestamp(text="Have you ever wondered about flowers?", start=0.0, end=2.4, word_count=6),
    SentenceTimestamp(text="Let's find out.", start=2.4, end=3.6, word_count=3),
    SentenceTimestamp(text="Flowers grow toward the sun.", start=3.6, end=5.6, word_count=5),
    SentenceTimestamp(text="Keep exploring!", start=5.6, end=6.4, word_count=2),
]
BEATS = [SemanticBeat(time=s.start, label=f"beat_{i + 1}") for i, s in enumerate(SENTENCES)]
SCENES = [
    ScriptScene(index=0, narration="Have you ever wondered about flowers? Let's find out.",
                visual_description="A sunny garden.", estimated_seconds=3.6),
    ScriptScene(index=1, narration="Flowers grow toward the sun. Keep exploring!",
                visual_description="A sunflower turning.", estimated_seconds=2.8),
]


def _build(**kw):
    args = dict(project_id="p1", beats=BEATS, sentences=SENTENCES, total_duration=6.4,
                scenes=SCENES, world_state=initial_world_state("p1"), now=NOW)
    args.update(kw)
    return build_shot_specs(**args)


def test_one_draft_per_beat_with_contiguous_timing():
    drafts = _build()
    assert [d.shot_index for d in drafts] == [0, 1, 2, 3]
    assert drafts[0].content.start_time == 0.0
    for a, b in zip(drafts, drafts[1:]):
        assert a.content.end_time == b.content.start_time
    assert drafts[-1].content.end_time == 6.4
    assert drafts[1].content.narration == "Let's find out."


def test_versioning_fields_are_set_from_the_start():
    spec = _build()[0].spec
    assert spec.version == 1
    assert spec.parent_version is None
    assert spec.status == ShotSpecStatus.DRAFT
    assert spec.created_by == SHOTSPEC_BUILDER_AGENT_ID
    assert spec.created_at == NOW
    assert spec.content_hash == content_hash(_build()[0].content)


def test_scenes_mapped_by_narration_words_and_shot_types():
    drafts = _build()
    assert [d.content.scene_index for d in drafts] == [0, 0, 1, 1]
    assert [d.content.camera.shot_type for d in drafts] == [
        ShotType.WIDE, ShotType.MEDIUM, ShotType.WIDE, ShotType.MEDIUM
    ]
    assert [d.content.scene_change for d in drafts] == [False, False, True, False]
    assert drafts[2].content.description == "A sunflower turning."


def test_deterministic_ids_and_hashes():
    a, b = _build(), _build()
    assert [d.spec.shot_id for d in a] == [d.spec.shot_id for d in b]
    assert [d.spec.content_hash for d in a] == [d.spec.content_hash for d in b]
    assert len({d.spec.shot_id for d in a}) == 4


def test_world_state_defaults_flow_into_shots():
    drafts = _build()
    assert drafts[0].content.environment.location == "main setting"
    assert drafts[0].content.style == initial_world_state("p1").style


def test_next_version_links_parent_and_changes_hash():
    draft = _build()[0]
    edited = draft.content.model_copy(update={"narration": "Edited line."})
    v2 = next_version(draft.spec, edited, now=NOW)
    assert (v2.version, v2.parent_version, v2.shot_id) == (2, 1, draft.spec.shot_id)
    assert v2.content_hash != draft.spec.content_hash
    assert v2.shotspec_id != draft.spec.shotspec_id


def test_rejects_empty_or_zero_length_beats():
    with pytest.raises(ShotSpecBuildError):
        _build(beats=[])
    with pytest.raises(ShotSpecBuildError):
        _build(beats=[SemanticBeat(time=1.0, label="a"), SemanticBeat(time=1.0, label="b")])
