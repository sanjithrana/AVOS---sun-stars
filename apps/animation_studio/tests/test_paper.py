"""The paper-cut look: the shared rules, and that every skill that offers it actually uses them."""
from __future__ import annotations

from studio import paper
from studio.explainer import engines
from studio.explainer import styles as xstyles
from studio.skilllab import company_story as CS
from studio.stickman import prompts as sprompts
from studio.stickman import styles as sstyles


def test_pacing_and_palettes() -> None:
    assert paper.sentences_for(30) == (12, 15)          # 16 would need a shot under two seconds
    assert paper.sentences_for(60) == (22, 30)
    assert paper.sentences_for(300) == (120, 150)
    lo, hi = paper.sentences_for(45)                      # between the tested marks
    assert 12 < lo < 22 and 16 < hi < 30
    lo, hi = paper.sentences_for(8)                       # shorter than the shortest mark
    assert 1 <= lo <= hi <= 6
    assert "earth" in paper.palette_for("The Roman Empire history")
    assert "indigo" in paper.palette_for("what happens inside a black hole")
    assert paper.palette_for("")                          # never empty


def test_look_is_recognised_and_short_enough_for_free_picture_services() -> None:
    assert paper.is_paper(paper.LOOK_SHORT) and paper.is_paper(paper.LOOK)
    assert not paper.is_paper("3D animated look, glossy Pixar-like render")
    assert not paper.is_paper(None)
    assert len(paper.LOOK_SHORT) < 320                    # routes keep 600 characters of the style field
    assert len(paper.tail("space", short=True)) < len(paper.tail("space"))


def test_animation_assembles_only_when_there_is_time_for_it() -> None:
    long_clip = paper.animation(10)
    short_clip = paper.animation(4)
    assert "ASSEMBLY" in long_clip and "LIVING PAPER POSTER" in long_clip
    assert "ASSEMBLY" not in short_clip and "living paper poster" in short_clip
    assert "ASSEMBLY" not in paper.animation(10, assemble=False)
    for text in (long_clip, short_clip):                  # the camera is locked in both
        assert "no zoom, pan, tilt" in text and "no music" in text
    assert "keep the narration audible" in paper.animation(10, audio=True)


def test_writer_share_drops_what_code_already_applies() -> None:
    md = ("# Paper\n\n## 1. Narration\nOne sentence, one visual.\n\n> a quoted prompt block\n\n"
          "## 5. Motion (image to video)\nnot for the writer\n\n> another block\n\n"
          "## 7. Where this is used\na table of studios\n")
    out = paper.for_writer(md, 60)
    assert "One sentence, one visual." in out
    assert "quoted prompt block" not in out and "not for the writer" not in out and "table of studios" not in out
    assert paper.for_writer("", 60) == paper.rules(60)    # missing file: the built-in rules


def test_explainer_offers_the_look_and_uses_it_everywhere() -> None:
    assert any(s["id"] == "paper" for s in xstyles.STYLES)
    p = {"id": "x1", "brief": "how viruses work", "style": xstyles.prompt_for("paper"),
         "plan": {"characters": [], "props": [], "world": {"look": "a cell"}, "palette": [],
                  "shots": [], "logline": "a virus story"}}
    assert engines.paper_look(p) and not engines.paper_look({"style": xstyles.prompt_for("3d")})
    shot = {"characters": [], "props": [], "action": "the virus drifts to the cell wall", "shot_type": "demonstration",
            "camera": {"type": "medium_shot", "lens_mm": 50, "movement": "static"}, "seconds": 4, "n": 2,
            "visualization": {"cross_section": False, "force_arrows": False}}
    text, _ = engines.shot_prompt_used(p, shot)
    assert "handcrafted" in text and "paper" in text.lower()
    assert paper.NEGATIVE in engines.negative(p) and paper.NEGATIVE not in engines.negative({"style": "3D animated look"})
    motion = engines.animation_prompt(p, shot)
    assert "no zoom, pan, tilt" in motion and "the virus drifts to the cell wall" in motion
    assert "ASSEMBLY" in engines.animation_prompt(p, {**shot, "n": 1, "seconds": 8})     # the first shot builds itself


def test_picture_prompt_file_is_one_prompt_per_paragraph() -> None:
    """The paper workflow's prompt file: every shot's prompt, self-contained, for any picture model."""
    from studio.explainer import routes, store
    shot = {"id": "S01", "index": 1, "shot_type": "establishing", "seconds": 3, "narration": "n", "characters": [], "props": [],
            "camera": {"type": "wide_shot", "lens_mm": 24, "movement": "static"}, "action": "the hall of scrolls stands quiet",
            "visualization": {"cross_section": False, "force_arrows": False}}
    p = {"id": "t-paper", "title": "The Library", "brief": "the library", "seconds": 30, "aspect": "9:16",
         "style": xstyles.prompt_for("paper"), "status": "done", "createdAt": "x", "updatedAt": "x",
         "plan": {"characters": [], "props": [], "world": {"look": "a scroll hall"}, "palette": [], "logline": "a library",
                  "shots": [shot, {**shot, "id": "S02", "index": 2, "action": "a scholar lifts one scroll"}]}}
    store.save(p)
    try:
        r = routes.picture_prompts("t-paper")
        body = r.body.decode()
        assert r.status_code == 200 and "attachment" in r.headers.get("content-disposition", "")
        parts = body.split("\n\n")
        assert len(parts) == 2                                 # one self-contained prompt per paragraph
        assert all(paper.LOOK_SHORT in x and "handcrafted" in x for x in parts)
    finally:
        store.delete("t-paper")


def test_stickman_offers_the_look() -> None:
    st = sstyles.get("b5-paper")
    assert st["id"] == "b5-paper" and st["fixed"]
    assert any(s["id"] == "b5-paper" for s in sstyles.public())
    lock = sprompts.style_lock({"style": "b5-paper"})
    assert "PAPER CRAFT" in lock and paper.TAIL in lock       # the craft belongs to the still
    assert "living paper poster" not in lock                  # and the motion to the clip prompt
    assert "PAPER CRAFT" not in sprompts.style_lock({"style": "a1-dark"})
    assert sprompts.is_paper({"style": "b5-paper"}) and not sprompts.is_paper({"style": "a1-dark"})


def test_company_story_backdrops_and_motion_are_paper() -> None:
    r = {"name": "Toyota"}
    sc = {"n": 2, "place": "a small garage", "visual": "a wooden loom", "purpose": "the start", "poses": ["thinking", "pointing"]}
    pic = CS.scene_prompt(r, sc)
    assert paper.LOOK_SHORT in pic and "paper" in pic.lower()
    assert len(pic) < 1800                                 # free picture services cut long prompts
    assert paper.NEGATIVE in CS.NEGATIVE
    assert "cardstock" in CS.motion_prompt(sc)
    assert "assembling itself" in CS.motion_prompt({**sc, "n": 1})     # only the first scene builds itself
    assert "assembling itself" not in CS.motion_prompt(sc)
