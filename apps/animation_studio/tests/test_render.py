"""The 2D engine: every look draws a real frame, framing keeps the subject in, whiteboard draws itself on."""
from __future__ import annotations

import numpy as np
import pytest

from studio.render import engines, rig, scene

PLAN = {"title": "Test", "look": {"palette": ["#1B1F3B", "#FFF3C4", "#FFB347", "#7EC8E3", "#E86A92"]}, "format": {"width": 1280, "height": 720, "fps": 24}}
CAST = {"luna": rig.from_description("luna", "Luna", "a small girl, long black hair, yellow raincoat"),
        "pip": rig.from_description("pip", "Pip", "a round orange cat")}


def spec(**over) -> dict:
    shot = {"id": "S1", "start_s": 0, "end_s": 3, "summary": "Luna waves at the moon", "camera": {"move": "dolly_in", "from": {"fill": 0.5}, "to": {"fill": 0.7}},
            "scene": {"setting": "park", "time": "night", "actors": [{"cast": "luna", "action": "wave"}, {"cast": "pip", "action": "idle"}],
                      "props": [{"kind": "moon", "x": 0.84, "y": 0.17, "scale": 0.15}]},
            "text_overlay": [{"text": "Hello moon!", "position": "bottom", "at": [0.2, 2.8]}]}
    shot.update(over)
    return scene.normalize_spec(None, scene.draft_spec(shot, PLAN, list(CAST)), list(CAST))


def frame(engine: str, sp: dict, t: float = 1.5, W: int = 640, H: int = 360):
    ctx = scene.make_ctx(PLAN, CAST, W, H, engines.look(engine))
    return scene.render_frame(sp, ctx, t, int(t * 24))


@pytest.mark.parametrize("engine", list(engines.ENGINES))
def test_every_look_draws_the_scene(engine):
    img, m = frame(engine, spec())
    assert img.shape == (360, 640, 3) and img.dtype == np.uint8
    assert img.std() > 20                                    # a real picture, not a flat colour
    assert len(m["actors"]) == 2 and len(m["texts"]) == 1
    for a in m["actors"]:                                    # both characters visible
        x0, y0, x1, y1 = a["box"]
        assert x1 > 0 and x0 < 640 and y1 > 0 and y0 < 360


def test_characters_get_their_own_places():
    _, m = frame("hyperframes", spec())
    a, b = m["actors"]
    assert abs((a["box"][0] + a["box"][2]) / 2 - (b["box"][0] + b["box"][2]) / 2) > 80


@pytest.mark.parametrize("action", ["fall", "sit", "jump", "cheer"])
def test_camera_keeps_the_subject_in_frame(action):
    sp = spec(scene={"setting": "park", "time": "day", "actors": [{"cast": "luna", "action": action, "scale": 0.6}]},
              camera={"move": "dolly_in", "from": {"fill": 0.7}, "to": {"fill": 0.85}})
    for t in (0.2, 1.5, 2.8):
        _, m = frame("anime-cel", sp, t)
        x0, y0, x1, y1 = m["actors"][0]["box"]
        assert x0 > -12 and y0 > -12 and x1 < 652 and y1 < 372, (action, t, m["actors"][0]["box"])


def test_whiteboard_draws_itself_on():
    sp = spec()
    sp["reveal"] = True
    early, _ = frame("whiteboard", sp, 0.15)
    done, _ = frame("whiteboard", sp, 2.9)
    ink = lambda im: (im.mean(axis=2) < 120).mean()   # dark marker pixels
    assert ink(early) < ink(done) * 0.7
    sp["reveal"] = False                                       # same setting as the shot before: already on the board
    again, _ = frame("whiteboard", sp, 0.15)
    assert ink(again) > ink(early) * 1.4


def test_pixel_captions_are_drawn_sharp_at_full_size():
    _, m = frame("pixel-art", spec())
    assert m["texts"][0]["size_px"] >= 0.05 * 360


def test_no_second_moon_when_the_shot_has_one():
    sp = spec()
    sp["props"] = [{**sp["props"][0], "x": 0.16}]           # the shot's own moon, top-left
    with_prop, _ = frame("hyperframes", sp)
    sp["props"] = []
    without, _ = frame("hyperframes", sp)                  # no moon prop: the night sky draws its own, top-right
    corner = lambda im: (im[15:110, 470:640].mean(axis=2) > 170).mean()
    assert corner(without) > 0.01
    assert corner(with_prop) < corner(without) * 0.3
