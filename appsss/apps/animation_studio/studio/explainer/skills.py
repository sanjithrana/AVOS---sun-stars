"""Autopilot skills: one named, switchable skill per part of the production line.

Each skill says what it does, which prompts it owns (the prompt library's keys, so it learns), which engine it uses, and how
often it worked. You can switch the optional ones off, improve a weak one, and see which are ready. The pipeline asks
`on(id)` before an optional step and calls `tick(id, ok)` after it, which is the record the Autopilot learns from."""
from __future__ import annotations

import json
import threading
from typing import Any

from . import prompts, store

_LOCK = threading.RLock()

# id, name, what it does, stage it runs in, prompt-library keys it owns, can be switched off
SKILLS: list[dict[str, Any]] = [
    {"id": "research", "name": "Research", "stage": "plan", "keys": [], "optional": True,
     "does": "Looks the topic up (Wikipedia, with links) so the script uses real facts."},
    {"id": "script", "name": "Script and story", "stage": "plan", "keys": ["director.rules", "director.cinema", "director.story", "director.explain"], "optional": False,
     "does": "Analyses the idea, builds the story and writes every shot: camera, lighting, mood, sound, who speaks."},
    {"id": "characters", "name": "Characters", "stage": "design", "keys": ["sheet.character", "portrait.identity"], "optional": False,
     "does": "Draws a design sheet for each character. You approve them before anything else is drawn from them."},
    {"id": "backgrounds", "name": "Backgrounds and props", "stage": "design", "keys": ["poster.tail"], "optional": False,
     "does": "Draws the set, the props and the key visual. You approve them with the characters."},
    {"id": "storyboard", "name": "Scene storyboard", "stage": "board", "keys": ["picture.base", "picture.recipe.presenter", "picture.recipe.demonstration",
                                                                          "picture.recipe.macro_close_up", "picture.recipe.scientific_cutaway", "picture.recipe.result",
                                                                          "picture.recipe.reaction", "picture.recipe.establishing"], "optional": False,
     "does": "Draws the first frame of every shot from the approved characters and set, and checks each picture."},
    {"id": "keyframes", "name": "Key poses (last frames)", "stage": "board", "keys": ["picture.endframe"], "optional": True,
     "does": "Draws the last frame of every shot, so the action has a start and an end; without a video model the shot becomes a key-pose animatic."},
    {"id": "voice", "name": "Voice", "stage": "shoot", "keys": [], "optional": False,
     "does": "Speaks the narration in the voice you picked."},
    {"id": "dialog", "name": "Dialog", "stage": "shoot", "keys": [], "optional": True,
     "does": "Lets characters speak their own lines, each in their own voice."},
    {"id": "motion", "name": "Images to video", "stage": "shoot", "keys": ["motion.keep"], "optional": False,
     "does": "Turns each picture into a moving shot with the best video model that is ready, or a camera move on the picture."},
    {"id": "lipsync", "name": "Lip-sync", "stage": "shoot", "keys": [], "optional": True,
     "does": "Makes the speaking character's mouth match the line, when a lip-sync model is ready."},
    {"id": "music", "name": "Music", "stage": "finish", "keys": [], "optional": True,
     "does": "Makes music that fits the story and mixes it under the voice."},
    {"id": "finish", "name": "Captions and final video", "stage": "finish", "keys": [], "optional": False,
     "does": "Joins the shots with voice and music, burns in the captions and writes the final video."},
]
BY_ID = {s["id"]: s for s in SKILLS}


def _file():
    return store.ROOT / "skills.json"


def _load() -> dict:
    try:
        d = json.loads(_file().read_text("utf-8"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _save(d: dict) -> None:
    store.ROOT.mkdir(parents=True, exist_ok=True)
    tmp = _file().with_suffix(".tmp")
    tmp.write_text(json.dumps(d, indent=1), "utf-8")
    tmp.replace(_file())


def on(skill: str) -> bool:
    """Is this skill switched on? (Skills that can't be switched off are always on.)"""
    s = BY_ID.get(skill)
    if not s or not s["optional"]:
        return True
    with _LOCK:
        return skill not in (_load().get("off") or [])


def set_on(skill: str, value: bool) -> None:
    s = BY_ID.get(skill)
    if not s:
        raise KeyError(skill)
    if not s["optional"]:
        raise ValueError("This skill is always on.")
    with _LOCK:
        d = _load()
        off = set(d.get("off") or [])
        (off.discard if value else off.add)(skill)
        d["off"] = sorted(off)
        _save(d)


def tick(skill: str, ok: bool, why: str = "") -> None:
    """Record that a skill worked (or didn't) once. Never breaks a project."""
    try:
        with _LOCK:
            d = _load()
            r = d.setdefault("runs", {}).setdefault(skill, {"ok": 0, "fail": 0, "last": ""})
            r["ok" if ok else "fail"] += 1
            if not ok:
                r["last"] = why[:160]
            _save(d)
    except Exception:  # noqa: BLE001
        pass


def _ready(skill: str, caps: dict) -> tuple[bool, str]:
    """(ready, one plain sentence)."""
    if skill == "motion":
        return (True, "AI video model ready") if caps.get("ai_video") else (True, "No video model: pictures with camera moves")
    if skill == "lipsync":
        return (bool(caps.get("lipsync")), "Lip-sync model ready" if caps.get("lipsync") else "No lip-sync model ready: speaking shots use the normal video")
    if skill in ("voice", "dialog"):
        return (bool(caps.get("voice")), "Voices ready" if caps.get("voice") else "Edge voices need the edge-tts package and internet")
    if skill == "music":
        return (bool(caps.get("music")), "Music model ready" if caps.get("music") else "No local music model: tries the cloud, else no music")
    return True, "Ready"


def listing(caps: dict | None = None) -> list[dict]:
    caps = caps or {}
    lib = {i["key"]: i for i in prompts.library()["items"]}
    with _LOCK:
        d = _load()
    out = []
    for s in SKILLS:
        items = [lib[k] for k in s["keys"] if k in lib]
        uses = sum((i["active"] or {}).get("uses", 0) for i in items)
        bad = sum((i["active"] or {}).get("bad", 0) for i in items)
        weak = max(items, key=lambda i: (i["active"] or {}).get("bad_rate", 0), default=None)
        rd, why = _ready(s["id"], caps)
        runs = (d.get("runs") or {}).get(s["id"], {"ok": 0, "fail": 0, "last": ""})
        out.append({"id": s["id"], "name": s["name"], "stage": s["stage"], "does": s["does"], "optional": s["optional"], "on": on(s["id"]),
                    "ready": rd, "ready_note": why, "prompts": [{"key": i["key"], "title": i["title"]} for i in items],
                    "uses": uses, "bad_rate": round(bad / uses, 2) if uses else 0.0, "ok": runs["ok"], "fail": runs["fail"], "last_error": runs["last"],
                    "weakest": weak["key"] if weak and (weak["active"] or {}).get("bad_rate", 0) > 0 else None})
    return out


def improve(skill: str, s: dict | None = None) -> str:
    """Improve this skill's weakest prompt now (the library's own improver, same safeguards)."""
    if skill not in BY_ID:
        raise KeyError(skill)
    items = [i for i in prompts.library()["items"] if i["key"] in BY_ID[skill]["keys"]]
    if not items:
        return "This skill has no prompt to improve; it learns from its results."
    weak = max(items, key=lambda i: (i["active"] or {}).get("bad_rate", 0))
    return prompts.improve_now(weak["key"], s)
