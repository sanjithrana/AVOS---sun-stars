"""Film Style: 66 looks, one implementation, and a prompt that never loses the shot."""
from __future__ import annotations

import re

import pytest

from studio.skilllab import film_style as FS
from studio.skilllab.filmstyles import STYLES
from studio.skilllab.filmstyles_extra import EXTRA
from studio.skilllab import pipeline, takes

SHOT = {"n": 3, "title": "The dial hits zero", "subject": "a brass lift dial and a gloved hand",
        "action": "the hand closes the dial to zero", "camera": "extreme-close",
        "light": "a single bulb above, hard from the left", "beat": "turn"}


def test_every_style_becomes_its_own_skill():
    sk = FS.skills()
    assert len(sk) == len(STYLES) == 66 + len(EXTRA)
    assert all(sid.startswith(FS.PREFIX) for sid in sk)
    assert len({s.INFO["name"] for s in sk.values()}) == len(STYLES)
    assert len({s.INFO["group"] for s in sk.values()}) > 5          # grouped in the tab, not one flat list of 66


def test_all_66_reach_the_pipeline():
    for sid in FS.skills():
        assert sid in pipeline.SKILLS
        spec = pipeline.spec_of({"skill": sid})
        assert spec["stages"] == FS.STAGES
        assert set(spec["run"]) == set(FS.STAGES)


@pytest.mark.parametrize("slug", sorted(FS.STYLES))
def test_the_prompt_keeps_the_shot_and_fits_the_budget(slug):
    """An earlier version gave the look the whole budget and every shot of a film came out identical."""
    p = FS.image_prompt(FS.STYLES[slug], SHOT, "16:9")
    assert len(p) <= 900, f"{slug}: Pollinations cuts the prompt here"
    assert "brass lift dial" in p, f"{slug}: the subject was trimmed off the end"
    assert "closes the dial to zero" in p, f"{slug}: the action was trimmed off the end"
    assert "extreme close shot" in p


def test_two_styles_do_not_produce_the_same_prompt():
    seen = {FS.image_prompt(st, SHOT, "16:9") for st in FS.STYLES.values()}
    assert len(seen) == len(STYLES)


def test_no_real_artist_or_film_is_named_in_any_prompt():
    """The library names real artists as grammar. Those names must not reach a picture model."""
    blob = " ".join(FS.image_prompt(st, SHOT, "16:9") for st in FS.STYLES.values())
    for name in ("Cassandre", "Lempicka", "Busby", "Berkeley", "Gatsby", "Hitchcock", "Miyazaki", "Disney", "Pixar"):
        assert name not in blob, f"{name} reached a prompt"


def test_build_notes_do_not_reach_the_prompt():
    """A style prompt is half art direction, half build notes. Only the first half means anything to a picture model."""
    junk = re.compile(r"source-over|globalComposite|framebuffer|\.mjs\b|\bmix\(|[Π∑÷]"
                      r"|(?<!\d)×(?!\d)")        # "320x180 pixels" is a look, not a formula
    bad = [s for s in FS.STYLES if junk.search(FS.image_prompt(FS.STYLES[s], SHOT, "16:9"))]
    assert not bad, bad


def test_a_short_or_broken_plan_is_repaired_not_trusted():
    st = FS.STYLES["art-deco"]
    got = FS.norm_plan({"shots": [{"n": 1, "camera": "zoom"}]}, "a late-night launch", st, 6)
    assert len(got["shots"]) == 6                                   # padded rather than failing the run
    cams = [s["camera"] for s in got["shots"]]
    assert all(a != b for a, b in zip(cams, cams[1:])), "the same camera twice running"
    assert got["shots"][-1]["beat"] == "land"
    assert FS.norm_plan("not a plan at all", "x", st, 4)["shots"][0]["n"] == 1


def test_no_shot_is_more_than_two_edits_from_a_fresh_drawing():
    got = FS.norm_plan({"shots": [{"n": i + 1} for i in range(12)]}, "x", FS.STYLES["art-deco"], 12)
    run = 0
    for sh in got["shots"]:
        run = 0 if sh["fresh"] else run + 1
        assert run <= FS.MAX_CHAIN
    assert got["shots"][0]["fresh"]


def test_lengths_and_shot_counts_line_up():
    for n in FS.LENGTHS:
        shots = FS.shots_for(n)
        each = FS.seconds_each(n, shots)
        assert 3 <= shots <= 14
        assert FS.SHOT_SECONDS[0] <= each <= FS.SHOT_SECONDS[1]
    sk = FS.skills()["film-art-deco"]
    assert sk.INFO["default_seconds"] in sk.INFO["seconds"]
    assert sk.INFO["aspect"] in sk.INFO["aspects"]


def test_the_style_is_read_off_the_skill_id():
    assert FS.slug_of({"skill": "film-risograph"}) == "risograph"
    assert FS.style_of({"skill": "film-risograph"})["name"] == "Risograph Print"
    assert FS.style_of({"skill": "nonsense"}), "an unknown id still has to return a style, not crash a run"


def test_redoing_one_shot_keeps_the_rest():
    shots = [{"n": i + 1} for i in range(6)]
    for sh in shots:
        takes.add(sh, "picture", f"S{sh['n']:02d}.png")
    p = {"plan": {"shots": shots}, "steps": {s: {} for s in FS.STAGES}, "video": "final.mp4"}
    FS.reset(p, "pictures", n=3)
    assert shots[2]["picture"] is None
    assert [sh["picture"] for sh in shots if sh["n"] != 3] == [f"S{i:02d}.png" for i in (1, 2, 4, 5, 6)]
    assert len(takes.listing(shots[2], "picture")) == 1          # still there to go back to


# ---------- what the "engineering" run got wrong, each now checked ----------
# A real run of film-blueprint returned six photoreal stock pictures of men in hard hats, with a flat 30-second
# drone under them. Four separate bugs, one test each.

def test_a_drawing_style_says_so_before_anything_else():
    """"Engineering" beat a paragraph of art direction, so the medium now leads and cannot be trimmed off."""
    phrase, photoreal = FS.medium_of(FS.STYLES["blueprint"])
    assert not photoreal and "DRAWING" in phrase
    p = FS.image_prompt(FS.STYLES["blueprint"], {"n": 1, "subject": "engineering", "action": "held still",
                                                 "camera": "wide", "light": "key"}, "9:16")
    assert p.startswith("A DRAWING"), p[:60]
    assert p.rstrip().endswith("Not a photograph.")


def test_a_photoreal_style_is_not_told_it_is_a_drawing():
    photo = [s for s in FS.STYLES if FS.medium_of(FS.STYLES[s])[1]]
    assert photo, "some of these styles really are footage"
    for slug in photo:
        assert FS.medium_of(FS.STYLES[slug])[0] == ""
        assert "Not a photograph" not in FS.image_prompt(
            FS.STYLES[slug], {"n": 1, "subject": "x", "action": "y", "camera": "wide", "light": "k"}, "16:9")


def test_the_photo_words_go_in_the_negative_where_they_are_free():
    """The negative list is its own field, so it costs no prompt budget. Every drawn style gets the photo words."""
    assert "stock photo" in FS.negative_for(FS.STYLES["blueprint"])
    for slug, st in FS.STYLES.items():
        drawn = not FS.medium_of(st)[1]
        assert ("stock photo" in FS.negative_for(st)) is drawn, slug


def test_the_fallback_plan_sets_fresh_so_one_bad_shot_is_not_the_whole_film():
    plan = FS.fallback_plan("engineering", FS.STYLES["blueprint"], 6)
    assert plan["by_ai"] is False
    assert plan["shots"][0]["fresh"]
    run = 0
    for sh in plan["shots"]:
        run = 0 if sh["fresh"] else run + 1
        assert run <= FS.MAX_CHAIN, "this is how five of six shots came from one bad opening picture"
    assert len({sh["camera"] for sh in plan["shots"]}) >= 4, "six identical cameras give six identical shots"
    assert len({sh["subject"] for sh in plan["shots"]}) == 6
    assert "seen plainly, held still" not in plan["shots"][0]["subject"]


def test_a_look_that_wants_a_score_is_not_handed_to_the_kitchen_synthesiser():
    how, _cue = FS.sound_plan(FS.STYLES["blueprint"], {"action": "a line draws itself"})
    assert how == "music", "harpsichord and bassoon fell through to foley's default 'stir' and became a drone"
    how2, cue2 = FS.sound_plan({"sound": ["a knife chopping on a board"]}, {"action": "chopping"})
    assert how2 == "foley" and cue2


def test_room_tone_is_quiet_where_a_cue_is_loud():
    import array
    import io
    import math
    import wave

    from studio.skilllab import foley

    def rms(b: bytes) -> float:
        w = wave.open(io.BytesIO(b))
        a = array.array("h")
        a.frombytes(w.readframes(w.getnframes()))
        return math.sqrt(sum(x * x for x in a) / len(a)) / 327.67

    quiet, loud = rms(foley.room(2.0, 1)), rms(foley.wav("the knife chops", 2.0, 1))
    assert quiet < loud / 5, f"room tone {quiet:.2f} must sit well under a cue {loud:.2f}"
    assert quiet > 0, "and not be digital silence, which some editors treat as no track at all"


def test_the_added_looks_are_complete_and_say_what_medium_they_are():
    for slug, st in EXTRA.items():
        assert slug in STYLES and FS.PREFIX + slug in FS.skills()
        for key in ("name", "cat", "line", "uses", "quote", "essence", "nots", "material", "colour", "motion", "camera", "sound"):
            assert st.get(key), (slug, key)
        medium, photoreal = FS.medium_of(st)
        assert not photoreal, slug
        assert medium or slug == "layered-motion", slug     # a picture model is told its medium; flat vector motion graphics have no fitting one
        assert len(FS.look_of(st)) < 1100, slug           # fits the picture prompt budget once trimmed
    assert "cold open" in EXTRA["explainer-collage"]["essence"]
    assert len(EXTRA) == 10
