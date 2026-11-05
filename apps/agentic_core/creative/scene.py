"""Scene graph and motion blueprint: what is in a shot, where, seen from where, and what moves when.

One JSON shape, read by the prompt compiler (Python), the Director stage (Three.js) and its timeline (GSAP):

    scene = {"location": "kitchen", "time": "evening", "framing": "medium",
             "lighting": {"preset": "evening interior", "key": "warm practical lamps", "mood": "cosy"},
             "actors": [{"id": "raju", "x": -0.6, "z": 0.0, "facing": "amma", "pose": "standing", "expression": "guilty",
                         "speaking": True}],
             "props": [{"name": "broken TV remote", "x": 0.2, "z": 0.6, "held_by": "raju"}],
             "camera": {"position": [0, 1.5, 3.2], "target": [-0.3, 1.3, 0], "lens": 35}}

    motion = {"duration": 4.0,
              "camera": {"move": "push_in", "ease": "power1.inOut", "from": {...camera}, "to": {...camera}, "shake": 0},
              "tracks": [{"target": "raju", "keys": [{"t": 0, "action": "hides the remote behind his back"},
                                                     {"t": 1.5, "action": "backs away", "x": -1.0}]}],
              "environment": [{"t": 0, "text": "steam rises from the pressure cooker"}],
              "lipsync": "raju"}

Stage units are metres: the floor is y = 0, x runs left → right as the camera first sees it, z comes toward the
camera (the back wall is at z = -4). People are ~1.6 m tall (kids ~1.3 m).
"""
from __future__ import annotations

import math
from typing import Any

FRAMINGS = ("wide", "medium", "two-shot", "close-up", "over-the-shoulder", "insert")
# framing → (lens mm, distance from the subject, camera height, look-at height)
RIG: dict[str, tuple[int, float, float, float]] = {
    "wide": (24, 6.5, 1.6, 1.1),
    "medium": (35, 3.2, 1.5, 1.25),
    "two-shot": (35, 3.8, 1.5, 1.2),
    "close-up": (85, 2.4, 1.45, 1.45),
    "over-the-shoulder": (50, 2.6, 1.55, 1.4),
    "insert": (85, 1.3, 1.1, 0.9),
}
MOVES = ("static", "push_in", "pull_out", "pan_left", "pan_right", "truck_left", "truck_right", "tilt_up", "tilt_down",
         "crane_up", "crane_down", "orbit_left", "orbit_right", "zoom_in", "handheld")
EASES = ("none", "power1.inOut", "power2.inOut", "power2.out", "power3.out", "sine.inOut", "expo.inOut")
ANGLES = ("eye level", "low angle", "high angle", "overhead")
LIGHTING = {
    "morning": ("soft morning sunlight through windows", "fresh, calm"),
    "afternoon": ("bright daylight", "cheerful"),
    "day": ("bright daylight", "cheerful"),
    "evening": ("warm golden evening light, practical lamps", "cosy"),
    "night": ("cool moonlight with warm lamp pools", "quiet, intimate"),
}


def _f(v: Any, default: float, lo: float, hi: float) -> float:
    try:
        return round(max(lo, min(hi, float(v))), 3)
    except (TypeError, ValueError):
        return default


def _vec(v: Any, default: list[float]) -> list[float]:
    if isinstance(v, (list, tuple)) and len(v) == 3:
        return [_f(v[0], default[0], -20, 20), _f(v[1], default[1], 0.05, 12), _f(v[2], default[2], -20, 20)]
    return list(default)


def stage_positions(n: int) -> list[float]:
    """Where n people stand across the frame (x), left to right."""
    return {0: [], 1: [0.0], 2: [-0.55, 0.55], 3: [-0.9, 0.0, 0.9]}.get(n, [round(-1.2 + 2.4 * i / max(1, n - 1), 2) for i in range(n)])


def camera_for(framing: str, subject: list[float] | None = None, lens: int | None = None) -> dict[str, Any]:
    """A camera framing a subject point (x, z) the way the framing says."""
    f = framing if framing in RIG else "medium"
    mm, dist, height, look = RIG[f]
    sx, sz = (subject or [0.0, 0.0])[:2] if subject else (0.0, 0.0)
    return {"position": [round(sx * 0.5, 3), height, round(sz + dist, 3)], "target": [round(sx, 3), look, round(sz, 3)],
            "lens": int(lens or mm)}


def angle_of(text: Any) -> str:
    """'low-angle', 'worm's eye', 'bird's-eye', 'top down', 'eye-level' … → one of ANGLES."""
    t = str(text or "").lower()
    if any(w in t for w in ("overhead", "bird", "top down", "top-down", "aerial")):
        return "overhead"
    if "low" in t or "worm" in t:
        return "low angle"
    if "high" in t:
        return "high angle"
    return "eye level"


def apply_angle(cam: dict[str, Any], angle: str) -> dict[str, Any]:
    """The same framing seen from below (low angle), above (high angle) or straight down-ish (overhead)."""
    p, t = list(cam["position"]), list(cam["target"])
    dist = max(0.5, abs(p[2] - t[2]) + abs(p[0] - t[0]))
    if angle == "low angle":
        p[1] = 0.3
        t[1] = round(max(t[1], 1.4 + 0.05 * dist), 3)
    elif angle == "high angle":
        p[1] = round(t[1] + max(1.6, 0.55 * dist), 3)
    elif angle == "overhead":
        p[1] = round(t[1] + 4.0, 3)
        p[2] = round(t[2] + (p[2] - t[2]) * 0.35, 3)
    return {**cam, "position": p, "target": t}


def normalize_camera(c: Any, fallback: dict[str, Any]) -> dict[str, Any]:
    c = c if isinstance(c, dict) else {}
    return {"position": _vec(c.get("position"), fallback["position"]), "target": _vec(c.get("target"), fallback["target"]),
            "lens": int(_f(c.get("lens"), fallback["lens"], 12, 200))}


def normalize_scene(sc: Any, *, subjects: list[str] | None = None, framing: str | None = None, location: str = "",
                    time: str = "day", default_lens: int | None = None) -> dict[str, Any]:
    """Fill a (possibly partial, possibly LLM-written) scene graph into a complete, valid one."""
    sc = sc if isinstance(sc, dict) else {}
    framing = str(sc.get("framing") or framing or "medium").lower()
    framing = framing if framing in FRAMINGS else "medium"
    given = {str(a.get("id")): a for a in sc.get("actors") or [] if isinstance(a, dict) and a.get("id")}
    ids = list(dict.fromkeys([*(subjects or []), *given]))
    xs = stage_positions(len(ids))
    actors = []
    for i, aid in enumerate(ids):
        a = given.get(aid, {})
        actors.append({"id": aid, "x": _f(a.get("x"), xs[i], -6, 6), "z": _f(a.get("z"), 0.0, -4, 4),
                       "facing": str(a.get("facing") or ("camera" if len(ids) == 1 else (ids[1 - i] if len(ids) == 2 else "camera")))[:40],
                       "pose": str(a.get("pose") or "standing")[:120], "expression": str(a.get("expression") or "neutral")[:60],
                       "speaking": bool(a.get("speaking"))})
    props = [{"name": str(p.get("name"))[:60], "x": _f(p.get("x"), 0.0, -6, 6), "z": _f(p.get("z"), 0.5, -4, 4),
              "held_by": (str(p["held_by"]) if p.get("held_by") in ids else None)}
             for p in sc.get("props") or [] if isinstance(p, dict) and p.get("name")][:6]
    t = str(sc.get("time") or time or "day").lower()
    key, mood = LIGHTING.get(t, LIGHTING["day"])
    light = sc.get("lighting") if isinstance(sc.get("lighting"), dict) else {}
    lighting = {"preset": str(light.get("preset") or t)[:40], "key": str(light.get("key") or key)[:160], "mood": str(light.get("mood") or mood)[:80]}
    focus = next((a for a in actors if a["speaking"]), actors[0] if actors else None)
    subj = [focus["x"], focus["z"]] if focus else None
    if framing in ("two-shot", "wide") and len(actors) > 1:
        subj = [sum(a["x"] for a in actors) / len(actors), sum(a["z"] for a in actors) / len(actors)]
    lens = sc.get("lens") if isinstance(sc.get("lens"), (int, float)) and not isinstance(sc.get("lens"), bool) else None
    base = camera_for(framing, subj, int(_f(lens, 35, 12, 200)) if lens else (default_lens if framing in ("medium", "two-shot") else None))
    if sc.get("angle") and not sc.get("camera"):
        base = apply_angle(base, angle_of(sc["angle"]))       # "low angle" from a prompt, when no exact camera was given
    cam = normalize_camera(sc.get("camera"), base)
    return {"location": str(sc.get("location") or location)[:60], "time": t[:20], "framing": framing, "lighting": lighting,
            "actors": actors, "props": props, "camera": cam}


def move_camera(cam: dict[str, Any], move: str, amount: float = 1.0) -> dict[str, Any]:
    """Where the camera ends after a move (the start is `cam`)."""
    p, t, lens = list(cam["position"]), list(cam["target"]), cam["lens"]
    d = [t[0] - p[0], t[1] - p[1], t[2] - p[2]]
    k = amount
    if move == "push_in":
        p = [p[i] + d[i] * 0.3 * k for i in range(3)]
    elif move == "pull_out":
        p = [p[i] - d[i] * 0.35 * k for i in range(3)]
    elif move in ("pan_left", "pan_right"):
        t[0] += (-0.9 if move == "pan_left" else 0.9) * k
    elif move in ("truck_left", "truck_right"):
        s = (-0.8 if move == "truck_left" else 0.8) * k
        p[0] += s
        t[0] += s
    elif move in ("tilt_up", "tilt_down"):
        t[1] += (0.6 if move == "tilt_up" else -0.5) * k
    elif move in ("crane_up", "crane_down"):
        p[1] = max(0.3, p[1] + (0.9 if move == "crane_up" else -0.6) * k)
    elif move in ("orbit_left", "orbit_right"):
        a = math.radians((-20 if move == "orbit_left" else 20) * k)
        dx, dz = p[0] - t[0], p[2] - t[2]
        p[0], p[2] = t[0] + dx * math.cos(a) - dz * math.sin(a), t[2] + dx * math.sin(a) + dz * math.cos(a)
    elif move == "zoom_in":
        lens = int(min(200, lens * 1.4))
    return {"position": [round(x, 3) for x in p], "target": [round(x, 3) for x in t], "lens": lens}


def normalize_motion(m: Any, scene: dict[str, Any], *, duration: float, speaker: str | None = None,
                     default_move: str = "static", default_ease: str = "power1.inOut") -> dict[str, Any]:
    """Fill a (possibly partial) motion blueprint: camera move with explicit from/to, per-actor key tracks in time."""
    m = m if isinstance(m, dict) else {}
    dur = _f(m.get("duration"), duration, 0.5, 60) if m.get("duration") else round(float(duration), 3)
    cam = m.get("camera") if isinstance(m.get("camera"), dict) else {}
    move = str(cam.get("move") or default_move).lower().replace(" ", "_").replace("-", "_")
    move = {"dolly_in": "push_in", "dolly_out": "pull_out", "slow_push_in": "push_in", "pan": "pan_right", "tilt": "tilt_up",
            "orbit": "orbit_right", "zoom": "zoom_in"}.get(move, move)
    move = move if move in MOVES else "static"
    ease = str(cam.get("ease") or default_ease)
    ease = ease if ease in EASES else default_ease
    start = normalize_camera(cam.get("from"), scene["camera"])
    end = normalize_camera(cam.get("to"), move_camera(start, move)) if cam.get("to") else move_camera(start, move)
    ids = {a["id"] for a in scene["actors"]}
    tracks = []
    for tr in m.get("tracks") or []:
        if not isinstance(tr, dict) or str(tr.get("target")) not in ids:
            continue
        keys = []
        for k in tr.get("keys") or []:
            if not isinstance(k, dict) or not str(k.get("action") or "").strip():
                continue
            key = {"t": _f(k.get("t"), 0.0, 0, dur), "action": str(k["action"]).strip()[:160]}
            for ax in ("x", "z"):
                if k.get(ax) is not None:
                    key[ax] = _f(k.get(ax), 0.0, -6, 6)
            keys.append(key)
        if keys:
            tracks.append({"target": str(tr["target"]), "keys": sorted(keys, key=lambda k: k["t"])[:8]})
    env = [{"t": _f(e.get("t"), 0.0, 0, dur), "text": str(e.get("text"))[:140]} for e in m.get("environment") or []
           if isinstance(e, dict) and e.get("text")][:4]
    lip = m.get("lipsync") if m.get("lipsync") in ids else (speaker if speaker in ids else None)
    return {"duration": dur, "camera": {"move": move, "ease": ease, "from": start, "to": end,
                                        "shake": _f(cam.get("shake"), 0.15 if move == "handheld" else 0.0, 0, 1)},
            "tracks": tracks, "environment": env, "lipsync": lip}


def retime(motion: dict[str, Any], duration: float) -> dict[str, Any]:
    """The same blueprint stretched to a new length (a line's real duration once it's voiced)."""
    old = float(motion.get("duration") or 0) or duration
    k = duration / old if old else 1.0
    out = {**motion, "duration": round(float(duration), 3),
           "tracks": [{**tr, "keys": [{**key, "t": round(min(duration, key["t"] * k), 3)} for key in tr["keys"]]} for tr in motion["tracks"]],
           "environment": [{**e, "t": round(min(duration, e["t"] * k), 3)} for e in motion["environment"]]}
    return out


def camera_at(motion: dict[str, Any], t: float) -> dict[str, Any]:
    """The camera at time t (linear interpolation; the Director's GSAP preview uses the same from/to)."""
    c = motion["camera"]
    u = 0.0 if motion["duration"] <= 0 else max(0.0, min(1.0, t / motion["duration"]))
    lerp = lambda a, b: [round(a[i] + (b[i] - a[i]) * u, 3) for i in range(3)]  # noqa: E731
    return {"position": lerp(c["from"]["position"], c["to"]["position"]), "target": lerp(c["from"]["target"], c["to"]["target"]),
            "lens": round(c["from"]["lens"] + (c["to"]["lens"] - c["from"]["lens"]) * u)}


def changed_parts(old_scene: dict | None, new_scene: dict, old_motion: dict | None, new_motion: dict) -> set[str]:
    """What a Director edit invalidates: 'picture' (the keyframe) and/or 'motion' (the clip)."""
    out: set[str] = set()
    if old_scene != new_scene:
        out |= {"picture", "motion"}
    if old_motion != new_motion:
        out.add("motion")
    return out
