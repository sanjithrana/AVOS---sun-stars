"""The three things that made a real eleven-shot run come out badly, each now checked.

Measured on that run: nine of eleven shots on the cutting board, four pairs where the edit model handed back the
picture it was given, and a black band on ten of eleven frames.
"""
from __future__ import annotations

import io

from PIL import Image

from studio.skilllab import asmr_cooking as AC
from studio.skilllab import compose


def _png(size, fill, band: int = 0) -> bytes:
    im = Image.new("RGB", size, fill)
    if band:
        d = Image.new("RGB", (size[0], band), (0, 0, 0))
        im.paste(d, (0, 0)); im.paste(d, (0, size[1] - band))
    b = io.BytesIO(); im.save(b, "PNG"); return b.getvalue()


def test_the_video_has_to_cook_not_just_chop():
    shots = [{"where": "board", "stage": "prep", "n": i + 1} for i in range(11)]
    AC.balance(shots, 11)
    cooking = [sh for sh in shots if sh["where"] in ("stove", "plate")]
    assert len(cooking) >= round(11 * AC.COOKING_SHARE)
    assert shots[-1]["where"] == "plate" and shots[-1]["stage"] == "climax"
    assert shots[0]["where"] == "board"                        # shot one still lays the ingredients out


def test_a_writer_that_already_got_it_right_is_left_alone():
    shots = ([{"where": "board", "stage": "prep", "n": 1}, {"where": "board", "stage": "prep", "n": 2}]
             + [{"where": "stove", "stage": "climax", "n": i} for i in range(3, 8)])
    AC.balance(shots, 7)
    assert [sh["where"] for sh in shots[:6]] == ["board", "board", "stove", "stove", "stove", "stove"]


def test_no_shot_is_more_than_two_edits_away_from_a_fresh_drawing():
    shots = [{"where": "board", "stage": "prep", "n": i + 1} for i in range(11)]
    AC.balance(shots, 11)
    run = 0
    for sh in shots:
        run = 0 if sh["fresh"] else run + 1
        assert run <= AC.MAX_CHAIN, f"shot {sh['n']} is {run} edits deep: that is how eleven shots become one"
    assert shots[0]["fresh"]


def test_the_prompt_names_the_instant_to_photograph():
    for action in ("the knife slices through the onion", "dicing the tomato", "she cuts the paneer"):
        assert "mid-stroke" in AC.peak_of(action), action     # "slices" and "slicing" both, not just one of them
    for action in ("pouring the cream in", "drizzles ghee over the top"):
        assert "mid-pour" in AC.peak_of(action), action
    assert "peak of the movement" in AC.peak_of("the hands fold the dough")


def test_what_is_already_used_is_named_as_out_of_frame():
    sh = {"camera": "top-down", "where": "board", "subject": "one red onion", "action": "the knife slices the onion",
          "physics": "", "state": "the ginger, still whole", "gone": "the tomato, now in the pan", "asmr": "thud"}
    out = AC.image_prompt({}, sh, "9:16")
    assert "OUT OF FRAME" in out and "the tomato" in out
    assert "mid-stroke" in out and out.count("9:16") == 1
    assert len(out) <= 900                                     # Pollinations cuts a prompt there
    assert AC.NEVER.split(",")[0] in out                       # the rules survive the trim


def test_a_black_band_is_cut_off_rather_than_shipped():
    raw = _png((720, 1280), (190, 170, 150), band=200)
    out = compose.fill(raw, 720, 1280)
    im = Image.open(io.BytesIO(out))
    assert im.size == (720, 1280)
    g = im.convert("L")
    assert all(sum(g.crop((0, y, 720, y + 1)).getdata()) / 720 > 100 for y in (2, 640, 1277))


def test_a_genuinely_dark_picture_keeps_its_shadows():
    raw = _png((720, 1280), (6, 6, 8))
    im = Image.open(io.BytesIO(compose.fill(raw, 720, 1280)))
    assert im.size == (720, 1280)                              # left alone, not cropped to nothing


def test_the_same_picture_twice_is_caught():
    a = _png((720, 1280), (190, 170, 150))
    assert compose.too_same(a, a) and compose.sameness(a, a) == 1.0
    assert not compose.too_same(a, _png((720, 1280), (20, 30, 60)))
