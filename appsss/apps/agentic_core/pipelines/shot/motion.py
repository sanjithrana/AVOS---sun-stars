"""Facts shots on the creative core: a ShotSpec becomes a scene graph + motion blueprint, and the clip's prompt is
compiled from them and the style preset's Design DNA (instead of "<picture prompt> Motion: <hint>").

    plan = facts_motion(content, preset, model="ltx-2.3")
    plan["prompt"]      the motion prompt for the video model (phrased for that model)
    plan["blueprint"]   camera move + ease + timed action, the same JSON as Series / the Director
    plan["scene"]       the scene graph it was compiled from

Pure and deterministic, like the picture compiler (pipelines/shot/prompt_compiler.py).
"""
from __future__ import annotations

import re
from typing import Any

from agentic_core.creative import compiler as C, dna as D, scene as S

FRAMING = {"wide": "wide", "medium": "medium", "close_up": "close-up", "insert": "insert"}
# ShotSpec camera.movement (free text from the planner / the Studio) → a blueprint move
MOVE_RX = [(r"push|dolly.?in|zoom.?in|closer", "push_in"), (r"pull|dolly.?out|zoom.?out|reveal", "pull_out"),
           (r"pan.?left", "pan_left"), (r"pan", "pan_right"), (r"truck|track|follow", "truck_right"), (r"tilt.?up", "tilt_up"),
           (r"tilt", "tilt_down"), (r"crane|rise|up", "crane_up"), (r"orbit|arc", "orbit_right"), (r"hand.?held|shaky", "handheld")]


def _move(movement: str) -> str:
    m = (movement or "static").lower()
    if m in S.MOVES:
        return m
    return next((mv for rx, mv in MOVE_RX if re.search(rx, m)), "static")


def facts_scene(content: Any) -> dict[str, Any]:
    names = sorted(content.characters)
    actors = []
    for name in names:
        st = content.characters[name]
        pos = (st.position or "").lower()
        actors.append({"id": name, "x": -0.6 if "left" in pos else 0.6 if "right" in pos else None, "pose": st.props and f"holding {', '.join(st.props)}" or "",
                       "expression": st.emotion or "neutral"})
    actors = [{k: v for k, v in a.items() if v not in (None, "")} for a in actors]
    env = content.environment
    return S.normalize_scene({"actors": actors, "lighting": {"key": content.lighting.key, "mood": content.lighting.mood},
                              "props": [{"name": n, "x": 0.3, "z": 0.6} for n in sorted(content.objects)]},
                             subjects=names, framing=FRAMING.get(content.camera.shot_type.value, "medium"),
                             location=env.location or "", time=env.time_of_day or "day", default_lens=content.camera.lens_mm)


def facts_motion(content: Any, preset: Any, *, model: str = "ltx-2.3", seconds: float | None = None) -> dict[str, Any]:
    scene = facts_scene(content)
    duration = float(seconds or content.duration_seconds or 4.0)
    # Facts descriptions are whole sentences ("A man punches a giant gorilla"): they lead the prompt as written
    action = (content.description or content.narration or "").strip().rstrip(".")
    tracks: list[dict[str, Any]] = []
    env = [{"t": 0, "text": action[:140]}] if action else []
    if content.environment.weather and content.environment.weather not in ("clear", ""):
        env.append({"t": 0, "text": f"{content.environment.weather} weather moving in the background"})
    blueprint = S.normalize_motion({"camera": {"move": _move(content.camera.movement)}, "tracks": tracks, "environment": env}, scene,
                                   duration=duration, default_ease="power1.inOut")
    dna = D.from_style_preset(preset) if preset is not None else D.normalize({"medium": content.style or ""})
    prompt = C.motion_prompt(blueprint, scene, dna, {n: n for n in content.characters}, model,
                             location_text=content.environment.location or "")
    return {"prompt": prompt, "blueprint": blueprint, "scene": scene, "dna": dna}
