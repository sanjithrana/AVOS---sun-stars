"""Shot specs → frames.

A shot spec is what a builder writes for one shot: setting, actors (cast id, place, action, expression, entrances),
props, on-screen text, effects and a camera move that copies the reference shot. The renderer draws it with the
project's engine and reports what it drew (actor/text boxes) so reviewers can measure, not guess.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import skia

from . import actions, rig
from .backgrounds import SETTINGS, Background, guess_setting, guess_time
from .color import mix, norm, palette_roles, shade, skc
from .fx import FX, draw_fx, guess_fx, pixelate, post
from .pen import Pen
from .props import KINDS as PROP_KINDS, draw_prop, guess_props, place_props
from .text import draw_line, measure, typeface, wrap

MOVES = ("static", "dolly_in", "dolly_out", "zoom_in", "zoom_out", "pan", "pan_left", "pan_right", "tilt", "tilt_up", "tilt_down",
         "orbit", "crane_up", "crane_down", "shake", "push_reveal", "rack_focus", "macro_slide", "whip")
TRANSITIONS = ("cut", "fade", "dissolve", "wipe", "wipeleft", "wiperight", "slide", "circle", "zoom", "whip", "pixelize", "flash", "smash")
POSITIONS = ("bottom", "top", "center", "left", "right", "upper_left", "upper_right")


def _f(v: Any, d: float, lo: float | None = None, hi: float | None = None) -> float:
    try:
        x = float(v)
        if math.isnan(x):
            raise ValueError
    except (TypeError, ValueError):
        x = d
    if lo is not None:
        x = max(lo, x)
    if hi is not None:
        x = min(hi, x)
    return x


def _move(v: Any) -> str:
    s = str(v or "static").lower().replace("-", "_").replace(" ", "_")
    s = {"push_in": "dolly_in", "pull_out": "dolly_out", "push": "dolly_in", "pull": "dolly_out", "still": "static", "zoom": "zoom_in",
         "track": "pan", "truck": "pan", "dolly": "dolly_in", "handheld": "shake", "推近": "dolly_in", "拉遠": "dolly_out", "平移": "pan",
         "環繞": "orbit", "固定": "static", "靜止": "static", "晃動": "shake"}.get(s, s)
    return s if s in MOVES else "static"


def normalize_spec(raw: dict | None, base: dict, cast_ids: list[str]) -> dict:
    """Clamp an (AI-written) shot spec into something the renderer can always draw. `base` is the engine's own draft."""
    r = raw if isinstance(raw, dict) else {}
    out = dict(base)
    out["duration"] = _f(base.get("duration"), 3.0, 0.4, 30.0)
    s = str(r.get("setting") or base.get("setting") or "room").lower()
    out["setting"] = s if s in SETTINGS else guess_setting(s, base.get("setting") or "room")
    tm = str(r.get("time") or base.get("time") or "day").lower()
    out["time"] = tm if tm in ("day", "sunset", "night") else "day"
    actors = []
    for a in (r.get("actors") if isinstance(r.get("actors"), list) else base.get("actors") or [])[:4]:
        if not isinstance(a, dict):
            continue
        cid = str(a.get("cast") or a.get("id") or "")
        if cid not in cast_ids:
            cid = cast_ids[len(actors) % len(cast_ids)] if cast_ids else ""
        if not cid:
            continue
        actors.append({
            "cast": cid, "x": _f(a.get("x"), 0.5, -0.3, 1.3), "y": _f(a.get("y"), 0.0, -0.2, 0.6),
            "scale": _f(a.get("scale"), 0.5, 0.12, 1.6), "facing": -1 if str(a.get("facing", "")).lower() in ("left", "-1", "l") or a.get("facing") == -1 else 1,
            "action": actions.canon(a.get("action")), "expression": a.get("expression") if a.get("expression") in rig.EXPRESSIONS else None,
            "enter": a.get("enter") if a.get("enter") in ("left", "right") else None,
            "exit": a.get("exit") if a.get("exit") in ("left", "right") else None,
            "turn": _f(a.get("turn"), -1, -1, 1),
        })
    out["actors"] = actors
    props = []
    for p in (r.get("props") if isinstance(r.get("props"), list) else base.get("props") or [])[:6]:
        if not isinstance(p, dict):
            continue
        k = str(p.get("kind") or "").lower()
        if k not in PROP_KINDS:
            g = guess_props(k, 1)
            if not g:
                continue
            k = g[0]
        props.append({"kind": k, "x": _f(p.get("x"), 0.7, -0.2, 1.2), "y": _f(p.get("y"), 0.6, -0.2, 1.2), "scale": _f(p.get("scale"), 0.16, 0.04, 0.9),
                      "anim": p.get("anim") if p.get("anim") in ("float", "spin", "pop", "bounce", "shake", "none", "fall") else "float",
                      "color": norm(p["color"]) if p.get("color") else "", "front": bool(p.get("front"))})
    out["props"] = props
    texts = []
    for t in (r.get("text") if isinstance(r.get("text"), list) else base.get("text") or [])[:4]:
        if isinstance(t, str):
            t = {"text": t}
        if not isinstance(t, dict) or not str(t.get("text") or "").strip():
            continue
        at = t.get("at") if isinstance(t.get("at"), (list, tuple)) and len(t.get("at")) == 2 else [0.15, out["duration"] - 0.15]
        a0, a1 = _f(at[0], 0.0, 0, out["duration"]), _f(at[1], out["duration"], 0, out["duration"])
        pos = str(t.get("position") or "bottom").lower()
        pos = next((p for p in POSITIONS if p in pos.replace(" ", "_")), "center" if "中" in pos else "bottom")
        if pos == "center" and actors and str(t.get("style") or "title") == "title":
            pos = "top"   # a centred title would sit on the character's face
        texts.append({"text": str(t["text"])[:140], "at": [min(a0, a1), max(a0, a1) if a1 > a0 else out["duration"]], "position": pos,
                      "size": _f(t.get("size"), 0.075 if pos != "center" else 0.11, 0.045, 0.2),
                      "style": t.get("style") if t.get("style") in ("caption", "title", "label") else ("title" if pos == "center" else "caption"),
                      "anim": t.get("anim") if t.get("anim") in ("pop", "fade", "slide", "type", "bounce", "none") else "pop"})
    out["text"] = texts
    cam = r.get("camera") if isinstance(r.get("camera"), dict) else base.get("camera") or {}
    bcam = base.get("camera") or {}
    out["camera"] = {"move": _move(cam.get("move") or bcam.get("move")), "pace": cam.get("pace") if cam.get("pace") in ("slow", "medium", "fast") else bcam.get("pace", "medium"),
                     "from": {"fill": _f((cam.get("from") or {}).get("fill"), _f((bcam.get("from") or {}).get("fill"), 0.5), 0.1, 1.6)},
                     "to": {"fill": _f((cam.get("to") or {}).get("fill"), _f((bcam.get("to") or {}).get("fill"), 0.5), 0.1, 1.6)},
                     "focus": cam.get("focus") if cam.get("focus") in cast_ids else (bcam.get("focus") if bcam.get("focus") in cast_ids else None),
                     "direction": cam.get("direction") if cam.get("direction") in ("left", "right", "up", "down") else bcam.get("direction")}
    fx = r.get("fx") if isinstance(r.get("fx"), list) else base.get("fx") or []
    out["fx"] = [f for f in fx if f in FX][:3]
    tr = str(r.get("transition_in") or base.get("transition_in") or "cut").lower()
    out["transition_in"] = next((x for x in TRANSITIONS if x in tr), "cut")
    out["narration"] = str(r.get("narration") if r.get("narration") is not None else base.get("narration") or "")[:400]
    out["bg_color"] = base.get("bg_color")
    return out


def draft_spec(shot: dict, plan: dict, cast_ids: list[str], seed: int = 0) -> dict:
    """The engine's own reading of a plan shot (used as-is without AI, and as the AI builder's starting point)."""
    txt = " ".join(str(shot.get(k) or "") for k in ("summary", "action", "notes")) + " " + " ".join(shot.get("reads") or [])
    scene = shot.get("scene") if isinstance(shot.get("scene"), dict) else {}
    dur = max(0.4, _f(shot.get("end_s"), 3) - _f(shot.get("start_s"), 0))
    setting = scene.get("setting") if scene.get("setting") in SETTINGS else guess_setting(txt, (plan.get("_default_setting") or "room"))
    cam = shot.get("camera") if isinstance(shot.get("camera"), dict) else {}
    move = _move(cam.get("move") or (shot.get("camera") if isinstance(shot.get("camera"), str) else None))
    present = [a for a in (scene.get("actors") or []) if isinstance(a, dict)]
    if not present:
        mentioned = [c["id"] for c in plan.get("characters") or [] if isinstance(c, dict) and c.get("id") and
                     (c["id"].lower() in txt.lower() or str(c.get("name") or "@@").lower() in txt.lower())]
        ids = mentioned or (cast_ids[:1] if cast_ids and not re.search(r"title|logo|字卡|片名|card|text only|空景|establishing", txt.lower()) else [])
        acts = re.findall(r"[a-z]+|[一-鿿]{1,2}", txt.lower())
        act = next((actions.canon(w) for w in acts if actions.canon(w) != "idle"), "idle")
        n = len(ids)
        present = [{"cast": cid, "x": 0.5 if n == 1 else 0.33 + 0.34 * i / max(1, n - 1), "action": act if i == 0 else "idle",
                    "facing": 1 if (n == 1 or i == 0) else -1} for i, cid in enumerate(ids[:3])]
    n_act = len(present)
    present = [dict(a) for a in present]
    for i, a in enumerate(present):
        if a.get("x") is None:
            a["x"] = 0.5 if n_act == 1 else 0.3 + 0.4 * i / max(1, n_act - 1)
            a.setdefault("facing", 1 if i == 0 or n_act == 1 else -1)
    fill_from = _f((cam.get("from") or {}).get("fill"), 0.55)
    fill_to = _f((cam.get("to") or {}).get("fill"), fill_from)
    base_scale = 0.5 if len(present) <= 1 else 0.42
    for a in present:
        a.setdefault("scale", base_scale)
    char_words = " ".join(str(c.get("design") or "") + " " + str(c.get("name") or "") for c in plan.get("characters") or [] if isinstance(c, dict)).lower()
    guessed = [k for k in guess_props(txt, 3) if not (k in ("cat", "dog", "bird", "fish") and re.search(k, char_words))][:2]
    props = scene.get("props") or place_props(guessed)
    texts = []
    for t in shot.get("text_overlay") or []:
        if isinstance(t, dict) and t.get("text"):
            texts.append(t)
    return {
        "id": shot.get("id"), "duration": dur, "start": _f(shot.get("start_s"), 0), "setting": setting, "time": scene.get("time") or guess_time(txt),
        "actors": present, "props": props, "text": texts,
        "camera": {"move": move, "pace": cam.get("pace") or "medium", "from": {"fill": fill_from}, "to": {"fill": fill_to},
                   "direction": cam.get("direction")},
        "fx": scene.get("fx") or guess_fx(txt), "transition_in": shot.get("transition_in") or "cut",
        "narration": shot.get("narration") or "",
    }


@dataclass
class Ctx:
    W: int
    H: int
    lk: dict
    roles: dict
    cast: dict
    lyrics: list = field(default_factory=list)
    bpm: float | None = None
    caption_style: dict = field(default_factory=dict)
    plate: Any = None          # optional AI background image (skia.Image)
    seed: int = 1
    extra_colors: list = field(default_factory=list)


def _ease(x: float, pace: str) -> float:
    x = max(0.0, min(1.0, x))
    if pace == "fast":
        return 1 - (1 - x) ** 3
    if pace == "slow":
        return x * x * (3 - 2 * x)
    return 0.5 - 0.5 * math.cos(math.pi * x)


LOW_POSES = {"fall": 0.55, "sit": 0.72, "sleep": 0.5, "lie": 0.45, "crawl": 0.6, "cry": 0.95}


def camera_at(spec: dict, t: float, ctx: Ctx, focus_pt: tuple[float, float],
              subject: tuple[float, float, float, float] | None = None) -> tuple[float, float, float, float]:
    """(zoom, focus_x, focus_y, roll) for time t. Focus is in world px."""
    cam = spec["camera"]
    W, H = ctx.W, ctx.H
    d = max(0.01, spec["duration"])
    u = _ease(t / d, cam.get("pace", "medium"))
    mv = cam["move"]
    main_scale = (spec["actors"][0]["scale"] if spec["actors"] else 0.5)
    z0 = max(0.75, min(3.2, cam["from"]["fill"] / max(0.12, main_scale)))
    z1 = max(0.75, min(3.2, cam["to"]["fill"] / max(0.12, main_scale)))
    if not spec["actors"]:
        z0, z1 = 1.0, 1.0
    k = {"slow": 0.6, "medium": 1.0, "fast": 1.6}.get(cam.get("pace", "medium"), 1.0)
    fx, fy = W / 2, H / 2
    roll = 0.0
    if mv in ("dolly_in", "zoom_in", "push_reveal"):
        if abs(z1 - z0) < 0.05:
            z1 = z0 * (1 + 0.18 * k)
        z = z0 + (z1 - z0) * u
    elif mv in ("dolly_out", "zoom_out"):
        if abs(z1 - z0) < 0.05:
            z0 = z1 * (1 + 0.18 * k)
        z = max(z0, z1) + (min(z0, z1) - max(z0, z1)) * u
    elif mv == "macro_slide":
        z = max(z0, 1.8)
        fx += (u - 0.5) * W * 0.16 * k
    else:
        z = z0 + (z1 - z0) * u
    if mv in ("pan", "pan_left", "pan_right", "orbit", "whip"):
        dirn = -1 if (mv == "pan_left" or cam.get("direction") == "left") else 1
        span = W * (0.14 if mv != "whip" else 0.4) * k
        fx += dirn * (u - 0.5) * span
        if mv == "orbit":
            z *= 1 + 0.06 * math.sin(u * math.pi)
            roll = 1.2 * math.sin(u * math.pi * 2)
    if mv in ("tilt", "tilt_up", "tilt_down", "crane_up", "crane_down"):
        dirn = -1 if (mv in ("tilt_up", "crane_up") or cam.get("direction") == "up") else 1
        fy += dirn * (u - 0.5) * H * 0.12 * k
    if mv == "static":
        z *= 1 + 0.012 * math.sin(t * 0.6)
    if mv == "shake" or "shake" in spec.get("fx", []):
        amp = H * 0.006 * k
        fx += amp * math.sin(t * 37.0) + amp * 0.5 * math.sin(t * 71)
        fy += amp * math.cos(t * 43.0)
    # move the focus toward the subject as we zoom in
    w = max(0.0, min(1.0, (z - 1.0) / 0.9))
    fx = fx + (focus_pt[0] - W / 2) * w
    fy = fy + (focus_pt[1] - H / 2) * w
    if subject and spec["actors"]:
        # framing safety: the planned fill can never push the subject out of the picture. Up to fill 0.9 the whole
        # body (and every actor) stays in frame; closer than that it's a deliberate close-up and the face stays in.
        l, top, r, bot = subject
        fill = max(cam["from"]["fill"], cam["to"]["fill"])
        bh, bw = (bot - top) * 1.12, (r - l) * 1.1
        if fill <= 0.9:
            z = min(z, H / max(1.0, bh), W / max(1.0, bw))
        z = max(0.75, z)
        hh, hw = H / (2 * z), W / (2 * z)
        if bh <= 2 * hh:
            fy = min(max(fy, bot + (bot - top) * 0.04 - hh), top - (bot - top) * 0.06 + hh)
        else:
            fy = top - (bot - top) * 0.06 + hh
        if bw <= 2 * hw:
            fx = min(max(fx, r - hw), l + hw)
        else:
            fx = min(max(fx, focus_pt[0] - hw * 0.6), focus_pt[0] + hw * 0.6)
    return z, fx, fy, roll


def _apply_cam(c: skia.Canvas, ctx: Ctx, z: float, fx: float, fy: float, roll: float, f: float = 1.0) -> None:
    W, H = ctx.W, ctx.H
    zl = 1 + (z - 1) * f
    fxl = W / 2 + (fx - W / 2) * f
    fyl = H / 2 + (fy - H / 2) * f
    c.translate(W / 2, H / 2)
    if roll:
        c.rotate(roll * f)
    c.scale(zl, zl)
    c.translate(-fxl, -fyl)


def actor_state(a: dict, t: float, dur: float) -> tuple[float, str, int]:
    """(x fraction, action, facing) with entrances/exits."""
    x, act, facing = a["x"], a["action"], a["facing"]
    if a.get("enter"):
        T = min(dur * 0.45, 1.8)
        src = -0.18 if a["enter"] == "left" else 1.18
        if t < T:
            u = t / T
            x = src + (x - src) * (1 - (1 - u) ** 2)
            act = "run" if act == "run" else "walk"
            facing = 1 if a["enter"] == "left" else -1
    if a.get("exit"):
        T0 = dur - min(dur * 0.4, 1.6)
        dst = -0.2 if a["exit"] == "left" else 1.2
        if t > T0:
            u = (t - T0) / max(0.01, dur - T0)
            x = x + (dst - x) * u * u
            act = "run" if act == "run" else "walk"
            facing = -1 if a["exit"] == "left" else 1
    elif act in actions.MOVING and not a.get("enter"):
        x = x + (t - dur / 2) * actions.MOVING[act] * 0.35 * facing
    return x, act, facing


def _actor_box(ctx: Ctx, cd: dict, a: dict, x: float, act: str, facing: int, t: float, idx: int, dur: float, bg: Background) -> tuple[float, float, float, float]:
    """Where this actor will be drawn (world px), from a dry run of the rig on a recording canvas."""
    W, H = ctx.W, ctx.H
    hgt = a["scale"] * H * cd["height"]
    s = hgt / 100.0
    gx, gy = x * W, bg.ground_y - a["y"] * H
    rec = skia.PictureRecorder()
    cv = rec.beginRecording(skia.Rect.MakeWH(W, H))
    cv.translate(gx, gy)
    cv.scale(s * facing, s)
    pose = actions.pose_for(act, t + idx * 0.37, dur, ctx.bpm, seed=idx * 3 + len(a["cast"]))
    if a.get("turn", -1) >= 0 and act not in actions.MOVING:
        pose.turn = a["turn"]
    expr = a.get("expression") or actions.ACTION_EXPR.get(act, "happy")
    drawn = rig.draw(Pen(cv, {**ctx.lk, "reveal": False}, 0, aa=False), cd, pose, expr, t + idx, symbols=False)
    b = cv.getTotalMatrix().mapRect(drawn.bounds)
    rec.finishRecordingAsPicture()
    return (b.left(), b.top(), b.right(), b.bottom())


def _surface(w: int, h: int) -> skia.Surface:
    return skia.Surface.MakeRaster(skia.ImageInfo.Make(w, h, skia.kRGBA_8888_ColorType, skia.kPremul_AlphaType))


def render_frame(spec: dict, ctx: Ctx, t: float, frame: int, bg: Background | None = None) -> tuple[np.ndarray, dict]:
    lk = ctx.lk
    pixel = lk["look"] == "pixel"
    W, H = ctx.W, ctx.H
    if pixel:
        ph = int(lk.get("pixel_h", 180))
        pw = int(round(ph * W / H))
        surf = _surface(pw, ph)
    else:
        surf = _surface(W, H)
    c = surf.getCanvas()
    if pixel:
        c.scale(pw / W, ph / H)
    roles = ctx.roles
    white = lk["look"] == "whiteboard"
    c.clear(skc("#FFFFFF" if white else roles["light"]))
    bg = bg or Background(spec["setting"], roles, spec["time"], W, H, lk, seed=ctx.seed,
                          no_sky={p["kind"] for p in spec["props"] if p["kind"] in ("moon", "sun")})
    dur = spec["duration"]
    reveal = 1.0
    if white and spec.get("reveal", True):
        reveal = min(1.0, t / max(0.6, min(dur * 0.45, 2.2)))
    pen = Pen(c, lk, frame, aa=not pixel, line_color=roles["line"], reveal=reveal)
    # subject for the camera
    main = spec["actors"][0] if spec["actors"] else None
    focus = (W / 2, H / 2)
    if main:
        cd = ctx.cast.get(main["cast"])
        x, _, _ = actor_state(main, t, dur)
        hgt = main["scale"] * H * (cd["height"] if cd else 1.0)
        cam_focus = spec["camera"].get("focus")
        if cam_focus and cam_focus != main["cast"]:
            other = next((a for a in spec["actors"] if a["cast"] == cam_focus), None)
            if other:
                x, _, _ = actor_state(other, t, dur)
        fill_to = spec["camera"]["to"]["fill"]
        focus = (x * W, bg.ground_y - hgt * (0.72 if fill_to > 0.75 else 0.55) - main["y"] * H)
    subject = None
    if spec["actors"]:
        boxes = []
        for idx, a in enumerate(spec["actors"]):
            cd2 = ctx.cast.get(a["cast"])
            if not cd2:
                continue
            ax, aact, afacing = actor_state(a, t, dur)
            if ax < -0.05 or ax > 1.05:
                continue   # entering / leaving: don't chase it off screen
            boxes.append(_actor_box(ctx, cd2, a, ax, aact, afacing, t, idx, dur, bg))
        if boxes:
            subject = (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes))
            if main and LOW_POSES.get(actor_state(main, t, dur)[1]):
                focus = (focus[0], (subject[1] + subject[3]) / 2)
    z, fx, fy, roll = camera_at(spec, t, ctx, focus, subject)
    # ---- background layers ----
    for name, f in Background.LAYERS:
        c.save()
        _apply_cam(c, ctx, z, fx, fy, roll, f)
        if name == "back" and ctx.plate is not None:
            img = ctx.plate
            sc = max(W * 1.25 / img.width(), H * 1.25 / img.height())
            dw, dh = img.width() * sc, img.height() * sc
            c.drawImageRect(img, skia.Rect.MakeXYWH(W / 2 - dw / 2, H / 2 - dh / 2 - H * 0.05, dw, dh), skia.SamplingOptions(skia.FilterMode.kLinear))
        elif not (ctx.plate is not None and name in ("far", "mid")):
            bg.draw(name, c, pen, t)
        c.restore()
    # ---- world: props behind, actors, props in front ----
    metrics: dict = {"t": round(t, 3), "actors": [], "texts": [], "props": []}
    c.save()
    _apply_cam(c, ctx, z, fx, fy, roll, 1.0)
    total = c.getTotalMatrix()

    def draw_props(front: bool) -> None:
        for i, p in enumerate(spec["props"]):
            if bool(p.get("front")) != front:
                continue
            sz = p["scale"] * H
            px, py = p["x"] * W, p["y"] * H
            an = p["anim"]
            rot, sc = 0.0, 1.0
            if an == "float":
                py += math.sin(t * 2.2 + i) * H * 0.012
            elif an == "spin":
                rot = t * 90
            elif an == "pop":
                sc = actions.back(min(1.0, t / 0.35))
            elif an == "bounce":
                py -= abs(math.sin(t * 5 + i)) * H * 0.04
            elif an == "shake":
                rot = 8 * math.sin(t * 30)
            elif an == "fall":
                py = -H * 0.2 + (py + H * 0.2) * min(1.0, t / 0.6) ** 2
            c.save()
            c.translate(px, py)
            c.rotate(rot)
            c.scale(sz / 100 * sc, sz / 100 * sc)
            draw_prop(pen, p["kind"], p["color"], t, roles)
            m = c.getTotalMatrix().mapRect(skia.Rect.MakeLTRB(-50, -50, 50, 50))
            metrics["props"].append({"kind": p["kind"], "box": [m.left(), m.top(), m.right(), m.bottom()]})
            c.restore()
    draw_props(False)
    order = sorted(range(len(spec["actors"])), key=lambda i: spec["actors"][i]["y"] * -1 + spec["actors"][i]["scale"] * 0.01)
    for idx in order:
        a = spec["actors"][idx]
        cd = ctx.cast.get(a["cast"])
        if not cd:
            continue
        x, act, facing = actor_state(a, t, dur)
        hgt = a["scale"] * H * cd["height"]
        s = hgt / 100.0
        gx, gy = x * W, bg.ground_y - a["y"] * H
        if bg.has_ground() and not white and lk["look"] != "paper":
            sh = skia.Path()
            sh.addOval(skia.Rect.MakeLTRB(gx - hgt * 0.28, gy - hgt * 0.035, gx + hgt * 0.28, gy + hgt * 0.035))
            c.drawPath(sh, skia.Paint(AntiAlias=not pixel, Color=skc(roles["dark"], 0.16)))
        pose = actions.pose_for(act, t + idx * 0.37, dur, ctx.bpm, seed=idx * 3 + len(a["cast"]))
        if a.get("turn", -1) >= 0 and act not in actions.MOVING:
            pose.turn = a["turn"]
        expr = a.get("expression") or actions.ACTION_EXPR.get(act, "happy")
        c.save()
        c.translate(gx, gy)
        c.scale(s * facing, s)
        drawn = rig.draw(pen, cd, pose, expr, t + idx)
        m = c.getTotalMatrix()
        bb, hb = m.mapRect(drawn.bounds), m.mapRect(drawn.head)
        c.restore()
        metrics["actors"].append({"cast": a["cast"], "action": act, "expression": expr,
                                  "box": [bb.left(), bb.top(), bb.right(), bb.bottom()], "head": [hb.left(), hb.top(), hb.right(), hb.bottom()]})
    draw_props(True)
    c.restore()
    tip = pen.flush() if white else None
    # ---- screen space: effects, text, lyrics ----
    center = None
    if metrics["actors"]:
        hb = metrics["actors"][0]["head"]
        center = ((hb[0] + hb[2]) / 2, (hb[1] + hb[3]) / 2)
    for k in spec["fx"]:
        if k == "glow":
            continue
        draw_fx(c, k, t, W, H, ctx.seed + frame // max(1, lk.get("step", 1)) * 0, roles["all"], white, center)
    def draw_texts(cv: skia.Canvas) -> None:
        for tx in spec["text"]:
            box = draw_text(cv, tx, t, ctx, white)
            if box:
                metrics["texts"].append(box)
        if spec.get("narration") and ctx.caption_style.get("narration_captions", True):
            box = draw_text(cv, {"text": spec["narration"], "at": [0.0, dur], "position": "bottom", "size": 0.055, "style": "caption", "anim": "fade"}, t, ctx, white)
            if box:
                metrics["texts"].append(box)
        if ctx.lyrics:
            box = draw_lyrics(cv, ctx, spec.get("start", 0.0) + t, white)
            if box:
                metrics["texts"].append(box)
    if not pixel:
        draw_texts(c)
    if tip is not None and reveal < 1.0:
        _marker(c, tip, H)
    img = surf.makeImageSnapshot().toarray()[..., :3]
    if pixel:
        img = pixelate(np.ascontiguousarray(img), W, H, roles["all"] + ctx.extra_colors)
        # captions are drawn at full resolution on top (pixel font, crisp edges) so they stay readable on a phone
        full = _surface(W, H)
        fc = full.getCanvas()
        rgba = np.dstack([img, np.full(img.shape[:2], 255, np.uint8)])
        fc.drawImage(skia.Image.fromarray(np.ascontiguousarray(rgba), colorType=skia.kRGBA_8888_ColorType), 0, 0)
        draw_texts(fc)
        img = full.makeImageSnapshot().toarray()[..., :3]
        k = W / pw
        for group in ("actors", "props", "texts"):
            for it in metrics[group]:
                for key in ("box", "head"):
                    if key in it and group != "texts":
                        it[key] = [v * k for v in it[key]]
    out = post(np.ascontiguousarray(img), lk, frame, roles["all"])
    metrics["zoom"] = round(z, 3)
    return out, metrics


def _marker(c: skia.Canvas, tip: tuple[float, float], H: int) -> None:
    x, y = tip
    s = H * 0.0016
    c.save()
    c.translate(x, y)
    c.rotate(-35)
    body = skia.Path()
    body.addRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(-8 * s, 6 * s, 16 * s, 70 * s), 4 * s, 4 * s))
    c.drawPath(body, skia.Paint(AntiAlias=True, Color=skc("#3D5AFE")))
    nib = skia.Path()
    nib.moveTo(-6 * s, 6 * s)
    nib.lineTo(6 * s, 6 * s)
    nib.lineTo(0, -4 * s)
    nib.close()
    c.drawPath(nib, skia.Paint(AntiAlias=True, Color=skc("#232327")))
    hand = skia.Path()
    hand.addOval(skia.Rect.MakeXYWH(-16 * s, 40 * s, 32 * s, 40 * s))
    c.drawPath(hand, skia.Paint(AntiAlias=True, Color=skc("#FFD9B8")))
    c.drawPath(hand, skia.Paint(AntiAlias=True, Color=skc("#232327"), Style=skia.Paint.kStroke_Style, StrokeWidth=2 * s))
    c.restore()


def draw_text(c: skia.Canvas, tx: dict, t: float, ctx: Ctx, white: bool) -> dict | None:
    a0, a1 = tx["at"]
    if t < a0 or t > a1:
        return None
    W, H, lk = ctx.W, ctx.H, ctx.lk
    style = tx.get("style", "caption")
    font_name = lk.get("title_font") if style == "title" else lk.get("font")
    tf = typeface(font_name or "baloo-2")
    U = min(W, H)
    size = max(U * 0.05, tx.get("size", 0.07) * U)
    if style == "caption":
        size = max(U * 0.055, min(size, U * 0.085))
    max_w = W * (0.84 if tx["position"] in ("bottom", "top", "center") else 0.4)
    text = tx["text"]
    anim = tx.get("anim", "pop")
    local = t - a0
    if anim == "type":
        n = max(1, int(len(text) * min(1.0, local / max(0.3, min(1.2, (a1 - a0) * 0.5)))))
        text = text[:n]
    lines = wrap(text, tf, size, max_w)[:3]
    lh = size * 1.18
    block_h = lh * len(lines)
    pos = tx["position"]
    cx = {"left": W * 0.27, "upper_left": W * 0.27, "right": W * 0.73, "upper_right": W * 0.73}.get(pos, W / 2)
    if pos == "bottom":
        top = H * 0.93 - block_h
    elif pos in ("top", "upper_left", "upper_right"):
        top = H * 0.07
    else:
        top = H / 2 - block_h / 2
    sc, alpha, dy = 1.0, 1.0, 0.0
    if anim == "pop":
        sc = actions.back(min(1.0, local / 0.28), 2.2) if local < 0.28 else 1.0
        sc = max(0.01, sc)
    elif anim == "fade":
        alpha = min(1.0, local / 0.25, max(0.0, (a1 - t) / 0.25))
    elif anim == "slide":
        dy = (1 - min(1.0, local / 0.35)) ** 3 * H * 0.08
        alpha = min(1.0, local / 0.2)
    out_fade = min(1.0, max(0.0, (a1 - t) / 0.15))
    alpha *= out_fade
    pal = ctx.roles
    fill = "#232327" if white else ("#FFFFFF" if style != "title" else mix(pal["light"], "#FFFFFF", 0.6))
    stroke = "#FFFFFF" if white else (pal["dark"] if style != "title" else mix(pal["dark"], "#000000", 0.4))
    c.save()
    c.translate(cx, top + block_h / 2 + dy)
    c.scale(sc, sc)
    widths = [measure(ln, tf, size) for ln in lines]
    if style == "caption" and not white and lk["look"] not in ("pixel",):
        bw = max(widths) + size * 0.8
        bg = skia.Path()
        bg.addRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(-bw / 2, -block_h / 2 - size * 0.18, bw, block_h + size * 0.36), size * 0.3, size * 0.3))
        c.drawPath(bg, skia.Paint(AntiAlias=True, Color=skc(pal["dark"], 0.38 * alpha)))
    for i, ln in enumerate(lines):
        y = -block_h / 2 + lh * i + size * 0.92
        bounce = 0.0
        if anim == "bounce" and ctx.bpm:
            bounce = -abs(math.sin((t * ctx.bpm / 60) * math.pi)) * size * 0.08
        draw_line(c, ln, -widths[i] / 2, y + bounce, tf, size, fill, stroke, (size * 0.26 if white else size * 0.16) if stroke else 0, alpha, aa=lk["look"] != "pixel")
    c.restore()
    bw = max(widths) * sc
    return {"text": tx["text"][:40], "size_px": size * sc, "box": [cx - bw / 2, top + dy, cx + bw / 2, top + dy + block_h * sc],
            "style": style, "font": font_name}


def draw_lyrics(c: skia.Canvas, ctx: Ctx, gt: float, white: bool) -> dict | None:
    line = next((ln for ln in ctx.lyrics if ln.get("start", 0) <= gt < ln.get("end", 0)), None)
    if not line or not str(line.get("text") or "").strip():
        return None
    W, H, lk = ctx.W, ctx.H, ctx.lk
    tf = typeface(lk.get("font") or "baloo-2")
    size = min(W, H) * 0.06
    text = str(line["text"])
    lines = wrap(text, tf, size, W * 0.86)[:2]
    lh = size * 1.2
    top = H * 0.94 - lh * len(lines)
    prog = (gt - line["start"]) / max(0.2, line["end"] - line["start"])
    hi = ctx.roles["accent"] if not white else "#3D5AFE"
    total_w = sum(measure(ln, tf, size) for ln in lines)
    done_w = total_w * min(1.0, prog * 1.15)
    for i, ln in enumerate(lines):
        w = measure(ln, tf, size)
        x = W / 2 - w / 2
        y = top + lh * i + size * 0.92
        draw_line(c, ln, x, y, tf, size, "#FFFFFF" if not white else "#232327", None if white else "#1E1E24", size * 0.16, 1.0)
        if done_w > 0:
            c.save()
            c.clipRect(skia.Rect.MakeLTRB(x, y - size * 1.2, x + min(w, done_w), y + size * 0.4))
            draw_line(c, ln, x, y, tf, size, hi, None if white else "#1E1E24", size * 0.16, 1.0)
            c.restore()
        done_w -= w
    return {"text": text[:40], "size_px": size, "box": [W * 0.07, top, W * 0.93, top + lh * len(lines)], "style": "lyrics", "font": lk.get("font")}


def make_ctx(plan: dict, cast: dict, W: int, H: int, lk: dict, lyrics: list | None = None, plate: Any = None) -> Ctx:
    pal = (plan.get("look") or {}).get("palette") or []
    roles = palette_roles(pal)
    if lk["look"] == "whiteboard":
        roles = {**roles, "line": "#232327"}
    m = plan.get("music") or {}
    bpm = m.get("bpm") if isinstance(m.get("bpm"), (int, float)) else None
    extra = [v for cd in cast.values() for k, v in cd["colors"].items() if k in ("skin", "hair", "top", "bottom", "accent")]
    return Ctx(W=W, H=H, lk=lk, roles=roles, cast=cast, lyrics=lyrics or [], bpm=bpm, plate=plate, extra_colors=extra,
               seed=sum(ord(ch) for ch in str(plan.get("title") or "x")) % 997 + 1)


__all__ = ["normalize_spec", "draft_spec", "render_frame", "make_ctx", "Ctx", "camera_at", "MOVES", "TRANSITIONS", "shade"]
