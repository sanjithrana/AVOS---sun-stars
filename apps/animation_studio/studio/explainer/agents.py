"""The crew: every agent that works on a video, what it is doing for THIS project, and what it produced.

The five stages are when the line stops for you; the agents are who does the work inside them. Each agent reports
state (waiting, working, done, skipped, off, needs attention), progress (n of m) and one line about its output,
worked out from the project itself, so the page always matches what is really on disk."""
from __future__ import annotations

from typing import Any

from . import skills

# id, name, stage, what it does, the skill switch it follows (None: always on)
CREW: list[dict[str, Any]] = [
    {"id": "research", "name": "Researcher", "stage": "plan", "skill": "research", "does": "Checks the facts and keeps the sources."},
    {"id": "writer", "name": "Scriptwriter", "stage": "plan", "skill": None, "does": "Writes the hook, the story and every spoken line."},
    {"id": "director", "name": "Director", "stage": "plan", "skill": None, "does": "Breaks the script into scenes and shots: camera, light, mood, sound, start and end of each shot."},
    {"id": "memory", "name": "Cast memory", "stage": "plan", "skill": None, "does": "Recognises characters the studio built before and locks their look and seed."},
    {"id": "casting", "name": "Character designer", "stage": "design", "skill": None, "does": "Draws an identity portrait and a design sheet for each new character."},
    {"id": "art", "name": "Set and prop designer", "stage": "design", "skill": None, "does": "Draws the set, every prop and the key visual."},
    {"id": "board", "name": "Storyboard artist", "stage": "board", "skill": None, "does": "Draws the first frame of every shot from the portraits, the set and the props."},
    {"id": "keys", "name": "Key-pose artist", "stage": "board", "skill": "keyframes", "does": "Draws the last frame of every shot, so the action has a start and an end."},
    {"id": "continuity", "name": "Continuity checker", "stage": "board", "skill": None, "does": "Compares each frame with the character's portrait and redraws one that drifted."},
    {"id": "boards", "name": "Board builder", "stage": "board", "skill": None, "does": "Lays out cast, world, scene and clip boards."},
    {"id": "voice", "name": "Voice actor", "stage": "shoot", "skill": None, "does": "Speaks every line in the chosen voice, or each character's own voice."},
    {"id": "animator", "name": "Animator", "stage": "shoot", "skill": None, "does": "Turns each shot into motion: an AI video model, or a key-pose animatic from first to last frame."},
    {"id": "lipsync", "name": "Lip-sync", "stage": "shoot", "skill": "lipsync", "does": "Matches the speaking character's mouth to the line."},
    {"id": "composer", "name": "Composer", "stage": "finish", "skill": "music", "does": "Makes music that fits and mixes it under the voice."},
    {"id": "editor", "name": "Editor", "stage": "finish", "skill": None, "does": "Cuts the shots together, burns in captions and writes the final video."},
]
ORDER = ("plan", "design", "board", "shoot", "finish")


def _state(p: dict, stage: str, done: bool) -> str:
    at = ORDER.index(p.get("stage") or "plan") if (p.get("stage") or "plan") in ORDER else 0
    me = ORDER.index(stage)
    if done:
        return "done"
    if me == at and p.get("status") == "working":
        return "working"
    if me == at and p.get("status") == "error":
        return "error"
    return "waiting"


def status(p: dict, have: Any) -> list[dict]:
    """have(rel) -> bool: is this file on disk."""
    plan = p.get("plan") or {}
    shots = plan.get("shots") or []
    chars = plan.get("characters") or []
    props = plan.get("props") or []
    a = p.get("assets") or {}
    caps = p.get("caps") or {}
    n = len(shots)
    frames = sum(1 for s in shots if have(s.get("frame")))
    ends = sum(1 for s in shots if have(s.get("end_frame")))
    clips = [s for s in shots if have(s.get("clip"))]
    ai = sum(1 for s in clips if s.get("engine") in ("ai_video", "lipsync"))
    voiced = sum(1 for s in shots if (s.get("voice") or {}).get("model"))
    remembered = [c["name"] for c in chars if c.get("memory")]
    drift = sum(1 for s in shots if "off_model" in (s.get("qc") or []))
    checked = sum(1 for s in shots if s.get("continuity_check"))
    boards = p.get("boards") or {}
    out = []
    for ag in CREW:
        k, st = ag["id"], ag["stage"]
        on = skills.on(ag["skill"]) if ag["skill"] else True
        row = {"id": k, "name": ag["name"], "stage": st, "does": ag["does"], "on": on, "progress": None, "output": ""}
        if k == "research":
            r = p.get("research") or {}
            done = r.get("status") == "ok"
            row["output"] = f"{len(r.get('facts') or [])} facts from {len(r.get('sources') or [])} sources" if done else ("skipped: " + (r.get("reason") or "")) if r else ""
            row["state"] = "done" if done else ("skipped" if r or plan else _state(p, st, False))
        elif k in ("writer", "director"):
            done = bool(plan)
            scenes = len({s.get("scene") for s in shots})
            row["output"] = (f"{plan.get('title', '')}: {sum(1 for s in shots if s.get('narration'))} lines" if k == "writer" else
                             f"{scenes} scenes, {n} shots, {round(sum(float(s.get('seconds') or 0) for s in shots), 1)} s") if done else ""
            row["state"] = _state(p, st, done)
        elif k == "memory":
            row["state"] = "done" if plan else _state(p, st, False)
            row["output"] = (f"recognised {', '.join(remembered)}" if remembered else "all characters are new; they are remembered after the design") if plan else ""
        elif k == "casting":
            got = sum(1 for c in chars if have(a.get(f"char:{c['id']}")))
            row["progress"] = [got, len(chars)] if chars else None
            row["state"] = _state(p, st, bool(chars) and got == len(chars))
            row["output"] = f"{got} of {len(chars)} characters" + (f" ({len(remembered)} from memory)" if remembered else "") if chars else ""
        elif k == "art":
            want = len(props) + 2 if plan else 0
            got = sum(1 for x in props if have(a.get(f"prop:{x['id']}"))) + have(a.get("world")) + have(a.get("poster"))
            row["progress"] = [got, want] if want else None
            row["state"] = _state(p, st, bool(want) and got == want)
            row["output"] = f"set, {len(props)} props, key visual" if want else ""
        elif k == "board":
            row["progress"] = [frames, n] if n else None
            row["state"] = _state(p, st, bool(n) and frames == n)
            row["output"] = f"{frames} of {n} first frames" if n else ""
        elif k == "keys":
            row["progress"] = [ends, n] if n and on else None
            row["state"] = "off" if not on else _state(p, st, bool(n) and ends == n)
            row["output"] = f"{ends} of {n} last frames" if on and n else ("switched off" if not on else "")
        elif k == "continuity":
            vis = p.get("vision_check")
            row["state"] = "done" if frames and frames == n else _state(p, st, False)
            row["output"] = (f"{checked} frames checked, {drift} redrawn" if vis else
                             "needs a vision model in your AI crew (e.g. qwen2.5vl or gemma3): identity is held by the locked look and seed") if frames else ""
            if frames and not vis:
                row["state"] = "skipped"
        elif k == "boards":
            got = len((boards.get("cast") or {})) + bool(boards.get("world")) + len(boards.get("scenes") or {}) + len(boards.get("clips") or {})
            row["state"] = "done" if got else _state(p, st, False)
            row["output"] = f"{len(boards.get('cast') or {})} cast, 1 world, {len(boards.get('scenes') or {})} scene and {len(boards.get('clips') or {})} clip boards" if got else ""
        elif k == "voice":
            want = sum(1 for s in shots if s.get("narration"))
            row["progress"] = [voiced, want] if want else None
            row["state"] = _state(p, st, bool(want) and voiced >= want)
            fb = sum(1 for s in shots if (s.get("voice") or {}).get("fallback"))
            row["output"] = f"{voiced} of {want} lines" + (f", {fb} silent (no internet for the voice)" if fb else "") if want else ""
        elif k == "animator":
            row["progress"] = [len(clips), n] if n else None
            row["state"] = _state(p, st, bool(n) and len(clips) == n)
            row["output"] = (f"{ai} AI video, {len(clips) - ai} key-pose animatic" if clips else
                             ("an AI video model is ready" if caps.get("ai_video") else "no AI video model ready: key-pose animatics (add fal.ai credit or a GPU for real motion)") if plan else "")
        elif k == "lipsync":
            ls = sum(1 for s in clips if s.get("engine") == "lipsync")
            row["state"] = "off" if not on else ("done" if ls else "skipped" if clips else _state(p, st, False))
            row["output"] = f"{ls} speaking shots" if ls else ("no lip-sync model ready" if clips and on else "")
        elif k == "composer":
            row["state"] = "off" if not on else ("done" if p.get("final") else _state(p, st, False))
        elif k == "editor":
            row["state"] = "done" if p.get("final") else _state(p, st, False)
            row["output"] = f"{p.get('finalSeconds')} s with captions" if p.get("final") else ""
        if not on and row.get("state") not in ("off",):
            row["state"] = "off"
        out.append(row)
    return out
