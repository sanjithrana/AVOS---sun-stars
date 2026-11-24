"""ASMR Cutting: an object on a board, an exact number of knife strokes, a counter, and the pieces going over at the end.

This is the Hinglish ASMR cutting workflow built as a skill. That workflow drives Blender through Codex and takes an
evening; the shot is simple enough to draw instead, so cutscene.py draws every frame with Pillow and foley.py puts one
knife stroke on each impact. No Blender, no picture model, no video model, no key: a run costs nothing and takes under a
minute, and the same object and number of cuts always give the same video.

What the workflow asks for, and what this does with it:
  Object = Papaya, Cuts = 50    the two things the person types; the count is exact, never "about fifty"
  vertical 9:16                 1080x1920, so it is a reel as drawn
  counter 0/N to N/N            steps on the frame the blade lands, not near it
  a sound on every impact       synthesised per object: a soft wet chop for papaya, a crisp snap for carrot, a dry
                                scrape for soap, so the texture follows the thing being cut
  the slices fall at the end    they go over like dominoes and the cut faces turn up
  a watermark in the margin     only if the person gives one; this never carries somebody else's handle

The AI's only job is the small spec: what the object looks like. The shot, the timing and the sound are fixed in code.
"""
from __future__ import annotations

import io
import json
import re
from collections.abc import Callable
from typing import Any

from ..series import writers
from . import base, cutscene, foley, store
from .mgfx import FPS, encode, frames_of

ID = "asmr-cutting"
SHAPES = {
    "auto": "Work it out from the object",
    "tall": "Tall - a papaya, a melon, a loaf lying down",
    "round": "Round - an apple, an orange, an onion",
    "long": "Long - a carrot, a cucumber, a candle",
    "bar": "Bar - soap, butter, cheese, clay",
}
INFO = {
    "id": ID, "name": "ASMR Cutting", "group": "Reels", "kind": "asmr",
    "made_for": "One object, an exact number of knife strokes, a counter, and the slices falling: the cutting reel, drawn in code",
    "about": "Every frame is drawn and every sound is synthesised, so a run costs nothing, needs no key and gives the same "
             "result every time. Say the object and the number of cuts; the counter steps on the frame the blade lands and "
             "the sound sits on that same frame, which is most of what makes a cutting video feel real. 1080x1920.",
    "input": "The object and how many cuts, e.g. 'papaya, 50 cuts'",
    "outputs": ["The plan", "The video"],
    "aspect": "9:16", "aspects": ["9:16"], "seconds": [18, 30, 45], "default_seconds": 30, "native_audio": True, "free": True,   # no picture or video model: a run costs nothing
    "examples": ["papaya, 50 cuts", "carrot, 30 cuts", "a bar of blue soap, 24 cuts", "watermelon, 40 cuts", "butter, 18 cuts"],
    "credit": "Follows the Hinglish ASMR cutting workflow (object, exact cut count, counter, impact sounds, slices falling).",
    "make": [["media", "Plan and video"], ["prompts", "The plan only"]],
    "cta": ["Write the plan", "Make the cutting video"],
    "note": "Nothing is generated and nothing is spent: every frame is drawn in code and every knife stroke is "
            "synthesised, so this needs no key and gives the same video twice. The cut count is exact - 50 means 50. "
            "Length sets how fast the strokes come, not how many: if the count will not fit at a watchable pace the "
            "video gets longer and the run says so.",
    "motions": [[k, v] for k, v in SHAPES.items()],
    "motions_label": "Shape",
}
INFO["lengths"] = [{"seconds": n, "scenes": 1, "each": n} for n in INFO["seconds"]]

SIZES = {"9:16": (1080, 1920), "1:1": (1080, 1080)}
DEFAULT_CUTS = 24

SPEC = """You describe one object for an ASMR cutting video. You never write prose, only the JSON below.

{"object":"<the thing being cut, one or two words, lower case>","shape":"<round|long|bar|tall>","skin":"<#rrggbb, the outside>","flesh":"<#rrggbb, the inside, seen on a cut face>","seeds":"<#rrggbb, pips or the core, or the same as flesh if there are none>","texture":"<wet|crisp|dry|soft>","title":"<4-6 words for the card, lower case>"}

shape: round for an apple or an onion; long for a carrot or a candle; bar for soap, butter or cheese; tall for a papaya,
a melon or a loaf lying on its side.
texture is what the knife sounds like going through it: wet for ripe fruit, crisp for a carrot or an apple, dry for soap
or clay, soft for butter, bread or cake.
Colours must be what the real thing looks like, not a stylised palette: an unripe papaya is green outside and orange
inside, a cucumber dark green outside and pale inside. Keep the skin and the flesh clearly different from each other, or
the cut will not read on screen.
Use the object the person named. If they named no object at all, use a papaya. Answer with the JSON and nothing else."""


def cuts_in(subject: str, fallback_n: int = DEFAULT_CUTS) -> int:
    """The number of strokes, taken from the person's own line. 'Cuts = 50' is the whole point, so it is never rounded."""
    t = (subject or "").lower()
    m = re.search(r"(\d{1,3})\s*(?:x\s*)?(?:cuts?|slices?|strokes?|pieces?|chops?)", t) or \
        re.search(r"(?:cuts?|slices?|strokes?|pieces?)\s*[:=]?\s*(\d{1,3})", t)
    if not m:
        m = re.search(r"(?<![\w.])(\d{1,3})(?![\w.])", t)
    n = int(m.group(1)) if m else fallback_n
    return max(1, min(cutscene.MAX_CUTS, n))


HANDLE = re.compile(r"@[A-Za-z0-9._][A-Za-z0-9._-]{1,30}")


def handle_in(subject: str) -> str:
    """A watermark, only if the person put one in their own line. Nobody else's handle ever ends up on their video."""
    m = HANDLE.search(subject or "")
    return m.group(0) if m else ""


def object_in(subject: str) -> str:
    """The object: the person's line with the count, the handle and the filler words taken out."""
    t = HANDLE.sub(" ", (subject or "")).lower()
    t = re.sub(r"\d{1,3}\s*(?:x\s*)?(?:cuts?|slices?|strokes?|pieces?|chops?)", " ", t)
    t = re.sub(r"(?:cuts?|slices?|strokes?|pieces?)\s*[:=]?\s*\d{1,3}", " ", t)
    t = re.sub(r"\b(?:object|cut|cutting|asmr|video|reel|a|an|the|of|into|in|with|please|make|bar|piece)\b", " ", t)
    t = re.sub(r"[^a-z\s-]", " ", t)
    words = [w for w in t.split() if len(w) > 2]
    return " ".join(words[:2]) or "papaya"


def _rgb(v: Any, fallback: tuple) -> tuple:
    if isinstance(v, (list, tuple)) and len(v) == 3:
        return tuple(max(0, min(255, int(x))) for x in v)
    s = str(v or "").strip().lstrip("#")
    if len(s) == 6:
        try:
            return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))
        except ValueError:
            pass
    return fallback


def fallback(subject: str, shape: str) -> dict:
    """No AI, or the AI could not answer: the object's own colours, from the table cutscene keeps."""
    name = object_in(subject)
    skin, flesh, pip = cutscene.colours_for(name)
    return {"object": name, "shape": shape if shape in cutscene.SHAPES else cutscene.shape_for(name),
            "skin": list(skin), "flesh": list(flesh), "seeds": list(pip),
            "texture": foley.texture_for(name), "title": f"cutting a {name}"}


def norm(d: Any, subject: str, shape: str) -> dict:
    base_spec = fallback(subject, shape)
    if not isinstance(d, dict):
        return base_spec
    name = str(d.get("object") or base_spec["object"]).strip().lower()[:28] or base_spec["object"]
    sh = str(d.get("shape") or "").strip().lower()
    if shape in cutscene.SHAPES:                              # the person's own choice wins over the AI's
        sh = shape
    elif sh not in cutscene.SHAPES:
        sh = cutscene.shape_for(name)
    tex = str(d.get("texture") or "").strip().lower()
    if tex not in foley.TEXTURES:
        tex = foley.texture_for(name)
    auto = cutscene.colours_for(name)
    return {"object": name, "shape": sh,
            "skin": list(_rgb(d.get("skin"), auto[0])), "flesh": list(_rgb(d.get("flesh"), auto[1])),
            "seeds": list(_rgb(d.get("seeds"), auto[2])), "texture": tex,
            "title": str(d.get("title") or base_spec["title"]).strip()[:70]}


def spec_for(s: dict, subject: str, shape: str, log: Callable[[dict], None] | None = None) -> dict:
    if not writers.uses_ai(s):
        return fallback(subject, shape)
    try:
        d = writers.ask(s, "story", writers.system("avos-asmr-cutting", SPEC),
                        f"The person wrote: {subject}\nWrite the JSON for the object.",
                        log, max_tokens=400, temperature=0.2)
        return norm(d, subject, shape)
    except Exception as e:  # noqa: BLE001 - the colours are in the table, so a failed writer is not a failed run
        if log:
            log({"text": f"The AI writer could not describe the object ({str(e)[:120]}); used its usual colours instead.", "kind": "warn"})
        return fallback(subject, shape)


def beat_for(seconds: float, cuts: int) -> float:
    """How long between strokes, so the video lands near the length the person picked.

    Clamped: below about an eighth of a second the strokes stop reading as separate, and above six tenths the shot
    drags. When the clamp bites the video is longer or shorter than asked, and the run says so rather than quietly
    dropping cuts -- the count is the one thing the person actually specified.
    """
    spare = float(seconds) - (cutscene.INTRO + cutscene.AFTER + cutscene.FALL + cutscene.OUTRO)
    return max(0.12, min(0.60, spare / max(1, cuts)))


def outputs_of(p: dict) -> list[dict]:
    """One card: this skill makes one video and nothing else."""
    return [{"key": "final", "step": "render", "title": "The cutting video", "kind": "video",
             "file": p.get("video"), "prompt": "plan"}]


# ---------- stages ----------
STAGES = ("plan", "render")
LABELS = {"plan": "The plan", "render": "The video"}


def _w_h(p: dict) -> tuple[int, int]:
    return SIZES.get(p.get("aspect") or "9:16", SIZES["9:16"])


def last_stage(p: dict) -> str:
    return "plan" if p.get("media") == "prompts" else "render"


def reset(p: dict, step: str, n: int | None = None) -> None:
    for st in STAGES[STAGES.index(step):]:
        p.setdefault("steps", {}).pop(st, None)
    if step == "plan":
        p.pop("spec", None)
        p.pop("prompts", None)
    p.pop("video", None)


def do_plan(pid: str) -> None:
    p = store.load(pid)
    base.step(pid, "plan", status="working")
    subject = p["subject"]
    cuts = cuts_in(subject)
    spec = spec_for(base.sdict(p), subject, p.get("motion") or "", base.logger(pid))
    spec["cuts"] = cuts
    spec["watermark"] = (str(p.get("watermark") or "").strip() or handle_in(subject))[:40]
    gap = beat_for(float(p.get("seconds") or INFO["default_seconds"]), cuts)
    spec["gap"] = round(gap, 3)
    total = cutscene.INTRO + gap * cuts + cutscene.AFTER + cutscene.FALL + cutscene.OUTRO
    base.put(pid, spec=spec, title=spec["title"],
             prompts={"plan": json.dumps({k: v for k, v in spec.items() if k != "watermark"}, indent=1)})
    note = (f"{cuts} cuts on a {spec['object']}, one every {gap:.2f}s, {spec['texture']} sound, "
            f"{total:.1f} seconds in all")
    if abs(total - float(p.get("seconds") or INFO["default_seconds"])) > 1.5:
        note += f" - {cuts} cuts will not fit {p.get('seconds')}s at a watchable pace, so the video is {total:.1f}s"
    base.step(pid, "plan", status="done", note=note)


def do_render(pid: str) -> None:
    from .. import config                      # studio/config.py, imported here like every other skill does it
    p = store.load(pid)
    base.check(pid)
    w, h = _w_h(p)
    spec = dict(p.get("spec") or fallback(p["subject"], p.get("motion") or ""))
    spec.setdefault("cuts", cuts_in(p["subject"]))
    spec.setdefault("gap", round(beat_for(float(p.get("seconds") or INFO["default_seconds"]), spec["cuts"]), 3))
    base.step(pid, "render", status="working")
    seconds, draw, (bg, _), impacts = cutscene.scene(spec, w, h)
    wav = foley.cuts_wav(impacts, seconds, spec.get("texture") or "wet", len(str(spec.get("object"))),
                         tumble=impacts[-1] + cutscene.AFTER)
    track = store.pdir(pid) / "cuts.wav"
    track.write_bytes(wav)
    thumb = None

    def frames():
        nonlocal thumb
        for im in frames_of(seconds, draw, w, h, bg):
            thumb = im
            yield im

    out = encode(frames(), store.pdir(pid) / "final.mp4", w, h, config.ffmpeg(), track)
    if thumb is not None:
        b = io.BytesIO()
        thumb.save(b, "PNG")
        base.put(pid, thumb=base.write(pid, "thumb.png", b.getvalue()))
    base.put(pid, video=out.name, finalSeconds=round(seconds, 1))
    base.step(pid, "render", status="done", model="drawn in code",
              note=f"{round(seconds, 1)} seconds at {w}x{h}, {spec['cuts']} strokes with a sound on every one: "
                   f"no picture or video model was used")


RUN = {"plan": do_plan, "render": do_render}
