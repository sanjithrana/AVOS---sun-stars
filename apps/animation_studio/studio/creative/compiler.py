"""Prompt compiler: scene graph + motion blueprint + design DNA → the exact text each model gets.

Deterministic (same inputs → byte-identical prompts and the same params_hash), so a shot is reproducible and a redo
changes only what was edited. The AI decides WHAT; the scene graph WHERE; the blueprint WHEN; the renderer (LTX, Wan,
InfiniteTalk…) only HOW IT LOOKS: swapping the renderer changes the phrasing table below, nothing else.

    keyframe_prompt(scene, dna, names, refs)    the picture model (Qwen-Image-Edit / Z-Image / FLUX)
    motion_prompt(motion, scene, dna, names, model)   the video model, phrased the way that model reads best
    compile_shot(...)                           both, plus negative prompt, size and params_hash
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from . import dna as D
from .scene import camera_at

CAMERA_WORDS = {
    "static": "The camera holds still", "push_in": "The camera slowly pushes in", "pull_out": "The camera slowly pulls back",
    "pan_left": "The camera pans left", "pan_right": "The camera pans right", "truck_left": "The camera tracks sideways to the left",
    "truck_right": "The camera tracks sideways to the right", "tilt_up": "The camera tilts up", "tilt_down": "The camera tilts down",
    "crane_up": "The camera rises", "crane_down": "The camera lowers", "orbit_left": "The camera arcs around to the left",
    "orbit_right": "The camera arcs around to the right", "zoom_in": "The lens zooms in", "handheld": "Gentle handheld camera",
}
EASE_WORDS = {"none": "at a steady speed", "power1": "easing gently in and out", "power2": "with a smooth ease",
              "power3": "with a quick, punchy ease", "sine": "softly", "expo": "with a dramatic ease"}
LENS_WORDS = [(20, "ultra-wide lens"), (30, "wide lens"), (45, "normal lens"), (70, "short telephoto lens, soft background"),
              (999, "telephoto lens, shallow depth of field")]


def _lens(mm: int) -> str:
    return next(w for limit, w in LENS_WORDS if mm < limit) + f" ({mm}mm)"


def _angle(cam: dict[str, Any]) -> str:
    dy = cam["position"][1] - cam["target"][1]
    dist = max(0.1, abs(cam["position"][2] - cam["target"][2]) + abs(cam["position"][0] - cam["target"][0]))
    r = dy / dist
    return "high angle" if r > 0.35 else "low angle" if r < -0.15 else "eye level"


def _where(x: float, z: float) -> str:
    h = "on the left" if x < -0.3 else "on the right" if x > 0.3 else "in the centre"
    d = " in the foreground" if z > 1.0 else " in the background" if z < -1.0 else ""
    return h + d


def keyframe_prompt(scene: dict[str, Any], dna: dict, names: dict[str, str], refs: list[str] | None = None,
                    location_text: str = "", note: str = "") -> str:
    """refs: what each reference picture is, in order (e.g. ["Raju's character sheet", "the kitchen"])."""
    parts: list[str] = []
    if refs:
        parts.append("; ".join(f"picture {i + 1} is {r}" for i, r in enumerate(refs)) + ".")
    cam = scene["camera"]
    parts.append(f"ONE frame of an animated film: {scene['framing']} shot, {_angle(cam)}, {_lens(cam['lens'])}.")
    for a in scene["actors"]:
        n = names.get(a["id"], a["id"])
        facing = "facing the camera" if a["facing"] == "camera" else f"facing {names.get(a['facing'], a['facing'])}"
        talk = ", mouth open mid-word, the one speaking" if a.get("speaking") else ""
        parts.append(f"{n} {_where(a['x'], a['z'])}: {a['pose']}, {a['expression']} expression, {facing}{talk}.")
    if len(scene["actors"]) > 1 and any(a.get("speaking") for a in scene["actors"]):
        parts.append("Everyone else keeps their mouth closed and listens.")
    for p in scene["props"]:
        held = f", held by {names.get(p['held_by'], p['held_by'])}" if p.get("held_by") else f" {_where(p['x'], p['z'])}"
        parts.append(f"Prop: {p['name']}{held}.")
    loc = location_text or scene["location"]
    parts.append(f"Place: {loc}, {scene['time']}. Lighting: {scene['lighting']['key']}, {scene['lighting']['mood']} mood.")
    if refs:
        parts.append("Every character looks exactly like their sheet (face, hair, outfit, colours); keep the place's look.")
    parts.append(D.style_clause(dna))
    if note:
        parts.append(f"Change: {note}.")
    parts.append("No text, no captions, no speech bubbles, no panel borders.")
    return " ".join(parts)


def _beats(motion: dict[str, Any], names: dict[str, str]) -> list[tuple[float, str]]:
    out = []
    for tr in motion["tracks"]:
        n = names.get(tr["target"], tr["target"])
        for k in tr["keys"]:
            out.append((k["t"], f"{n} {k['action']}"))
    for e in motion["environment"]:
        out.append((e["t"], e["text"]))
    return sorted(out, key=lambda x: x[0])


REFERENCE = ("Use the first frame as the exact visual reference: the same characters, faces, costumes, art style, lighting and "
             "place.")
KEEP = "No character redesign, no face change, no costume change."


def motion_prompt(motion: dict[str, Any], scene: dict[str, Any], dna: dict, names: dict[str, str], model: str = "ltx-2.3",
                  note: str = "", emotion: str = "", location_text: str = "") -> str:
    beats = _beats(motion, names)
    cam = motion["camera"]
    cam_text = CAMERA_WORDS.get(cam["move"], "The camera holds still")
    if cam["move"] not in ("static", "handheld"):
        cam_text += " " + EASE_WORDS.get(cam["ease"].split(".")[0], "smoothly")
    style = D.style_clause(dna)
    anim = D.motion_clause(dna)
    speaker = names.get(motion.get("lipsync") or "", "")
    if model in ("infinitetalk", "longcat-avatar"):
        who = speaker or (names.get(scene["actors"][0]["id"]) if scene["actors"] else "The character")
        acts = "; ".join(t for _, t in beats) or "natural gestures"
        return (f"{who} talks{(' ' + emotion) if emotion and emotion != 'neutral' else ''}, lips in sync with the speech, "
                f"natural blinking and head movement; {acts}. {cam_text}. {anim} {style} {KEEP}" + (f" {note}." if note else ""))
    timed = " ".join(f"At {t:.1f}s, {txt}." if i else f"{txt[0].upper()}{txt[1:]}." for i, (t, txt) in enumerate(beats)) \
        or "Subtle natural movement, breathing, blinking."
    if model == "ltx-2.3":
        # LTX reads one flowing, chronological paragraph: the main action first, then details, camera, light, look
        who = ", ".join(names.get(a["id"], a["id"]) for a in scene["actors"]) or "the scene"
        return (f"{timed} The shot shows {who} in {location_text or scene['location']} ({scene['time']}), {scene['framing']} framing. "
                f"{cam_text}. Lighting: {scene['lighting']['key']}, {scene['lighting']['mood']} mood. {anim} {style} "
                f"{REFERENCE} {KEEP}" + (f" {note}." if note else ""))
    # Wan 2.2 and others: the storyboard-frame template (reference → only this shot → camera → motion → keep)
    return (f"{REFERENCE} Animate only this shot: {timed} Camera movement: {cam_text[0].lower()}{cam_text[1:]}. {anim} {style} {KEEP}"
            + (f" {note}." if note else ""))


def compile_shot(scene: dict[str, Any], motion: dict[str, Any], dna: dict, names: dict[str, str], *, model: str,
                 refs: list[str] | None = None, location_text: str = "", width: int = 1280, height: int = 720,
                 note: str = "", emotion: str = "") -> dict[str, Any]:
    out = {"keyframe_prompt": keyframe_prompt(scene, dna, names, refs, location_text, note),
           "motion_prompt": motion_prompt(motion, scene, dna, names, model, note, emotion, location_text),
           "negative_prompt": D.negative(dna), "model": model, "width": width, "height": height,
           "duration": motion["duration"], "camera_start": motion["camera"]["from"], "camera_end": camera_at(motion, motion["duration"])}
    out["params_hash"] = hashlib.sha256(json.dumps(out, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    return out
