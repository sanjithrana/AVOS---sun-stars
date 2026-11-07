"""The one contract every shot follows, whichever engine makes it, and the cleaning of an AI-written plan."""
from __future__ import annotations

import re
from typing import Any

from . import cinema

SHOT_TYPES = ("presenter", "demonstration", "macro_close_up", "scientific_cutaway", "result", "reaction", "establishing")
ENGINES = ("ai_video", "blender", "still")
CAMERA_TYPES = ("wide", "medium", "close_up", "macro_close_up", "over_shoulder", "top_down", "cutaway")
CAMERA_MOVES = ("static", "push_in", "pull_out", "pan_right", "pan_left", "orbit", "tilt_up", "tilt_down")
ASPECTS = {"9:16": (720, 1280), "16:9": (1280, 720), "1:1": (960, 960)}
MIN_SHOT, MAX_SHOT = 2.0, 8.0
ID_RX = re.compile(r"[^a-z0-9]+")


def slug(text: str, fallback: str = "x") -> str:
    return ID_RX.sub("-", str(text or "").lower()).strip("-")[:24] or fallback


def _s(v: Any, n: int = 400) -> str:
    return re.sub(r"\s+", " ", str(v or "")).strip()[:n]


def _f(v: Any, lo: float, hi: float, d: float) -> float:
    try:
        return round(max(lo, min(hi, float(v))), 2)
    except (TypeError, ValueError):
        return d


def _pick(v: Any, opts: tuple[str, ...], d: str) -> str:
    v = str(v or "").strip().lower().replace(" ", "_").replace("-", "_")
    return v if v in opts else d


def speak_seconds(text: str) -> float:
    return round(max(0.0, len((text or "").strip()) / 14.0), 2)


def norm_item(raw: Any, i: int, kind: str) -> dict:
    raw = raw if isinstance(raw, dict) else {"name": str(raw)}
    name = _s(raw.get("name") or f"{kind} {i + 1}", 60)
    out = {"id": slug(raw.get("id") or name, f"{kind}{i + 1}"), "name": name, "look": _s(raw.get("look") or raw.get("description") or name, 500)}
    if kind == "character":
        out["voice"] = _s(raw.get("voice") or "warm, friendly, clear", 120)
        out["role"] = _pick(raw.get("role"), ("presenter", "supporting"), "presenter" if i == 0 else "supporting")
    return out


def norm_shot(raw: Any, i: int, ids: dict[str, set[str]]) -> dict:
    raw = raw if isinstance(raw, dict) else {}
    cam = raw.get("camera") if isinstance(raw.get("camera"), dict) else {}
    vis = raw.get("visualization") if isinstance(raw.get("visualization"), dict) else {}
    narration = _s(raw.get("narration") or raw.get("line"), 260)
    seconds = _f(raw.get("seconds") or raw.get("duration_seconds"), MIN_SHOT, MAX_SHOT, 3.5)
    seconds = max(seconds, min(MAX_SHOT, speak_seconds(narration) + 0.3))      # long enough to say the line
    st = _pick(raw.get("shot_type"), SHOT_TYPES, "demonstration")
    shot = {
        "id": f"S{i + 1:02d}", "index": i + 1, "shot_type": st, "seconds": seconds, "narration": narration,
        "action": _s(raw.get("action") or narration or "the presenter explains", 300),
        "characters": [c for c in (raw.get("characters") or raw.get("character_ids") or []) if c in ids["characters"]],
        "props": [p for p in (raw.get("props") or raw.get("prop_ids") or []) if p in ids["props"]],
        "camera": {"type": _pick(cam.get("type"), CAMERA_TYPES, "medium"), "movement": _pick(cam.get("movement") or cam.get("move"), CAMERA_MOVES, "push_in"),
                   "lens_mm": int(_f(cam.get("lens_mm"), 14, 135, 35))},
        "physics": bool(raw.get("physics")),
        "visualization": {"cross_section": bool(vis.get("cross_section")) or st == "scientific_cutaway",
                          "force_arrows": bool(vis.get("force_arrows")) or st == "scientific_cutaway"},
        "sfx": _s(raw.get("sfx"), 120),
        "scene": int(_f(raw.get("scene"), 1, 12, 1)), "scene_title": _s(raw.get("scene_title"), 60),
        "lighting": _s(raw.get("lighting"), 160), "mood": _s(raw.get("mood") or (None if raw.get("lighting") else ""), 140),
        "emotion": _s(raw.get("emotion"), 60), "audio": _s(raw.get("audio") or raw.get("sound") or raw.get("sfx"), 200),
        "cam_note": _s(raw.get("camera_note") or cam.get("note") or cam.get("description"), 200),
        "objective": _s(raw.get("objective") or raw.get("character_objective"), 160), "performance": _s(raw.get("performance"), 200),
        "end_state": _s(raw.get("end_state") or raw.get("end_frame"), 200), "continuity": _s(raw.get("continuity"), 200),
        "angle": _pick(raw.get("angle") or raw.get("camera_angle"), tuple(cinema.ANGLES), cinema.BY_TYPE.get(st, ("eye_level", "center"))[0]),
        "composition": _pick(raw.get("composition"), tuple(cinema.COMPOSITIONS), cinema.BY_TYPE.get(st, ("eye_level", "center"))[1]),
        "speaker": raw.get("speaker") if raw.get("speaker") in ids["characters"] else "",
        "engine": None, "engine_why": "", "status": "pending", "version": 1,
    }
    if not shot["characters"] and st in ("presenter", "reaction"):
        shot["characters"] = list(ids["characters"])[:1]
    shot["gaps"] = cinema.missing(shot)
    return shot


HEX_RX = re.compile(r"^#?([0-9a-fA-F]{6})$")


def norm_palette(raw: Any) -> list[dict]:
    """[{"name","hex"}] from the plan (also accepts "#B87333" strings); bad entries are dropped."""
    out = []
    for i, c in enumerate(raw if isinstance(raw, list) else []):
        name, hx = (c.get("name"), c.get("hex") or c.get("color")) if isinstance(c, dict) else ("", c)
        m = HEX_RX.match(str(hx or "").strip())
        if m:
            out.append({"name": _s(name or f"Colour {i + 1}", 30), "hex": "#" + m.group(1).upper()})
    return out[:8]


def norm_plan(data: Any, seconds: int, fmt: str = "9:16") -> dict:
    """An AI answer (or the built-in outline) → a plan every later step can trust. Raises ValueError when unusable."""
    if not isinstance(data, dict):
        raise ValueError("the plan is not an object")
    chars = [norm_item(c, i, "character") for i, c in enumerate(data.get("characters") or [])][:4]
    props = [norm_item(p, i, "prop") for i, p in enumerate(data.get("props") or [])][:6]
    if not chars:
        raise ValueError("the plan has no presenter")
    ids = {"characters": {c["id"] for c in chars}, "props": {p["id"] for p in props}}
    shots = [norm_shot(s, i, ids) for i, s in enumerate((data.get("shots") or [])[:16])]
    if len(shots) < 2:
        raise ValueError("the plan has fewer than two shots")
    total = sum(s["seconds"] for s in shots)
    if total > seconds * 1.4:                                        # too long for what was asked: shrink evenly (never below the minimum)
        k = seconds / total
        for s in shots:
            s["seconds"] = round(max(MIN_SHOT, s["seconds"] * k), 2)
    w = data.get("world") if isinstance(data.get("world"), dict) else {}
    return {"title": _s(data.get("title"), 90) or "Explainer", "hook": _s(data.get("hook"), 200), "characters": chars, "props": props,
            "world": {"name": _s(w.get("name") or "Studio", 60), "look": _s(w.get("look") or "bright studio, soft light, clean background", 400)},
            "music": _s(data.get("music") or "light curious suspense, playful, instrumental", 160), "style": _s(data.get("style"), 240),
            "logline": _s(data.get("logline"), 240), "palette": norm_palette(data.get("palette")), "camera_language": _s(data.get("camera_language"), 240),
            "lighting_note": _s(data.get("lighting_note") or data.get("lighting_direction"), 240), "sound_design": _s(data.get("sound_design"), 240),
            "note": _s(data.get("narrative_note") or data.get("note"), 300), "shots": shots, "aspect": fmt,
            "narration_mode": _pick(data.get("narration_mode"), ("narrator", "dialogue", "none"), "narrator")}


def total_seconds(plan: dict) -> float:
    return round(sum(s["seconds"] for s in plan.get("shots") or []), 1)
