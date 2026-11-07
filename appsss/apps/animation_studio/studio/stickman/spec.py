"""Stickman contracts: topics, fact brief, story, roster and clip plans, cleaned from AI answers."""
from __future__ import annotations

import re
from typing import Any

CLIP_SECONDS = 10
BEAT_WINDOWS = ((0.0, 3.0, "setup"), (3.0, 7.0, "escalation"), (7.0, 10.0, "payoff"))
NARRATION_WORDS = (18, 25)
HEX = re.compile(r"^#?[0-9a-fA-F]{6}$")
ASPECTS = {"9:16": (720, 1280), "16:9": (1280, 720), "1:1": (960, 960)}
CAMERA_MOVES = ("static", "slow push in", "slow pull out", "pan left", "pan right", "tilt up", "tilt down")


def _s(v: Any, n: int = 300) -> str:
    return re.sub(r"\s+", " ", str(v or "")).strip()[:n]


def words(text: str) -> int:
    return len(re.findall(r"[\w'’-]+", text or ""))


def hexc(v: Any, d: str = "#c0392b") -> str:
    v = str(v or "").strip()
    return ("#" + v.lstrip("#")).lower() if HEX.match(v) else d


# ---------- topics ----------
def norm_topics(data: Any) -> dict:
    raw = (data or {}).get("topics") if isinstance(data, dict) else None
    if not isinstance(raw, list) or len(raw) < 3:
        raise ValueError("fewer than three topic ideas")
    out = []
    for t in raw[:8]:
        t = t if isinstance(t, dict) else {}
        title = _s(t.get("title"), 90)
        if not title:
            continue
        out.append({"title": title, "date_place": _s(t.get("date_place"), 120), "premise": _s(t.get("premise"), 300),
                    "opening_visual": _s(t.get("opening_visual"), 260), "conflict": _s(t.get("conflict"), 220), "ending": _s(t.get("ending"), 220),
                    "duration_s": int(max(30, min(120, int(float(t.get("duration_s") or 60) // 10 * 10)))), "clips": int(max(3, min(12, int(float(t.get("clips") or 6))))),
                    "difficulty": t.get("difficulty") if t.get("difficulty") in ("easy", "medium", "hard") else "medium"})
    if len(out) < 3:
        raise ValueError("fewer than three usable topic ideas")
    rec = data.get("recommended")
    return {"topics": out, "recommended": rec if isinstance(rec, int) and 0 <= rec < len(out) else 0, "why": _s(data.get("why"), 300)}


# ---------- fact brief ----------
def norm_brief(data: Any) -> dict:
    if not isinstance(data, dict):
        raise ValueError("the fact brief is not an object")
    facts = []
    for f in (data.get("facts") or [])[:14]:
        f = f if isinstance(f, dict) else {"claim": f}
        if _s(f.get("claim")):
            facts.append({"claim": _s(f["claim"], 300), "confidence": "well-established" if f.get("confidence") == "well-established" else "check"})
    if not facts:
        raise ValueError("the fact brief has no facts")
    return {"event": _s(data.get("event"), 120), "date": _s(data.get("date"), 80), "location": _s(data.get("location"), 120),
            "people": [_s(x, 80) for x in (data.get("people") or [])[:8]], "cause": _s(data.get("cause"), 300),
            "turning_point": _s(data.get("turning_point"), 300), "outcome": _s(data.get("outcome"), 300), "facts": facts,
            "disputed": [_s(x, 240) for x in (data.get("disputed") or [])[:6]],
            "sources_to_check": [_s(x, 160) for x in (data.get("sources_to_check") or [])[:8]],
            "dramatization_notes": [_s(x, 200) for x in (data.get("dramatization_notes") or [])[:6]],
            "verification": "pending"}                       # nothing here has been checked against a source by this app


# ---------- story ----------
def norm_story(data: Any, n: int) -> dict:
    clips = (data or {}).get("clips") if isinstance(data, dict) else None
    if not isinstance(clips, list) or len(clips) < n:
        raise ValueError(f"the story has fewer than {n} clips")
    out = []
    for i, c in enumerate(clips[:n]):
        c = c if isinstance(c, dict) else {}
        nar = _s(c.get("narration"), 400)
        if not nar:
            raise ValueError(f"clip {i + 1} has no narration")
        out.append({"n": i + 1, "t0": i * CLIP_SECONDS, "t1": (i + 1) * CLIP_SECONDS, "purpose": _s(c.get("purpose"), 160),
                    "narration": nar, "main_action": _s(c.get("main_action"), 240)})
    return {"title": _s(data.get("title"), 90), "hook": _s(data.get("hook"), 200), "clips": out}


def narration_warning(text: str) -> str:
    w = words(text)
    lo, hi = NARRATION_WORDS
    return "" if lo - 2 <= w <= hi + 3 else f"{w} words (aim for {lo}-{hi} for ten seconds)"


# ---------- roster ----------
def norm_roster(data: Any) -> list[dict]:
    raw = (data or {}).get("characters") if isinstance(data, dict) else None
    if not isinstance(raw, list) or not raw:
        raise ValueError("the roster is empty")
    out = []
    for i, c in enumerate(raw[:3]):
        c = c if isinstance(c, dict) else {}
        acc = [{"name": _s(a.get("name"), 30) or "accent", "hex": hexc(a.get("hex"))} for a in (c.get("accents") or []) if isinstance(a, dict)][:4]
        if not acc:
            acc = [{"name": "accent red", "hex": "#c0392b"}]
        out.append({"id": f"CHAR_{i + 1:02d}", "name": _s(c.get("name"), 60) or f"Character {i + 1}", "role": _s(c.get("role"), 100) or "lead",
                    "age_presentation": _s(c.get("age_presentation"), 40) or "adult", "head_shape": _s(c.get("head_shape"), 80) or "round head",
                    "height_heads": round(max(3.0, min(8.0, float(c.get("height_heads") or 5))), 1),
                    "proportions": _s(c.get("proportions"), 160) or "slim stick body, thin stick limbs of equal length",
                    "eyes": _s(c.get("eyes"), 60) or "two black dot eyes", "brows": _s(c.get("brows"), 80) or "short expressive black eyebrows",
                    "mouth": _s(c.get("mouth"), 80) or "a simple curved line mouth", "hair_or_headwear": _s(c.get("hair_or_headwear"), 140) or "no hair",
                    "clothing": _s(c.get("clothing"), 220) or "simple period tunic", "footwear": _s(c.get("footwear"), 80) or "simple flat shoes",
                    "accents": acc, "signature_prop": _s(c.get("signature_prop"), 100) or "none",
                    "distinguishing_feature": _s(c.get("distinguishing_feature"), 120) or "a small notch in the headwear",
                    "planned_damage": _s(c.get("planned_damage"), 120) or "none planned"})
    return out


# ---------- clip plan ----------
def _state(c: Any, ids: set[str]) -> dict:
    c = c if isinstance(c, dict) else {}
    return {"id": c.get("id") if c.get("id") in ids else None, "position": _s(c.get("position"), 80) or "centre", "facing": _s(c.get("facing"), 40) or "facing camera",
            "pose": _s(c.get("pose"), 100) or "standing", "expression": _s(c.get("expression"), 60) or "neutral", "clothing_state": _s(c.get("clothing_state"), 80) or "as designed",
            "prop_grip": _s(c.get("prop_grip"), 80) or "empty hands", "holds": _s(c.get("holds") or c.get("prop_grip"), 80) or "nothing", "emotion": _s(c.get("emotion") or c.get("expression"), 40) or "neutral"}


def norm_clip(data: Any, n: int, ids: set[str], prev_out: dict | None) -> dict:
    d = data if isinstance(data, dict) else {}
    b = d.get("beats") if isinstance(d.get("beats"), dict) else {}
    chars = [x for x in (_state(c, ids) for c in (d.get("chars") or [])) if x["id"]][:3]
    if not chars:
        raise ValueError(f"clip {n} shows no recurring character")
    fs = d.get("final_state") if isinstance(d.get("final_state"), dict) else {}
    fchars = [x for x in (_state(c, ids) for c in (fs.get("chars") or [])) if x["id"]] or [{**c} for c in chars]
    old = {"setup": " ".join(x for x in (_s(b.get("hook"), 150), _s(b.get("main"), 150)) if x), "escalation": _s(b.get("reaction"), 300), "payoff": _s(b.get("outcome"), 300)}
    beats = {k: _s(b.get(k), 300) or old[k] for _, _, k in BEAT_WINDOWS}       # older plans used four beats
    if not all(beats.values()):
        raise ValueError(f"clip {n} is missing one of the three timed beats")
    return {"n": n, "t0": (n - 1) * CLIP_SECONDS, "t1": n * CLIP_SECONDS, "location": _s(d.get("location"), 120) or "a period-appropriate location", "time_of_day": _s(d.get("time_of_day"), 40) or "daytime",
            "scenery": _s(d.get("scenery"), 240) or "simple period-appropriate scenery", "framing": _s(d.get("framing"), 100) or "medium wide shot",
            "camera_angle": _s(d.get("camera_angle"), 60) or "eye level", "foreground": _s(d.get("foreground"), 160) or "a plain ground line",
            "middle": _s(d.get("middle"), 160) or "the characters", "background": _s(d.get("background"), 160) or "pale muted scenery",
            "chars": chars, "opening_setup": _s(d.get("opening_setup"), 260) or "the characters stand ready before the action begins",
            "beats": beats, "camera_move": d.get("camera_move") if d.get("camera_move") in CAMERA_MOVES else "static",
            "prop_interaction": _s(d.get("prop_interaction"), 200) or "no prop interaction", "final_summary": _s(fs.get("summary"), 240) or beats["payoff"],
            "outgoing": {"chars": fchars, "location": _s(d.get("location"), 120), "summary": _s(fs.get("summary"), 240) or beats["payoff"]},
            "incoming": prev_out, "sfx": [_s(x, 80) for x in (d.get("sfx") or [])[:4]], "music": _s(d.get("music"), 100) or "soft period-flavoured underscore, very quiet",
            "transition": "cut" if d.get("transition") == "cut" else "match", "transition_note": _s(d.get("transition_note"), 200)}
