import io

from PIL import Image

from studio.explainer import contactsheet, engines, planner, spec


def _png(c, w=640, h=360):
    b = io.BytesIO()
    Image.new("RGB", (w, h), c).save(b, "PNG")
    return b.getvalue()


def _plan():
    return spec.norm_plan(planner.builtin("a magnet in a copper pipe", 30, "16:9"), 30, "16:9")


def test_film_fields_and_palette_survive_the_plan():
    pl = _plan()
    s = pl["shots"][0]
    assert s["cam_note"] and s["lighting"] and s["audio"]
    assert pl["palette"][0]["hex"].startswith("#") and len(pl["palette"][0]["hex"]) == 7
    assert spec.norm_palette(["B87333", {"name": "x", "hex": "nope"}, "#00d2ff"]) == [
        {"name": "Colour 1", "hex": "#B87333"}, {"name": "Colour 3", "hex": "#00D2FF"}]


def test_picture_prompt_carries_camera_lighting_mood_and_palette():
    pl = _plan()
    pl["shots"][0].update({"mood": "intrigued", "lighting": "warm window light"})
    p = {"plan": pl, "style": ""}
    txt = engines.shot_prompt(p, pl["shots"][0])
    for want in (pl["shots"][0]["cam_note"], "lighting: warm window light", "mood: intrigued", pl["palette"][0]["hex"]):
        assert want in txt
    assert "key visual" in engines.poster_prompt(p).lower()


def test_board_builds_with_and_without_pictures():
    pl = _plan()
    n = len(pl["shots"])
    full = contactsheet.board(pl, [_png((90, 60, 40))] * n, _png((50, 40, 80)), [_png((230, 220, 200))], _png((100, 140, 100)), [_png((200, 180, 160), 300, 300)], "16:9")
    empty = contactsheet.board(pl, [None] * n, None, None, None, None, "9:16")
    for data in (full, empty):
        im = Image.open(io.BytesIO(data))
        assert im.width == 2400 and im.height > 1500
