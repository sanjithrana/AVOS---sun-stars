"""Small pieces: reading briefs and descriptions, the AI-answer parser, settings validation, the style registry."""
from __future__ import annotations

import pytest

from studio import jobs, styles
from studio.director.pre import title_from_brief
from studio.llm import extract_json
from studio.render import engines, rig
from studio.render.fx import guess_fx
from studio.render.props import guess_props, place_props


def test_title_from_brief():
    assert title_from_brief("A 20-second whiteboard story about a girl who wants to touch the moon, with a funny twist") == \
        "A girl who wants to touch the moon"
    assert title_from_brief("Make a 30 second video about a shy cat who learns to dance") == "A shy cat who learns to dance"
    assert len(title_from_brief("x" * 300)) <= 41


def test_keywords_match_whole_words_only():
    assert guess_props("a girl in the street who wants to touch the moon") == ["moon"]        # not "tree" in street
    assert "mic" not in guess_props("a comic about teaching")                                   # not "mic" in comic
    assert "cup" not in guess_props("she starts to teach")                                       # not "tea" in teach
    assert "rain" not in guess_fx("she wears a yellow raincoat")
    assert "confetti" not in guess_fx("back at the window")
    assert "speedlines" in guess_fx("he runs to the bus")


def test_props_are_placed_where_they_belong():
    sky, wall, ground = place_props(["moon", "window", "ball"])
    assert sky["y"] < 0.3 and 0.3 <= wall["y"] <= 0.5 and ground["y"] > 0.6
    assert all(p["x"] < 0.35 or p["x"] > 0.65 for p in (sky, wall, ground))   # characters stand mid-frame


def test_character_from_description():
    luna = rig.from_description("luna", "Luna", "a small girl, long black hair with a yellow bow, yellow raincoat, blue boots")
    assert luna["hair"] == "long" and luna["top"] == "hoodie" and "bow" in luna["accessories"]
    assert luna["colors"]["top"].upper() in ("#FFD54F", "#FFEB3B", "#FFC107", "#F9D71C") or luna["colors"]["top"].upper().startswith("#FF")
    assert luna["colors"]["hair"].upper() != luna["colors"]["top"].upper()
    cat = rig.from_description("pip", "Pip", "a round orange cat")
    assert cat["body"] == "animal" and cat["ears"] == "cat"
    girl = rig.from_description("hero", "Hero", "a girl who wants to touch the moon")
    assert girl["hair"] in ("long", "ponytail") and girl["top"] == "dress"


@pytest.mark.parametrize("text,want", [
    ('{"a": 1}', {"a": 1}),
    ('```json\n{"a": 1}\n```', {"a": 1}),
    ('Sure! Here it is: {"a": {"b": [1, 2,]}, } thanks', {"a": {"b": [1, 2]}}),
    ('[1, 2]', [1, 2]),
    ("no json here", None),
])
def test_extract_json(text, want):
    assert extract_json(text) == want


def test_review_rounds_validation():
    assert jobs.clean_rounds({"castRounds": "4", "finalRounds": ""}) == {"castRounds": 4, "finalRounds": None}
    for bad in ("0", "11", "2.5", "x"):
        with pytest.raises(ValueError):
            jobs.clean_rounds({"chunkRounds": bad})


def test_style_registry_matches_engines():
    reg = styles.registry()
    names = {s["name"] for s in reg}
    assert {"painted-story-mv", "whiteboard-explainer", "pixel-story", "anime-cel", "crayon-storybook", "paper-cutout", "motion-graphics"} <= names
    for s in reg:
        assert s["installed"] == (s["engine"] in engines.ENGINES)
    assert len(engines.ENGINES) == 7
