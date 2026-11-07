"""ASMR Cooking skill: name a dish, get a hyper-realistic vertical cooking video.

One look is locked for every shot so the video cuts together as one piece: matte-black latex gloves (never a face, never a person),
a pristine white board against a pitch-black background, softbox light and a macro lens. The AI writes the recipe and the shot list;
the look, the camera and the sound are built here in code, so they cannot drift shot to shot.

The pipeline: recipe and shot list -> one picture per shot (each drawn from the one before, so the food keeps its state) -> one clip
per shot (Seedance with its own ASMR sound, or a macro camera move on the picture) -> joined with the kitchen foley under it.

Ingredient continuity runs raw -> washed -> peeled -> chopped -> seasoned -> cooked -> plated, and every shot states what is left
over from the shot before it, so nothing appears or vanishes between cuts.
"""
from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from ..series import media, writers
from . import base, store

ID = "asmr-cooking"
INFO = {
    "id": ID, "name": "ASMR Cooking", "group": "Food and ASMR", "kind": "recipe",
    "made_for": "Name a dish: it writes the recipe and the shot list, then makes a hyper-realistic cooking video with black gloves and ASMR sound",
    "about": "One locked look for every shot - matte-black latex gloves, a pristine white board on a pitch-black background, softbox light and a macro "
             "lens, never a face. The AI writes the recipe and a shot list that walks the ingredients from raw to plated; each shot is drawn from the "
             "one before it so nothing appears or vanishes, then animated and given its own kitchen sound (sizzle, chop, pour, simmer).",
    "input": "A dish, e.g. cheese corn nuggets, paneer butter masala, garlic butter prawns",
    "outputs": ["Recipe and shot list", "Shot pictures", "ASMR video"],
    "aspect": "9:16", "aspects": ["9:16", "16:9"], "seconds": [30, 45, 60, 90, 120, 180], "default_seconds": 45, "native_audio": True,
    "examples": ["cheese corn nuggets", "paneer butter masala", "chocolate lava cake", "garlic butter prawns", "masala dosa", "Korean corn dogs"],
    "credit": "Workflow modelled on the 'Hyper-Realistic ASMR Cooking Studio' skill.",
    "make": [["media", "Recipe, shots and video"], ["prompts", "Recipe and prompts only"]],
    "motions": [["video", "AI video for every shot with its own sound (Seedance, needs fal.ai credit)"],
                ["macro", "Macro camera move on each picture + kitchen sound made in code (free)"]],
}

# ---------- the locked look (every picture prompt carries it word for word) ----------
HANDS = ("a pair of hands in sleek matte-black latex gloves with a clean sharp manicure, precise professional culinary movements, consistent hand "
         "proportions, no arms above the wrist, no face and no person visible")
SURFACE = ("a pristine white matte chopping board on a matte white counter, set against a pitch-black minimalist background with deep shadow contrast")
LIGHT = ("cinematic studio softbox lighting, overhead softbox illumination with a warm directional key light, shallow depth of field, f/2.8 macro lens "
         "look, vibrant natural colour grading, every droplet and crumb sharp")
NEVER = "No text, no letters, no logos, no labels, no watermarks, no faces, no people, no clutter, no props that do not belong to the recipe."
LOOK = f"Hyper-realistic macro food photography on {SURFACE}, {LIGHT}"

CAMERAS = {"top-down": "a locked top-down overhead macro shot", "45-degree": "a 45-degree macro shot just above the board",
           "eye-level": "a low eye-level macro shot level with the board", "side": "a tight side-on macro shot across the board",
           "close": "an extreme close-up macro shot, the subject filling the frame"}
STATES = ("raw", "washed", "peeled", "chopped", "seasoned", "cooked", "plated")
WORK = [("teaser", "the raw ingredients in their raw state, grouped on the board, nothing cut yet"),
        ("prep", "cutting and precision prep on the white board: slicing, dicing, peeling or grating"),
        ("season", "spicing, seasoning and tactile mixing in a matte-black or clear glass bowl"),
        ("assembly", "assembly and coating: dipping, breading, pouring or layering"),
        ("climax", "the cooking climax and the plating: high heat, sizzling, bubbling, then the finished dish and a macro reveal")]

SHOT_SECONDS = (3.0, 6.0)                 # one action per shot: shorter than this reads as a glitch, longer drags

RECIPE = """You are the director of a hyper-realistic ASMR cooking channel: vertical macro videos where two black-gloved hands cook a dish on a white board against a black background, with no voice and no music, only the sound of the cooking. You are given a dish and a number of shots. You write the real recipe and then the shot list.
RULES
- Use a real, correct recipe for the dish. Real ingredients, real quantities, real method, in the right order. If the dish is regional, keep it authentic.
- ONE action per shot. A shot shows one thing happening: one cut, one pour, one mix, one fry. Never two.
- The shots walk the whole recipe in order through five stages: 1 raw ingredients laid out, 2 cutting and prep, 3 seasoning and mixing, 4 assembly or coating, 5 the cooking and the plating. Spend the most shots on whichever stages this dish actually needs.
- CONTINUITY: ingredients move raw -> washed -> peeled -> chopped -> seasoned -> cooked -> plated and never jump backwards. Every shot's "state" says what is already done and what is still visible from the shot before it (the bowl of chopped onion still at the back of the board, the empty shells, the dusting of flour).
- Never show a face, a person, an arm above the wrist, a brand, a label or any text.
Each shot has:
- "title": 2-5 words, the action, e.g. "Slicing the onion"
- "stage": teaser|prep|season|assembly|climax
- "state": one sentence naming what is already done and what is still on the board from the shot before
- "subject": exactly what is in frame - the food in its current state, the tool, the bowl or pan, with colours and textures
- "action": what the gloved hands do, as one physical movement
- "physics": what the food does - steam, oil splatter, bubbling viscosity, knife pressure, the way the liquid falls, crumbs scattering
- "asmr": the sound, in the words of the sound itself, e.g. "crisp dry crunch", "loud oil sizzle tsssss", "heavy liquid splash", "soft knife thud on the board"
- "camera": top-down|45-degree|eye-level|side|close
Answer with ONE JSON object:
{"title":"the dish, title case","ingredients":["quantity + ingredient", ...],"tools":["the tools and vessels used"],"shots":[{...}, ...]}"""


def shots_for(total: float) -> int:
    """How many shots a video of this length holds: one action each, three to six seconds."""
    return max(5, min(40, round(float(total) / 4.2)))


def seconds_each(total: float, n: int) -> float:
    lo, hi = SHOT_SECONDS
    return max(lo, min(hi, float(total) / max(1, n)))


INFO["lengths"] = [{"seconds": n, "scenes": shots_for(n), "each": round(seconds_each(n, shots_for(n)), 1)} for n in INFO["seconds"]]


def subject_of(text: str) -> str:
    t = " ".join(str(text or "").split())
    m = re.search(r"(?:make|cook|recipe for|how to make)\s+(.+)", t, re.I)
    return (m.group(1) if m else re.split(r"[.!?\n]", t)[0]).strip(" .,'\"")[:120] or "a dish"


def _s(v: Any, n: int, fb: str = "") -> str:
    v = " ".join(str(v or "").split())
    return v[:n] if v else fb


def norm_recipe(d: Any, dish: str, n: int) -> dict:
    if not isinstance(d, dict) or not isinstance(d.get("shots"), list) or not d["shots"]:
        raise writers.WriterError("The AI writer didn't return a usable shot list. Try again, or pick another AI crew.")
    shots = []
    for i, sh in enumerate(d["shots"][:n]):
        sh = sh if isinstance(sh, dict) else {}
        stage = _s(sh.get("stage"), 12, "").lower()
        stage = stage if stage in {k for k, _ in WORK} else WORK[min(i * len(WORK) // max(1, n), len(WORK) - 1)][0]
        cam = _s(sh.get("camera"), 12, "").lower()
        shots.append({"n": i + 1, "title": _s(sh.get("title"), 60, f"Step {i + 1}"), "stage": stage,
                      "state": _s(sh.get("state"), 300, "the board as it was left in the shot before"),
                      "subject": _s(sh.get("subject"), 400, dish), "action": _s(sh.get("action"), 300, "the gloved hands work on the board"),
                      "physics": _s(sh.get("physics"), 300, ""), "asmr": _s(sh.get("asmr"), 160, "soft handling sounds"),
                      "camera": cam if cam in CAMERAS else ("top-down" if i % 2 else "45-degree"),
                      "picture": None, "video": None})
    if len(shots) < n:
        raise writers.WriterError(f"The AI writer wrote {len(shots)} of {n} shots. Try again.")
    return {"title": _s(d.get("title"), 90, dish.title()),
            "ingredients": [_s(x, 90) for x in (d.get("ingredients") or []) if str(x).strip()][:20],
            "tools": [_s(x, 60) for x in (d.get("tools") or []) if str(x).strip()][:12], "shots": shots}


def recipe(s: dict, dish: str, n: int, log: Callable[[dict], None] | None = None, secs: float = 4.2) -> dict:
    if not writers.uses_ai(s):
        raise writers.WriterError("ASMR Cooking needs an AI writer for the recipe (pick Groq or another AI crew in Models).")
    system = writers.system("avos-asmr-cooking", RECIPE)
    stages = "; ".join(f"{i + 1} {what}" for i, (_, what) in enumerate(WORK))
    ask = (f"Dish: {dish}\nWrite exactly {n} shots. The five stages in order: {stages}.\nEach shot is on screen for about "
           f"{round(secs, 1)} seconds, so it holds ONE action.\nWrite the JSON.")
    return norm_recipe(writers.ask(s, "story", system, ask, log, max_tokens=4000, temperature=0.5), dish, n)


# ---------- prompts ----------
def _sentence(text: str) -> str:
    """A clause from the writer, turned into its own sentence so the prompt does not read as one run-on line."""
    t = " ".join(str(text or "").split()).rstrip(".")
    return f" {t[:1].upper()}{t[1:]}." if t else ""


def image_prompt(r: dict, sh: dict, aspect: str = "9:16") -> str:
    """One shot's picture. The look leads, because the free picture models weigh the opening words most and cut long prompts."""
    shape = "vertical 9:16 framing" if aspect == "9:16" else "horizontal 16:9 framing"
    return (f"{LOOK}, {shape}. {CAMERAS.get(sh['camera'], CAMERAS['top-down']).capitalize()} of {sh['subject'].rstrip('.')}. "
            f"{HANDS}, mid-action: {sh['action'].rstrip('.')}.{_sentence(sh.get('physics'))} "
            f"Already done in this scene: {sh['state'].rstrip('.')}. "
            f"Real food, real texture, every crumb and droplet in focus. {NEVER}")


NEGATIVE = ("face, person, portrait, arm, elbow, bare hand, white gloves, text, letters, numbers, logo, label, packaging text, watermark, caption, "
            "cartoon, illustration, 3d render, plastic food, messy background, cluttered counter, blurry, low detail, extra fingers, deformed hands")


def motion_prompt(sh: dict, secs: float = 4.0) -> str:
    """The image-to-video prompt: the picture is the first frame, one action happens, the sound is the shot's own ASMR."""
    return (f"Animate this exact photograph as a {round(secs)}-second hyper-realistic macro cooking shot. Keep the frame, the matte-black latex gloves, "
            f"the white board, the pitch-black background and the lighting exactly as they are. One thing happens: "
            f"{sh['action'].rstrip('.')}.{_sentence(sh.get('physics'))} "
            f"{CAMERAS.get(sh['camera'], CAMERAS['top-down']).capitalize()}, the camera barely moves - a slow push or a small drift, nothing more. "
            "Real physics and real weight: food deforms, liquids fall and splash, steam rises, oil spits, crumbs scatter. No face, no person, no arm "
            f"above the wrist, no new objects, no cuts, no text. Sound: close ASMR of the action only - {sh['asmr'].rstrip('.')} - with quiet kitchen "
            "air under it. No music, no voice, no narration.")


def prompts_of(r: dict, aspect: str, secs: float) -> list[dict]:
    return [{"n": sh["n"], "title": sh["title"], "stage": sh["stage"], "state": sh["state"], "asmr": sh["asmr"],
             "camera": sh["camera"], "image": image_prompt(r, sh, aspect), "motion": motion_prompt(sh, secs)} for sh in r["shots"]]


# ---------- stages ----------
STAGES = ("recipe", "pictures", "motion", "finish")
LABELS = {"recipe": "Recipe and shot list", "pictures": "Shot pictures", "motion": "Motion and sound", "finish": "Final video"}


def _w_h(p: dict) -> tuple[int, int]:
    return base.SIZES.get(p.get("aspect") or "9:16", base.SIZES["9:16"])


def _each(p: dict) -> float:
    shots = ((p.get("recipe") or {}).get("shots") or [])
    return seconds_each(float(p.get("seconds") or 45), len(shots) or shots_for(float(p.get("seconds") or 45)))


def do_recipe(pid: str) -> None:
    p = store.load(pid)
    base.step(pid, "recipe", status="working")
    total = float(p.get("seconds") or 45)
    n = shots_for(total)
    r = recipe(base.sdict(p), p["subject"], n, base.logger(pid), seconds_each(total, n))
    base.put(pid, recipe=r, title=r["title"], prompts=prompts_of(r, p.get("aspect") or "9:16", seconds_each(total, len(r["shots"]))))
    base.step(pid, "recipe", status="done", note=f"{len(r['shots'])} shots, {len(r['ingredients'])} ingredients")


def do_pictures(pid: str) -> None:
    """Each shot is drawn from the shot before it, so the food keeps the state it was left in."""
    p = store.load(pid)
    s, (w, h) = base.sdict(p), _w_h(p)
    base.step(pid, "pictures", status="working")
    prev: bytes | None = None
    for sh in p["recipe"]["shots"]:
        base.check(pid)
        if sh.get("picture") and store.file_path(pid, sh["picture"]):
            prev = base.read(pid, sh["picture"]) or prev
            continue
        prompt = image_prompt(p["recipe"], sh, p.get("aspect") or "9:16")
        seed = media.seed_of(pid, sh["n"], p.get("version", 1))
        img, info = media.picture(prompt, [prev] if prev else [], w, h, seed, f"{pid}-S{sh['n']}", s=s, negative=NEGATIVE)
        name = base.write(pid, f"S{sh['n']:02d}.png", img)
        model = str(info.get("model") or "")
        store.update(pid, lambda q, n=sh["n"], name=name, m=model: q["recipe"]["shots"][n - 1].update(picture=name, picture_model=m))
        prev = img
        if sh["n"] == 1:
            base.put(pid, thumb=name)
    base.step(pid, "pictures", status="done", note=f"{len(p['recipe']['shots'])} shots drawn, each from the one before")


def _macro_clip(src, out, w: int, h: int, secs: float, kind: str, ffmpeg: str):
    """A macro camera move on the still: the free stand-in for a video model. zoompan does it in ffmpeg, so it stays fast."""
    import subprocess
    fps, n = 24, max(2, round(secs * 24))
    z = {"in": "min(zoom+0.0012,1.22)", "out": f"max(1.22-(on/{n})*0.22,1.0)"}.get(kind, "min(zoom+0.0012,1.22)")
    x = {"left": f"(iw-iw/zoom)*(1-on/{n})", "right": f"(iw-iw/zoom)*(on/{n})"}.get(kind, "iw/2-(iw/zoom/2)")
    vf = (f"scale={w * 2}:{h * 2}:force_original_aspect_ratio=increase,crop={w * 2}:{h * 2},"
          f"zoompan=z='{z}':d={n}:x='{x}':y='ih/2-(ih/zoom/2)':s={w}x{h}:fps={fps},format=yuv420p")
    subprocess.run([ffmpeg, "-v", "error", "-y", "-loop", "1", "-i", str(src), "-t", f"{secs:.3f}", "-vf", vf,
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "19", str(out)], check=True)
    return out


MOVES = ("in", "left", "out", "right")


def do_motion(pid: str) -> None:
    from .. import config
    from ..stickman import video
    p = store.load(pid)
    s = base.sdict(p)
    w, h = _w_h(p)
    secs = _each(p)
    base.step(pid, "motion", status="working")
    d = store.pdir(pid)
    want_video = (p.get("motion") or "video") == "video" and video.ready(s)
    if (p.get("motion") or "video") == "video" and not want_video:
        store.say(pid, "No video model is ready (add a fal.ai key with credit in Settings), so each shot gets a macro camera move and the kitchen "
                       "sound made in code. The video still gets made.", "warn")
    kinds: list[str] = []
    for sh in p["recipe"]["shots"]:
        base.check(pid)
        if sh.get("video") and store.file_path(pid, sh["video"]):
            continue
        img = base.read(pid, sh.get("picture"))
        if not img:
            raise RuntimeError(f"shot {sh['n']} has no picture yet")
        out = d / f"S{sh['n']:02d}.mp4"
        made = False
        if want_video:
            try:
                out.write_bytes(video.clip(motion_prompt(sh, secs), [img], None, round(secs), p.get("aspect") or "9:16", audio=True))
                made, _ = True, kinds.append("Seedance 2.0")
            except Exception as e:  # noqa: BLE001 - a finished video beats a stopped run
                want_video = False
                store.say(pid, f"Shot {sh['n']}: the AI video failed ({str(e)[:160]}). Carrying on with macro camera moves and the kitchen sound made "
                               "in code for the rest of this run.", "warn")
        if not made:
            still = d / f"S{sh['n']:02d}_still.png"
            still.write_bytes(img)
            _macro_clip(still, out, w, h, secs, MOVES[(sh["n"] - 1) % len(MOVES)], config.ffmpeg())
            kinds.append("macro move")
        store.update(pid, lambda q, n=sh["n"], name=out.name: q["recipe"]["shots"][n - 1].update(video=name))
    base.step(pid, "motion", status="done", model=" + ".join(sorted(set(kinds))) or None,
              note="" if kinds == ["Seedance 2.0"] * len(kinds) else "Macro camera moves, with the kitchen sound synthesised per shot from its ASMR line.")


def do_finish(pid: str) -> None:
    from ..series import assemble
    from ..stickman import video
    from . import foley
    p = store.load(pid)
    w, h = _w_h(p)
    secs = _each(p)
    base.step(pid, "finish", status="working")
    d = store.pdir(pid)
    work = d / "work"
    work.mkdir(exist_ok=True)
    parts, total, made = [], 0.0, 0
    for sh in p["recipe"]["shots"]:
        clip = d / (sh.get("video") or "")
        if not clip.is_file():
            raise RuntimeError(f"shot {sh['n']} has no clip yet")
        fit = assemble.fit_shot(clip, work / f"S{sh['n']:02d}_fit.mp4", secs, w, h)
        sfx = None
        if not video.has_audio(clip):                     # Seedance brings its own sound; a macro move does not
            sfx = work / f"S{sh['n']:02d}.wav"
            sfx.write_bytes(foley.wav(sh.get("asmr") or "", secs, seed=sh["n"] * 17))
            made += 1
        aud = assemble.shot_audio(work / f"S{sh['n']:02d}_a.wav", secs, None, sfx, line_at=0.0)
        parts.append({"video": fit, "audio": aud, "seconds": secs})
        total += secs
    joined = assemble.part(parts, work, work / "joined.mp4", w, h, None, [])
    import shutil
    shutil.copyfile(joined, d / "final.mp4")
    base.put(pid, video="final.mp4", finalSeconds=round(total, 1))
    base.step(pid, "finish", status="done",
              note=f"No music, as the look asks: {made} shot(s) carry kitchen sound made in code" if made else "No music: the shots carry their own sound")


RUN = {"recipe": do_recipe, "pictures": do_pictures, "motion": do_motion, "finish": do_finish}


def last_stage(p: dict) -> str:
    return "recipe" if p.get("media") == "prompts" else "finish"


def reset(p: dict, step: str, n: int | None = None) -> None:
    """Clear what `step` (and every later step) made. With n: only that shot."""
    order = STAGES[STAGES.index(step):]
    for st in order:
        p.setdefault("steps", {}).pop(st, None)
    if "recipe" in order:
        p.pop("recipe", None)
        p.pop("prompts", None)
        return
    for sh in (p.get("recipe") or {}).get("shots") or []:
        if n and sh["n"] != n:
            continue
        if "pictures" in order:
            sh["picture"] = None
        if "motion" in order:
            sh["video"] = None
    if "finish" in order:
        p.pop("video", None)
