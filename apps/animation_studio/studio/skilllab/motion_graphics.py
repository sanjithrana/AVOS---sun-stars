"""Motion Graphics: four code-drawn animations - a line graph, minimal line art, a map route and an exploded breakdown.

Ported from the animation skills at github.com/artemnovitckii/claude-animation-skills (MIT, Artem Novitckii), which render
with three.js, GSAP and a headless browser. Here they are drawn with Pillow and written out with ffmpeg, so they need
nothing the studio container does not already have - no Node, no npx, no Chromium - and they use no picture or video
model at all. A run costs nothing and takes about ten seconds.

The AI's only job is to turn what the person typed into a small spec: the numbers for a graph, the two ends of a route,
the parts of a device. The look and the timing are fixed in code, so two runs of the same spec give the same video.
"""
from __future__ import annotations

import json
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

from ..series import writers
from . import base, store
from .mgfx import FPS, encode, frames_of
from .mgscenes import SCENES

ID = "motion-graphics"
KINDS = {
    "graph": "Line graph - a line draws itself while one big number counts up",
    "lineart": "Line art - black and white, a dot hops up rising steps",
    "route": "Map route - a white 3D city, a route that draws itself, a pin drop",
    "breakdown": "Breakdown - a device comes apart layer by layer, every part labelled",
}
INFO = {
    "id": ID, "name": "Motion Graphics", "group": "Reels", "kind": "graphics",
    "made_for": "A stat, a thought, a journey or a device: four clean animations drawn in code, free and in about ten seconds",
    "about": "No picture model and no video model: every frame is drawn in code, so a run costs nothing, needs no key and gives the "
             "same result every time. The AI only writes the small spec - the numbers, the two ends of the route, the list of parts - "
             "and the look and the timing are fixed. 1080x1920 for reels, or 16:9.",
    "input": "What to show, e.g. '0 to 100K followers in 9 months: 1.2K, 2.1K, 5K, 24K, 100K'",
    "outputs": ["The spec", "The animation"],
    "aspect": "9:16", "aspects": ["9:16", "16:9"], "seconds": [5, 8, 12], "default_seconds": 5, "native_audio": False, "free": True,
    "examples": ["0 to 100K followers in 9 months: 1.2K, 2.1K, 3.4K, 9K, 24K, 51K, 100K",
                 "every step feels small until you look back",
                 "home to the gym, 2.8 km, 9 minutes",
                 "my phone, every part labelled"],
    "credit": "The four animations are ports of the MIT-licensed animation skills by Artem Novitckii.",
    "make": [["media", "Spec and animation"], ["prompts", "The spec only"]],
    "cta": ["Write the spec", "Make the animation"],
    "note": "No picture model and no video model: every frame is drawn in code, so a run costs nothing, needs no key "
            "and gives the same result every time. The AI writes only the small spec - your numbers, the two ends of "
            "the route, the list of parts - and never invents a number you did not write. These four animations are "
            "built to land in five to twelve seconds; there is no thirty-second version that would not just be slower.",
    "motions": [[k, v] for k, v in KINDS.items()],
    "motions_label": "What to draw",
}
INFO["lengths"] = [{"seconds": n, "scenes": 1, "each": n} for n in INFO["seconds"]]

SPEC = """You turn one line from a person into a small JSON spec for a code-drawn animation. You never write prose, only the JSON.
You are told which of four animations it is. Use ONLY the facts the person gave; never invent a number they did not state.

graph - a line that draws itself while a number counts up:
{"kind":"graph","label":"<4-6 words, lower case, what the line is>","values":[<6 to 10 numbers, plain integers, rising or falling as the person said>],"labels":["<short tick, e.g. Jan>", ...],"prefix":"<$ or empty>","suffix":"<% or empty>","decimals":0,"dark":false}
- If the person gave numbers, use them in the order given. If they gave only a start and an end ("0 to 100K in 9 months"), write a believable curve between them with the right number of points, and keep the first and last exactly as they said.
- "labels" has one entry per value; use "" for the ones that should stay blank. Leave it [] if there is nothing sensible.

lineart - black and white, a dot hops up rising steps:
{"kind":"lineart","line":"<the person's line, lower case, under 60 characters>","second":"<an optional shorter payoff line, or empty>","steps":<3 to 7>}

route - a white city with a route drawing itself:
{"kind":"route","from":"<start, 1-3 words>","to":"<destination, 1-3 words>","km":<number or 0>,"minutes":<whole minutes or 0>}

breakdown - a device comes apart layer by layer:
{"kind":"breakdown","title":"<4-6 words, what is being taken apart>","parts":[{"name":"<1-2 words per layer>"}, ...]}
- Between 3 and 6 parts, in the order they would come off, outside first.

Answer with ONE JSON object and nothing else."""

# A K or an M only multiplies when no letter follows it, so "2.8 km" stays 2.8 and "9 minutes" stays 9, while "100K" is 100000.
_NUM = re.compile(r"(\d[\d,]*(?:\.\d+)?)(?:\s*([kKmM]))?(?![\w])")


def numbers_in(s: str) -> list[float]:
    """The numbers a person typed, with 1.2K and 3M read properly - and km, min and months left alone."""
    after = (s or "").rsplit(":", 1)
    s = after[1] if len(after) > 1 and len(_NUM.findall(after[1])) >= 3 else (s or "")   # "0 to 100K: 1.2K, 2.1K, ..." -> the list
    out = []
    for raw, unit in _NUM.findall(s):
        try:
            v = float(raw.replace(",", ""))
        except ValueError:
            continue
        out.append(v * {"k": 1e3, "m": 1e6}.get(unit.lower(), 1))
    return out


def guess_kind(subject: str) -> str:
    """Which of the four a line is asking for, when the person has not picked."""
    t = (subject or "").lower()
    if re.search(r"\bto\b.*\b(km|miles?|min|minutes?)\b|route|commute|journey|drive|walk from", t):
        return "route"
    if re.search(r"part|teardown|exploded|inside|components?|labelled|labeled|breakdown", t):
        return "breakdown"
    if len(numbers_in(t)) >= 3 or re.search(r"\bgrowth|followers|revenue|subscribers|\bchart\b|\bgraph\b|0 to ", t):
        return "graph"
    return "lineart"


def fallback(kind: str, subject: str) -> dict:
    """A spec without an AI writer. A graph can be read straight out of what the person typed; the rest get honest defaults."""
    nums = numbers_in(subject)
    head = " ".join(subject.split())[:60]
    if kind == "graph":
        vals = [n for n in nums if n >= 0][:10]
        if len(vals) < 4:                                   # "0 to 100K": only the two ends, so draw a believable climb between them
            start, end = (vals + [0.0, 100.0])[:2] if len(vals) >= 2 else (0.0, (vals or [100.0])[0])
            vals = [start + (end - start) * (i / 7) ** 2.2 for i in range(8)]
        return {"kind": "graph", "label": re.sub(r"[\d,.]+[kKmM]?", "", head).strip(" :,-").lower()[:40] or "the numbers",
                "values": [round(v, 2) for v in vals], "labels": [], "prefix": "", "suffix": "", "decimals": 0, "dark": False}
    if kind == "route":
        parts = re.split(r"\s+to\s+", head, maxsplit=1)
        km = re.search(r"([\d.]+)\s*(?:km|kms|mi|miles?)\b", subject, re.I)          # read the units the person wrote
        mins = re.search(r"([\d.]+)\s*(?:min|mins|minutes?)\b", subject, re.I)
        rest = [n for n in nums if not km or abs(n - float(km.group(1))) > 1e-9]
        return {"kind": "route", "from": (parts[0] or "Start").strip(" ,")[:24].title(),
                "to": (re.sub(r"[\d.]+\s*(?:km|kms|mi|miles?|min|mins|minutes?)\b.*$", "", re.split(r"[,(]", parts[1])[0], flags=re.I).strip()[:24].title()
                       or "Destination") if len(parts) > 1 else "Destination",
                "km": float(km.group(1)) if km else next((n for n in nums if 0 < n < 500), 0),
                "minutes": int(float(mins.group(1))) if mins else int(next((n for n in rest if 0 < n <= 240), 0))}
    if kind == "breakdown":
        return {"kind": "breakdown", "title": head[:40], "parts": [{"name": n} for n in ("Glass", "Screen", "Frame", "Board", "Back")]}
    return {"kind": "lineart", "line": head.lower(), "second": "", "steps": 5}


def norm(d: Any, kind: str, subject: str) -> dict:
    """Whatever the writer returned, made safe to draw."""
    if not isinstance(d, dict):
        return fallback(kind, subject)
    out = fallback(kind, subject)
    if kind == "graph":
        vals = [float(v) for v in (d.get("values") or []) if isinstance(v, (int, float)) and float(v) >= 0][:10]
        if len(vals) >= 2 and max(vals) > 0:
            out["values"] = vals
            labels = [str(x)[:8] for x in (d.get("labels") or [])][: len(vals)]
            out["labels"] = labels + [""] * (len(vals) - len(labels)) if labels else []
        for k, cast in (("label", str), ("prefix", str), ("suffix", str)):
            if d.get(k):
                out[k] = cast(d[k])[:48]
        out["decimals"] = max(0, min(2, int(d.get("decimals") or 0)))
        out["dark"] = bool(d.get("dark"))
    elif kind == "lineart":
        out["line"] = (str(d.get("line") or out["line"]).strip() or out["line"])[:70].lower()
        out["second"] = str(d.get("second") or "").strip()[:48].lower()
        out["steps"] = max(3, min(7, int(d.get("steps") or 5)))
    elif kind == "route":
        out["from"] = str(d.get("from") or out["from"]).strip()[:24] or "Start"
        out["to"] = str(d.get("to") or out["to"]).strip()[:24] or "Destination"
        try:
            out["km"] = max(0.0, min(9999.0, float(d.get("km") or 0)))
            out["minutes"] = max(0, min(600, int(float(d.get("minutes") or 0))))
        except (TypeError, ValueError):
            pass
    else:
        parts = [{"name": str(p.get("name") if isinstance(p, dict) else p)[:18].strip()} for p in (d.get("parts") or [])]
        parts = [p for p in parts if p["name"]][:6]
        if len(parts) >= 2:
            out["parts"] = parts
        out["title"] = str(d.get("title") or out["title"])[:46]
    out["kind"] = kind
    return out


def spec_for(s: dict, kind: str, subject: str, log: Callable[[dict], None] | None = None) -> dict:
    """The spec: written by the AI crew when there is one, read out of the person's own words when there is not."""
    if not writers.uses_ai(s):
        return fallback(kind, subject)
    try:
        d = writers.ask(s, "story", writers.system("avos-motion-graphics", SPEC),
                        f"Animation: {kind} - {KINDS[kind]}\nThe person wrote: {subject}\nWrite the JSON spec.",
                        log, max_tokens=900, temperature=0.3)
        return norm(d, kind, subject)
    except Exception as e:  # noqa: BLE001 - the spec is small enough to read out of the subject instead
        if log:
            log({"text": f"The AI writer could not write the spec ({str(e)[:120]}); read it from your words instead.", "kind": "warn"})
        return fallback(kind, subject)


def outputs_of(p: dict) -> list[dict]:
    """One card: this skill makes one video and nothing else."""
    return [{"key": "final", "step": "render", "title": "The animation", "kind": "video",
             "file": p.get("video"), "prompt": "spec"}]


# ---------- stages ----------
STAGES = ("spec", "render")
LABELS = {"spec": "The spec", "render": "The animation"}


# Full reel resolution: nothing here is limited by a model's output size, so there is no reason to draw it small.
SIZES = {"9:16": (1080, 1920), "16:9": (1920, 1080), "1:1": (1080, 1080)}


def _w_h(p: dict) -> tuple[int, int]:
    return SIZES.get(p.get("aspect") or "9:16", SIZES["9:16"])


def _kind(p: dict) -> str:
    k = p.get("motion") or ""
    return k if k in SCENES else guess_kind(p.get("subject") or "")


def do_spec(pid: str) -> None:
    p = store.load(pid)
    base.step(pid, "spec", status="working")
    kind = _kind(p)
    spec = spec_for(base.sdict(p), kind, p["subject"], base.logger(pid))
    base.put(pid, spec=spec, motion=kind, title=str(spec.get("label") or spec.get("title") or spec.get("line") or p["subject"])[:70],
             prompts={"spec": json.dumps(spec, indent=1)})
    base.step(pid, "spec", status="done", note=f"{KINDS[kind].split(' - ')[0]}: {len(json.dumps(spec))} characters of spec")


def do_render(pid: str) -> None:
    from .. import config
    p = store.load(pid)
    base.check(pid)
    w, h = _w_h(p)
    kind = _kind(p)
    spec = p.get("spec") or fallback(kind, p["subject"])
    base.step(pid, "render", status="working")
    seconds, draw, (bg, _) = SCENES[kind](spec, w, h)
    hold = max(0.0, float(p.get("seconds") or 5) - seconds)          # the extra time is a hold on the last frame

    def frames():
        last = None
        for im in frames_of(seconds, draw, w, h, bg):
            last = im
            yield im
        for _ in range(round(hold * FPS)):
            if last is not None:
                yield last

    out = encode(frames(), store.pdir(pid) / "final.mp4", w, h, config.ffmpeg())
    thumb = None
    for im in frames_of(seconds, draw, w, h, bg):                     # one frame near the end, for the card
        thumb = im
    if thumb is not None:
        import io
        b = io.BytesIO()
        thumb.save(b, "PNG")
        base.put(pid, thumb=base.write(pid, "thumb.png", b.getvalue()))
    base.put(pid, video=out.name, finalSeconds=round(seconds + hold, 1))
    base.step(pid, "render", status="done", model="drawn in code",
              note=f"{round(seconds + hold, 1)} seconds at {w}x{h}, drawn in code: no picture or video model was used")


RUN = {"spec": do_spec, "render": do_render}


def last_stage(p: dict) -> str:
    return "spec" if p.get("media") == "prompts" else "render"


def reset(p: dict, step: str, n: int | None = None) -> None:
    for st in STAGES[STAGES.index(step):]:
        p.setdefault("steps", {}).pop(st, None)
    if step == "spec":
        p.pop("spec", None)
        p.pop("prompts", None)
    p.pop("video", None)
