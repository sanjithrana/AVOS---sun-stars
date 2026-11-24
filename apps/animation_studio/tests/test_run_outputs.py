"""A run page shows what the run actually made.

It used to hold one hard-coded list -- Mechanical Toy's compact / transformed / video -- so a Blueprint run was
asked for files it has never had: three cards reading "Waiting" forever and three empty prompt boxes, over a run that
had finished correctly.
"""
from __future__ import annotations

from studio.skilllab import asmr_cooking as AC
from studio.skilllab import asmr_cutting as XC
from studio.skilllab import film_style as FS
from studio.skilllab import motion_graphics as MG
from studio.skilllab import pipeline, routes

FILM = {
    "skill": "film-blueprint", "video": "final.mp4",
    "plan": {"shots": [{"n": 1, "title": "the sheet", "picture": "S01.png", "video": "S01.mp4"},
                       {"n": 2, "title": "one detail", "picture": "S02.png"},
                       {"n": 3, "title": "the machine"}]},
}


def test_every_skill_describes_its_own_outputs():
    for sid, mod in pipeline.SKILLS.items():
        if sid == "mechanical-toy":
            continue                                        # the one that keeps the old fallback
        assert callable(getattr(mod, "outputs_of", None)), sid


def test_a_film_shows_one_card_per_shot_then_the_film():
    out = FS.outputs_of(FILM)
    assert len(out) == 4
    assert [o["kind"] for o in out] == ["video", "image", "image", "video"]
    assert [o["file"] for o in out] == ["S01.mp4", "S02.png", None, "final.mp4"]
    assert out[0]["title"].startswith("1.") and out[-1]["title"] == "The film"


def test_each_shot_card_points_at_its_own_prompt():
    out = FS.outputs_of(FILM)
    assert [o["prompt"] for o in out] == ["shot1", "shot2", "shot3", None]
    assert out[1]["step"] == "pictures" and out[0]["step"] == "motion"


def test_the_one_video_skills_show_one_card():
    for mod, title in ((XC, "The cutting video"), (MG, "The animation")):
        out = mod.outputs_of({"video": "final.mp4"})
        assert len(out) == 1 and out[0]["kind"] == "video" and out[0]["title"] == title
        assert out[0]["file"] == "final.mp4" and out[0]["prompt"]


def test_cooking_looks_like_a_film_because_it_is_one():
    out = AC.outputs_of({"recipe": {"shots": [{"n": 1, "title": "the board", "picture": "S01.png"}]}, "video": "final.mp4"})
    assert len(out) == 2 and out[-1]["title"] == "The video"


def test_mechanical_toy_keeps_the_three_cards_it_has_always_had():
    out = routes.outputs_of({"skill": "mechanical-toy", "compact": "c.png", "transformed": "t.png", "video": "v.mp4"})
    assert [o["title"] for o in out] == ["Compact device", "Fully transformed", "Transformation video"]
    assert [o["file"] for o in out] == ["c.png", "t.png", "v.mp4"]


def test_an_unknown_skill_does_not_take_the_page_down():
    assert len(routes.outputs_of({"skill": "something-new"})) == 3
    assert len(routes.outputs_of({})) == 3


def test_a_describer_that_throws_falls_back_instead_of_erroring(monkeypatch):
    class Broken:
        INFO = {"name": "Broken"}

        @staticmethod
        def outputs_of(p):
            raise RuntimeError("boom")

    monkeypatch.setitem(pipeline.SKILLS, "broken-skill", Broken)
    assert len(routes.outputs_of({"skill": "broken-skill"})) == 3
