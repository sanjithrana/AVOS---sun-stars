"""The three ways to make one shot. Each returns (mp4 bytes, info). Every engine can fall back to the still picture with
a camera move, and says so in info["note"], so a finished video always comes out and you can see what was substituted."""
from __future__ import annotations

import json
import os
from typing import Any

import httpx

from .. import models
from . import cinema, prompts
from ..series import media

NEG = ("blurry, low quality, distorted face, extra fingers, warped anatomy, off-model character, changed outfit, "
       "text, letters, numbers, labels, watermark, logo, captions, stiff frozen pose")


def capabilities(s: dict) -> dict:
    """What can be made right now (so the router never plans a shot nothing can make)."""
    # you picked a video model: plan shots for it, and say plainly if it can't run (never quietly swap it)
    ai = media.choice(s, "motion")[0] != "off" and (media.strict(s, "motion") or any(media.usable(s, "motion", m) for m in media.ordered(s, "motion", ["wan-2.2", "ltx-2.3"])))
    lip = media.choice(s, "lipsync")[0] != "off" and any(media.usable(s, "lipsync", m) for m in media.ordered(s, "lipsync", ["infinitetalk", "longcat-avatar"]))
    return {"ai_video": ai, "blender": bool(blender_url()), "lipsync": lip}


def lipsync(s: dict, shot: dict, key: bytes, line: bytes, seconds: float, seed: int, tag: str, prompt: str) -> tuple[bytes, dict]:
    """A speaking shot: the first frame plus the voice line in, a clip with the mouth matching the line out. Raises when no lip-sync model works."""
    errors: list[str] = []
    for mid in media.ordered(s, "lipsync", ["infinitetalk", "longcat-avatar"]):
        if not media._ready(mid):
            continue
        n, fps = media.frames_for(mid, seconds)
        try:
            data = models.run_model(mid, task="avatar", want="video", prompt=prompt, w=s["format"]["width"], h=s["format"]["height"], seconds=seconds,
                                    frames=n, fps=fps, seed=seed, inputs={"image": key, "audio": line}, timeout=2400, tag=tag, backend=media.where(s, "lipsync", mid))
            return data, {"model": mid, "fallback": False, "engine": "lipsync"}
        except Exception as e:  # noqa: BLE001 - the next model, else the caller falls back to normal video
            errors.append(f"{mid}: {str(e)[:160]}")
    raise RuntimeError("; ".join(errors) or "no lip-sync model is ready")


def blender_url() -> str:
    return (os.environ.get("BLENDER_RENDER_URL") or "").rstrip("/")


STYLE = "3D animated look, glossy Pixar-like render, soft studio lighting, saturated colours, shallow depth of field, clean background"


def look(p: dict) -> str:
    """The picture look: your pick, else what the brief asked for, else the default 3D look."""
    return p.get("style") or ((p.get("plan") or {}).get("style")) or STYLE


def shot_prompt(p: dict, shot: dict) -> str:
    return shot_prompt_used(p, shot)[0]


def _lock(p: dict, ids: list[str]) -> str:
    """The character lock: each character's remembered identity, word for word, and that it appears exactly once."""
    chars = {c["id"]: c for c in p["plan"]["characters"]}
    out = []
    for c in ids:
        if c in chars:
            look = " ".join(str(chars[c]["look"]).split()).rstrip(".")
            out.append(f"{chars[c]['name']} (exactly one, identical to the reference in every shot): {look}")
    return "; ".join(out)


def shot_prompt_used(p: dict, shot: dict, moment: str = "start") -> tuple[str, list]:
    """One picture prompt, ordered the way picture models weigh words (first = strongest):
    the shot in one sentence, the locked characters, the action at its most readable instant, props, the set, the camera and
    composition, light, mood and palette, the library recipe, the quality tail, then the hard rules.
    moment="end" draws the shot's LAST frame (its end state), so a shot has a start and an end pose.
    Returns the text and the [[library key, version], ...] it was built from."""
    chars = {c["id"]: c for c in p["plan"]["characters"]}
    props = {x["id"]: x for x in p["plan"]["props"]}
    names = ", ".join(chars[c]["name"] for c in shot["characters"] if c in chars)
    what = "; ".join(f"{props[x]['name']}: {props[x]['look']}" for x in shot["props"] if x in props)
    cam = shot["camera"]
    framing = cinema.phrases(shot) or [f"{shot['camera']['type'].replace('_', ' ')} shot, {cam['lens_mm']}mm lens"]
    size = cinema.SIZES.get(cam.get("type"), "").split(",")[0] or "Cinematic shot"
    act = shot["action"].rstrip(".")
    if moment == "end" and shot.get("end_state"):
        lead = f"{size[0].upper() + size[1:]}, the final moment of the shot: {shot['end_state'].rstrip('.')} (just after: {act})"
    elif moment == "end":
        lead = f"{size[0].upper() + size[1:]}, the moment the action completes: {act}, its result clearly visible"
    else:
        lead = f"{size[0].upper() + size[1:]} of {names or 'the scene'}: {act}, caught at the most telling instant of the movement"
    lock = _lock(p, shot["characters"])
    # the look goes FIRST: free picture services cut long prompts (Pollinations at 900 characters, FLUX at ~256 tokens), and a
    # style at the end was being cut off, which turned the 3D characters into photos of different people
    parts = [f"{look(p)}", lead, lock and f"Characters: {lock}", *framing, shot.get("cam_note"), shot.get("performance") and f"performance: {shot['performance']}",
             what and f"props, exactly as designed: {what}", f"set: {p['plan']['world']['look']}"]
    if shot.get("lighting"):
        parts.append(f"lighting: {shot['lighting']}")
    if shot.get("mood"):
        parts.append(f"mood: {shot['mood']}")
    if shot.get("emotion"):
        parts.append(f"feeling: {shot['emotion']}")
    pal = ", ".join(c["hex"] for c in (p["plan"].get("palette") or [])[:5])
    if pal:
        parts.append(f"colour palette {pal}")
    pid = p.get("id") or ""
    recipe, rv = prompts.pick(f"picture.recipe.{shot['shot_type']}", pid) if f"picture.recipe.{shot['shot_type']}" in prompts.DEFAULTS else ("", 0)
    base, bv = prompts.pick("picture.base", pid)
    used = [[f"picture.recipe.{shot['shot_type']}", rv]] * bool(rv) + [["picture.base", bv]]
    if moment == "end":
        tail, tv = prompts.pick("picture.endframe", pid)
        parts.append(tail)
        used.append(["picture.endframe", tv])
    if recipe:
        parts.insert(5, recipe)
    parts.append(base)
    if shot["characters"]:
        parts.append(f"only these characters are in the picture: {names}; no other people or animals, no duplicates")
    if shot["visualization"]["cross_section"]:
        parts.append("a clean 3D cross-section cutaway showing the inside")
    if shot["visualization"]["force_arrows"]:
        parts.append("glowing translucent 3D arrows and colour flows showing the force, no text")
    parts.append("same art style as every other shot, sharp focus on the subject, correct anatomy and hands, no text, no letters, no captions")
    return ". ".join(x for x in parts if x), used


def end_prompt(p: dict, shot: dict) -> tuple[str, list]:
    return shot_prompt_used(p, shot, "end")


def poster_prompt(p: dict) -> str:
    """The key visual: the hero(es), the main prop and the set in one cinematic frame (the left panel of a production board)."""
    pl = p["plan"]
    who = "; ".join(f"{c['name']}: {c['look']}" for c in pl["characters"][:2])
    what = "; ".join(f"{x['name']}: {x['look']}" for x in pl["props"][:2])
    mood = next((s.get("mood") or s.get("lighting") for s in pl["shots"] if s.get("mood") or s.get("lighting")), "")
    names = ", ".join(c["name"] for c in pl["characters"][:2])
    return ". ".join(x for x in [
        look(p), "Cinematic key visual of the story", pl.get("logline"), who, what, f"set: {pl['world']['look']}", mood and f"lighting and mood: {mood}",
        f"only these characters appear: {names}; no other people or animals",
        prompts.pick("poster.tail", p.get("id") or "")[0], "absolutely no text, no letters, no title, no words, no logo"] if x)


KEEP = prompts.default("motion.keep")


def animation_prompt(p: dict, shot: dict) -> str:
    """What MOVES in this shot, written the way image-to-video models follow best: the camera move and the one main action in
    the first sentence (strong verbs, real speed and weight), then secondary motion, then timed beats and the exact end frame.
    The picture already holds who/where/style, so this never re-describes the look."""
    who = ", ".join(c["name"] for c in p["plan"]["characters"] if c["id"] in shot["characters"])
    things = ", ".join(x["name"] for x in p["plan"]["props"] if x["id"] in shot["props"])
    moving = shot["action"].rstrip(".")
    move = cinema.MOVES.get(shot["camera"].get("movement"), "steady camera").split(",")[0]
    bits = [f"{move[0].upper() + move[1:]} as {moving}."]
    if shot.get("cam_note"):
        bits.append(f"Camera: {shot['cam_note']}.")
    if shot.get("performance"):
        bits.append(f"Performance: {shot['performance'].rstrip('.')}.")
    if shot.get("objective"):
        bits.append(f"The character is trying to: {shot['objective'].rstrip('.')}.")
    if who:
        bits.append(f"{who} moves with real weight and follow-through: weight shifts, the head leads the turn, hands finish the gesture, clothes and hair settle after the move.")
    if things:
        bits.append(f"{things} move only as the action makes them move, with believable physics, and keep their shape and colour.")
    if shot.get("lighting") or shot.get("mood"):
        bits.append(f"Light and mood stay: {'; '.join(x for x in (shot.get('lighting'), shot.get('mood')) if x)}.")
    bits.append("Background has small living motion (light flicker, dust in the air, a soft breeze) but nothing new enters the frame.")
    if shot["visualization"]["force_arrows"]:
        bits.append("Glowing translucent arrows flow along the force direction and pulse with the action.")
    bits.append(beats(float(shot.get("seconds") or 4)))
    if shot.get("end_state"):
        bits.append(f"End exactly on: {shot['end_state'].rstrip('.')}.")
    if shot.get("continuity"):
        bits.append(f"Keep unchanged: {shot['continuity'].rstrip('.')}.")
    return " ".join(bits)


def beats(seconds: float) -> str:
    """Timed beats so the model knows when things happen: establish, main move, reveal, a readable hold."""
    a, b, c = round(seconds * 0.2, 1), round(seconds * 0.6, 1), round(seconds * 0.85, 1)
    return (f"Timing: 0-{a}s establish the opening pose; {a}-{b}s the main movement; {b}-{c}s the result or reaction; "
            f"{c}-{round(seconds, 1)}s hold a clear, readable final pose for the cut.")


def motion_prompt(prompt: str, mv: str, sfx: str | None = "", pid: str = "") -> str:
    """The image-to-video prompt: opens from the picture, one action, an explicit camera move, and the keep-the-look rules."""
    body = prompt.strip().rstrip(".")
    if not body.lower().startswith("starting from"):
        body = "Starting from the attached image. " + body
    return f"{body}. Camera: {mv}. {prompts.pick('motion.keep', pid)[0]}" + (f" Sound: {sfx}." if sfx else "")


def ai_video(s: dict, shot: dict, key: bytes, seconds: float, seed: int, prompt: str, tag: str) -> tuple[bytes, dict]:
    errors: list[str] = []
    W, H = s["format"]["width"], s["format"]["height"]
    mv = shot["camera"]["movement"].replace("_", " ")
    for mid in media.ordered(s, "motion", ["wan-2.2", "ltx-2.3"] if seconds <= 5.2 else ["ltx-2.3", "wan-2.2"]):
        if not media.strict(s, "motion") and not media.usable(s, "motion", mid):
            continue
        n, fps = media.frames_for(mid, seconds)
        full = motion_prompt(prompt, mv, shot.get("sfx") if mid == "ltx-2.3" else "", s.get("id") or "")
        try:
            data = models.run_model(mid, task="video", want="video", prompt=full, w=W, h=H, seconds=seconds, frames=n, fps=fps, seed=seed,
                                    inputs={"image": key}, negative=NEG, timeout=2400, tag=tag, backend=media.where(s, "motion", mid))
            return data, {"engine": "ai_video", "model": mid, "fallback": False}
        except Exception as e:  # noqa: BLE001 - provider failing (no credit, offline): the next model, else the still
            errors.append(f"{mid}: {str(e)[:160]}")
    if media.strict(s, "motion") or media.local_only(s):       # you picked this video model: no stand-in
        raise media.Fallback("The video model you chose could not make this shot: " + ("; ".join(errors)[:400] or "it isn't ready") +
                             ". Nothing else was tried (set Video to Automatic to allow a picture-with-camera-move instead).")
    return still(s, shot, key, seconds, "; ".join(errors)[:300] or "no AI video model is ready", shot.get("_end"))


def still(s: dict, shot: dict, key: bytes, seconds: float, why: str = "", end: bytes | None = None) -> tuple[bytes, dict]:
    """No video model: a key-pose animatic when the shot has a last frame (first frame -> last frame with the camera moving
    through both), else the first frame with a camera move."""
    kind = media.STILL_MOVES.get(shot["camera"]["movement"], "push")
    if end:
        try:
            return keypose(s, key, end, seconds, kind), {"engine": "still", "mode": "keypose", "model": "key-pose animatic", "fallback": bool(why),
                                                        "note": (why + "; " if why else "") + "key-pose animatic: first frame to last frame"}
        except Exception as e:  # noqa: BLE001 - ffmpeg without xfade: the single picture
            why = (why + "; " if why else "") + f"key-pose blend failed ({str(e)[:80]})"
    return media.still_motion(s, key, seconds, kind), {"engine": "still", "model": "still", "fallback": bool(why),
                                                        "note": why or "picture with camera move (your choice)"}


def keypose(s: dict, first: bytes, last: bytes, seconds: float, kind: str) -> bytes:
    """Two key poses joined by a soft cross-dissolve while the camera keeps moving: reads as the action happening."""
    import subprocess
    import tempfile
    from pathlib import Path
    from .. import config
    blend = min(1.0, max(0.5, seconds * 0.22))
    a = round(seconds * 0.5 + blend / 2, 2)
    b = round(seconds - a + blend, 2)
    with tempfile.TemporaryDirectory() as t:
        pa, pb, out = Path(t) / "a.mp4", Path(t) / "b.mp4", Path(t) / "k.mp4"
        pa.write_bytes(media.still_motion(s, first, a, kind))
        pb.write_bytes(media.still_motion(s, last, b, kind))
        r = subprocess.run([config.ffmpeg(), "-y", "-v", "error", "-i", str(pa), "-i", str(pb), "-filter_complex",
                            f"[0:v][1:v]xfade=transition=fade:duration={blend}:offset={round(a - blend, 2)},format=yuv420p[v]",
                            "-map", "[v]", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", str(out)], capture_output=True, text=True)
        if r.returncode:
            raise RuntimeError((r.stderr or "")[-200:])
        return out.read_bytes()


# ---------- Blender ----------
PROP_TYPES = (("ball", "sphere"), ("potato", "sphere"), ("sphere", "sphere"), ("orb", "sphere"), ("balloon", "balloon"), ("coin", "coin"),
              ("rock", "rock"), ("tree", "tree"), ("wall", "wall"), ("pillar", "pillar"))
COLOURS = {"red": "#d33", "blue": "#3366dd", "green": "#33aa55", "yellow": "#f2c230", "brown": "#8a5a2b", "orange": "#ee8822",
           "purple": "#8844cc", "pink": "#ee77aa", "white": "#f2f2f2", "black": "#222", "grey": "#888", "gray": "#888"}
MOVES = {"push_in": "push_in", "pull_out": "pull_out", "orbit": "orbit", "pan_right": "pan", "pan_left": "pan", "static": "static",
         "tilt_up": "low_angle", "tilt_down": "static"}


def scene_spec(p: dict, shot: dict, seconds: float, w: int, h: int) -> dict:
    """The shot as the plain, validated scene the Blender service accepts (never code from the AI)."""
    props = {x["id"]: x for x in p["plan"]["props"]}
    out_props = []
    for i, pid in enumerate(shot["props"][:6]):
        text = f"{props.get(pid, {}).get('name', '')} {props.get(pid, {}).get('look', '')}".lower()
        typ = next((t for k, t in PROP_TYPES if k in text), "box")
        col = next((c for k, c in COLOURS.items() if k in text), "#cccccc")
        out_props.append({"type": typ, "position": [(i - (len(shot['props']) - 1) / 2) * 0.9, 0.0, 0.5], "scale": 0.5,
                          "color": col, "material": "glass" if shot["visualization"]["cross_section"] else "plastic",
                          "motion": "float" if shot["visualization"]["force_arrows"] else "none"})
    actors = [{"id": "a1", "asset": "mannequin", "variant": "man", "action": "point" if shot["shot_type"] != "reaction" else "shocked",
               "position": [0, 1.2], "facing": 0, "scale": 1.0}] if shot["characters"] and shot["shot_type"] != "scientific_cutaway" else []
    close = shot["camera"]["type"] in ("close_up", "macro_close_up", "cutaway")
    return {"environment": "grid_studio", "duration": round(seconds, 2), "fps": 24, "width": w, "height": h, "engine": "eevee", "samples": 16,
            "seed": int(shot["index"]) * 7, "actors": actors, "props": out_props,
            "camera": {"shot": "close" if close else "medium", "move": MOVES.get(shot["camera"]["movement"], "push_in"), "target": "a1" if actors else ""}}


def blender(s: dict, p: dict, shot: dict, key: bytes, seconds: float) -> tuple[bytes, dict]:
    W, H = s["format"]["width"], s["format"]["height"]
    scene = scene_spec(p, shot, seconds, W // 2 * 2, H // 2 * 2)
    try:
        r = httpx.post(blender_url() + "/render", json=scene, timeout=1800)
        r.raise_for_status()
        if len(r.content) < 2000:
            raise RuntimeError("Blender returned an empty video")
        return r.content, {"engine": "blender", "model": "blender", "fallback": False, "scene": scene}
    except Exception as e:  # noqa: BLE001 - not running / failing: the picture with a camera move
        data, info = still(s, shot, key, seconds, f"Blender: {str(e)[:200]}")
        info["scene"] = scene
        return data, info
