"""Film Style: one subject, one of 66 looks, a short film.

The 66 looks come from the Lemo-Opuscar style library (MIT), compressed into `filmstyles.py`. Upstream renders each
style in code with Node and headless Chrome; the container has neither, so AVOS does the other half of the job -- it
uses each style as a *lock* on the prompts it sends to the picture and video models it already has. The look survives
because every shot in a run carries the same look sentence, the same colour rule and the same list of what the style
is not.

Every style is its own entry in the Skills tab (`film-art-deco`, `film-risograph`, ...), built by `skills()` at import
time from one shared implementation. Adding a style is a line in `filmstyles.py`, not a new module.

Structure mirrors ASMR Cooking deliberately -- plan, pictures, motion, finish, with the chain cap, the sameness gate,
the band cutter and takes -- because that path is the one that has actually run end to end.
"""
from __future__ import annotations

import json
import re
from collections.abc import Callable
from typing import Any

from .. import house
from ..series import media, writers
from . import base, compose, store, takes
from .filmstyles import STYLES

KIND = "film"
PREFIX = "film-"
SHOT_SECONDS = (4.0, 6.0)
MAX_CHAIN = 2                      # see asmr_cooking.balance: a long chain of edits drifts back to its own input
SIZES = {"16:9": (1280, 720), "9:16": (720, 1280), "1:1": (960, 960)}
LENGTHS = [15, 30, 45, 60]
DEFAULT_SECONDS = 30
STAGES = ("plan", "pictures", "motion", "finish")
LABELS = {"plan": "The shot plan", "pictures": "Shot pictures", "motion": "Motion and sound", "finish": "The film"}

# Short on purpose. The long list of things to avoid goes to the model as `negative=NEGATIVE`, where it costs nothing;
# anything repeated here is spending the 900-character prompt budget twice.
NEVER = "No text, no watermark, no real person or brand."
NEGATIVE = ("text, caption, subtitle, watermark, signature, logo, brand, ui, hud, border, frame, letterbox, black bars, "
            "blurry, low detail, extra limbs, deformed hands, duplicate subject, split screen, photo of a screen")


def negative_for(st: dict) -> str:
    """The negative list, plus the photo words when the style is not a photographic one. Free: it is its own field."""
    _m, photoreal = medium_of(st)
    return NEGATIVE if photoreal else f"{NEGATIVE}, {NOT_PHOTO}"

PLAN = """You are the director of a very short film. You answer with JSON and nothing else.

THE LOOK YOU ARE SHOOTING IN
{look}

WHAT THIS LOOK IS NOT
{nots}

HOW IT MOVES
{motion}

THE RULES
- The film is {seconds} seconds long in {shots} shots, so each shot is one single action, about {each:.0f} seconds.
- Every shot must look DIFFERENT from the one before it: different thing in frame, different camera, different distance. If two shots would photograph the same, merge them and spend the spare shot elsewhere.
- Shot 1 establishes the place with something already happening in it. The last shot lands the idea. The middle shots are the turn.
- Write what is IN THE FRAME, not what it means. "A hand closes the brass dial to zero" is a shot. "She feels time running out" is not.
- "camera" is one of: wide, medium, close, extreme-close, overhead, low-angle, over-shoulder. Never the same twice in a row.
- Do not name any real person, company, film or artist anywhere in your answer.

ANSWER WITH THIS JSON
{{"title":"<4-7 words, lower case>","logline":"<one sentence, what happens>","shots":[{{"n":1,"title":"<3-5 words>","subject":"<what is in frame, concrete nouns>","action":"<the single movement, caught at its peak>","camera":"<from the list>","light":"<where the light comes from and what it does>","beat":"<establish|turn|land>"}}]}}

Write exactly {shots} shots, numbered from 1. Answer with the JSON and nothing else."""


# A style's medium has to be stated as a flat fact at the very front of a picture prompt. Said only in prose, it loses
# to the subject: asking Blueprint -- white linework on cyanotype paper -- for "engineering" returned six stock
# photographs of men in hard hats, because "engineering" is a stronger signal to a picture model than a paragraph of
# art direction. Measured on a real run.
MEDIA = (
    ("photo", r"photoreal|live.action|real footage|camcorder|archive film|documentary footage|photographed|vhs|super ?8",
     "Photoreal live-action"),
    ("line", r"linework|line art|technical draw|blueprint|cyanotype|engrav|etch|pencil|ink wash|pen and ink|chalk|crayon|sketch",
     "A DRAWING, not a photograph: drawn line on a surface"),
    ("print", r"risograph|screen ?print|silkscreen|halftone|woodcut|letterpress|stencil|lithograph|printed on",
     "A PRINT, not a photograph: ink pressed onto paper"),
    ("paper", r"paper|cut.?out|collage|pop.?up|lantern|origami|cardstock",
     "A PAPER CONSTRUCTION, not a photograph: cut and layered paper"),
    ("cel", r"\bcel\b|anime|cartoon|rubber hose|hand.painted|hand.inked|toon|animated",
     "HAND-DRAWN ANIMATION, not a photograph: painted cels"),
    ("3d", r"low.?poly|voxel|stop.?motion|claymation|plasticine|brick|3d render|cgi|isometric|white model",
     "A 3D RENDER, not a photograph"),
    ("pixel", r"pixel|indexed palette|sprite|8.?bit|16.?bit", "PIXEL ART, not a photograph"),
    ("screen", r"terminal|crt|phosphor|hud|screencast|interface", "A SCREEN IMAGE, not a photograph"),
)
NOT_PHOTO = ("photograph, photo, photorealistic, stock photo, real person, human face, portrait photography, "
             "dslr, bokeh, film still of a live actor")


def medium_of(st: dict) -> tuple[str, bool]:
    """(the sentence that opens the prompt, is this style photoreal?).

    Photoreal styles get no medium sentence: for those the photograph IS the medium and saying so wastes budget.
    """
    hay = " ".join([st.get("quote") or "", st.get("essence") or "", " ".join(st.get("material") or [])]).lower()
    for key, rx, phrase in MEDIA:
        if re.search(rx, hay):
            return ("" if key == "photo" else phrase + "."), key == "photo"
    return "", False


# ---------- the style ----------
def slug_of(p: dict) -> str:
    sid = str(p.get("skill") or "")
    return sid[len(PREFIX):] if sid.startswith(PREFIX) else ""


def style_of(p: dict) -> dict:
    return STYLES.get(slug_of(p)) or next(iter(STYLES.values()))


def _join(items, sep: str = " ") -> str:
    return sep.join(x for x in items if x)


def look_of(st: dict, long: bool = False) -> str:
    """The look in one block. Short for a picture prompt, long for the writer."""
    bits = [st.get("quote") or "", st.get("essence") or ""]
    if long:
        bits += ["MATERIALS: " + _join(st.get("material") or [], "; "),
                 "COLOUR: " + _join(st.get("colour") or [], "; "),
                 "CAMERA: " + _join(st.get("camera") or [], "; ")]
    else:
        bits += [_join((st.get("material") or [])[:2], "; "), _join((st.get("colour") or [])[:1], "; ")]
    return _join(bits, " ")


_trim = house.trim                     # shared with every director now (studio/house.py)


def _cap(text: str, tail: str, limit: int = 900) -> str:
    out = _trim(text, limit - len(tail) - 2)
    return f"{out} {tail}" if out else tail


_fit = house.fit                       # lead with the look, never lose the shot: see house.fit


def shots_for(seconds: float) -> int:
    lo, hi = SHOT_SECONDS
    return max(3, min(14, round(float(seconds) / ((lo + hi) / 2))))


def seconds_each(seconds: float, shots: int) -> float:
    lo, hi = SHOT_SECONDS
    return max(lo, min(hi, float(seconds) / max(1, shots)))


# ---------- the plan ----------
# What each beat actually shows, when there is no writer to invent it. "The subject is seen plainly, held still" --
# which is what this used to say -- is not a shot, and six of them chained together is how a run comes back as six
# near-identical stock photographs.
BEATS = (
    ("establish", "the place, empty and wide, before anything happens", "wide"),
    ("detail", "one small part of it, close enough to see the surface", "extreme-close"),
    ("turn", "the thing itself, head on, the moment it matters", "medium"),
    ("scale", "the whole of it from above, laid out", "overhead"),
    ("press", "the same thing from low down, bigger than it was", "low-angle"),
    ("land", "the last look, pulled back, nothing moving", "wide"),
)


def fallback_plan(subject: str, st: dict, shots: int) -> dict:
    """No writer, or it failed: a plain film still beats a stopped run, but it has to be six different shots."""
    s = (subject or "a short film").strip()
    out = []
    for i in range(shots):
        beat, what, cam = BEATS[i % len(BEATS)]
        out.append({"n": i + 1, "title": what[:40], "subject": f"{s} - {what}",
                    "action": "held still, nothing moving",
                    "camera": cam, "light": "the look's own key light",
                    "beat": "establish" if i == 0 else "land" if i == shots - 1 else beat,
                    # Without this every shot after the first was drawn FROM the one before, so one bad opening
                    # shot became the whole film. norm_plan set it; this did not.
                    "fresh": i == 0 or i % (MAX_CHAIN + 1) == 0})
    out[-1]["beat"] = "land"
    return {"title": s.lower()[:60], "logline": s, "shots": out, "by_ai": False}


def norm_plan(d: Any, subject: str, st: dict, shots: int) -> dict:
    if not isinstance(d, dict) or not isinstance(d.get("shots"), list) or not d["shots"]:
        return fallback_plan(subject, st, shots)
    cams = ["wide", "medium", "close", "overhead", "low-angle", "extreme-close", "over-shoulder"]
    out, last = [], ""
    for i, raw in enumerate(d["shots"][:shots]):
        sh = raw if isinstance(raw, dict) else {}
        cam = str(sh.get("camera") or "").strip().lower()
        if cam not in cams or cam == last:                 # never the same camera twice running
            cam = next(c for c in cams if c != last and c != cam) if cam == last else cams[i % len(cams)]
        last = cam
        out.append({"n": i + 1, "title": str(sh.get("title") or f"Shot {i + 1}")[:60],
                    "subject": str(sh.get("subject") or subject)[:220],
                    "action": str(sh.get("action") or "held still")[:220],
                    "camera": cam, "light": str(sh.get("light") or "")[:160],
                    "beat": str(sh.get("beat") or ("establish" if not i else "turn"))[:20]})
    while len(out) < shots:                                 # the writer was short: pad rather than fail
        out.append(fallback_plan(subject, st, shots)["shots"][len(out)])
    out[-1]["beat"] = "land"
    for i, sh in enumerate(out):
        sh["fresh"] = i == 0 or (i % (MAX_CHAIN + 1) == 0)
    out[0]["fresh"] = True
    return {"title": str(d.get("title") or subject)[:70], "logline": str(d.get("logline") or "")[:200], "shots": out, "by_ai": True}


def plan_for(s: dict, subject: str, st: dict, seconds: float, log: Callable[[dict], None] | None = None) -> dict:
    shots = shots_for(seconds)
    if not writers.uses_ai(s):
        return fallback_plan(subject, st, shots)
    ask = PLAN.format(look=look_of(st, long=True), nots=st.get("nots") or "-",
                      motion=_join(st.get("motion") or [], "; ") or "-",
                      seconds=int(seconds), shots=shots, each=seconds_each(seconds, shots))
    try:
        d = writers.ask(s, "story", writers.directed("avos-film-style", ask),
                        f"The film is about: {subject}", log, max_tokens=1600, temperature=0.6)
        return norm_plan(d, subject, st, shots)
    except Exception as e:  # noqa: BLE001 - the fallback keeps the run going
        if log:
            log({"text": f"The writer could not plan the film ({str(e)[:120]}); used a plain three-beat plan.", "kind": "warn"})
        return fallback_plan(subject, st, shots)


# ---------- the prompts ----------
def image_prompt(st: dict, sh: dict, aspect: str) -> str:
    shape = {"16:9": "horizontal 16:9", "9:16": "vertical 9:16", "1:1": "square"}.get(aspect, "horizontal 16:9")
    light = f" {_trim(sh['light'], 110).rstrip('.')}." if sh.get("light") else ""
    shot = (f"{sh['camera'].replace('-', ' ')} shot, {shape}, the frame filled edge to edge. "
            f"In frame: {_trim(sh['subject'], 170).rstrip('.')}. {_trim(sh['action'], 170).rstrip('.')}.{light}")
    extra = _join([st.get("essence") or "", _join((st.get("material") or [])[:2], "; "),
                   _join((st.get("colour") or [])[:1], "; "),
                   f"NOT: {st['nots']}" if st.get("nots") else ""])
    medium, photoreal = medium_of(st)
    lead = _join([medium, _trim(st.get("quote") or st.get("essence") or "", 230 if medium else 260)])
    tail = NEVER if photoreal else NEVER + " Not a photograph."
    return _fit(lead, shot, extra, tail)


def edit_prompt(st: dict, sh: dict) -> str:
    return _cap(
        f"Keep the look, the materials, the colour and the light of the reference exactly. Change the shot to this: "
        f"{sh['camera'].replace('-', ' ')} shot. In frame: {sh['subject'].rstrip('.')}. {sh['action'].rstrip('.')}. "
        f"It is a different moment in the same film, so the framing and what is in it must visibly change.",
        NEVER)


# A video prompt is a labelled block, not a sentence. Two things that look like instructions are not: the aspect
# ratio and the duration are job parameters, passed to the model alongside the prompt, so writing "16:9" or
# "5 seconds" in the text sets nothing and spends budget that the craft lines need. (Confirmed independently by the
# Higgsfield prompt library, MIT, which calls format and resolution "job settings, never prefix text".)
VIDEO_LIMIT = 1200


def motion_prompt(st: dict, sh: dict, seconds: float) -> str:
    """The image-to-video prompt: the picture is the first frame, and exactly one thing happens in it."""
    move = _join((st.get("motion") or [])[:2], "; ") or "steady, deliberate movement, nothing floats"
    lines = [
        f"Animate this exact picture as the next moment of the same film. Style: {_trim(st.get('quote') or '', 190)}",
        f"Action: one thing happens - {sh['action'].rstrip('.')}. Nothing else moves on its own.",
        f"Camera: {sh['camera'].replace('-', ' ')}, locked off or an extremely slow push. "
        "No handheld, no shake, no whip pan, no orbit, no dolly zoom, no speed ramp.",
        f"Motion: {_trim(move, 180)}",
        "Physics: gravity and inertia respected, mass has real weight, contact shadows stay put, nothing floats.",
        "Continuity: the look, the palette, the light and everything already in frame stay exactly as they are. "
        "No new objects, no new characters, no identity drift, no cuts.",
        # Not a blanket "no music": for several of these styles the score IS the sound palette, and an earlier
        # version told the model "diegetic only - symphonic jazz ... No music" in the same line.
        f"Audio: {_trim(ambience(st, sh), 130)}. No voice-over, no narration, no subtitles.",
        NEVER,
    ]
    out = " ".join(x for x in lines if x)
    return out[:VIDEO_LIMIT].rsplit(" ", 1)[0] if len(out) > VIDEO_LIMIT else out


MUSICAL = re.compile(r"\b(music|score|orchestr|harpsichord|bassoon|strings|harp|celesta|piano|clarinet|jazz|band|"
                     r"synth|theme|melody|song|choir|drum|beat|bass|guitar|violin|cello|organ)\b", re.I)


def ambience(st: dict, sh: dict) -> str:
    """What the clip should sound like, in words, for the video model's own audio."""
    return _join((st.get("sound") or [])[:1], " ") or sh.get("action") or ""


def sound_plan(st: dict, sh: dict) -> tuple[str, str]:
    """(how to make the sound, the cue). One of 'foley', 'music' or 'quiet'.

    foley.py is a kitchen synthesiser: sizzle, chop, pour, boil, stir, knock. Most of these 66 styles ask for a score
    instead -- Blueprint wants "contrapuntal mechanical music: harpsichord, bassoon, strings spiccato" -- and an
    earlier version fed that sentence straight to foley, matched none of its cue words, fell through to its default
    'stir', and laid thirty seconds of flat stirring noise under the film. A drone pretending to be sound design is
    worse than silence, and AVOS has no music model, so now it says so instead of faking it.
    """
    from . import foley
    text = _join([st.get("sound") and st["sound"][0] or "", sh.get("action") or ""])
    if MUSICAL.search(text):
        return "music", ""
    for name, rx in foley.WORDS:
        if re.search(rx, text, re.I):
            return "foley", text
    return "quiet", ""


def _meter(kind: str, model: str, units: float, pid: str = "", skill: str = "", ok: bool = True) -> None:
    """One line in the usage ledger. Wrapped because a run must never fail over its own bookkeeping."""
    try:
        from ..usage import record
        record(kind, model, units, run=pid, skill=skill, ok=ok)
    except Exception:  # noqa: BLE001
        pass


def outputs_of(p: dict) -> list[dict]:
    """One card per shot -- the clip once it exists, the still until then -- and the finished film at the end.

    Each entry carries its own file, so the run page never has to guess which field holds what.
    """
    shots = (p.get("plan") or {}).get("shots") or []
    out = [{"key": f"shot{sh['n']}", "step": "motion" if sh.get("video") else "pictures",
            "title": f"{sh['n']}. {(sh.get('title') or 'Shot').strip()[:40]}",
            "kind": "video" if sh.get("video") else "image",
            "file": sh.get("video") or sh.get("picture"),
            "prompt": f"shot{sh['n']}"} for sh in shots]
    out.append({"key": "final", "step": "finish", "title": "The film", "kind": "video",
                "file": p.get("video"), "prompt": None})
    return out


# ---------- stages ----------
def _w_h(p: dict) -> tuple[int, int]:
    return SIZES.get(p.get("aspect") or "16:9", SIZES["16:9"])


def _each(p: dict) -> float:
    plan = p.get("plan") or {}
    return seconds_each(float(p.get("seconds") or DEFAULT_SECONDS), len(plan.get("shots") or []) or 1)


def last_stage(p: dict) -> str:
    return "plan" if p.get("media") == "prompts" else "finish"


def reset(p: dict, step: str, n: int | None = None) -> None:
    order = STAGES[STAGES.index(step):]
    for st in order:
        p.setdefault("steps", {}).pop(st, None)
    if "plan" in order:
        p.pop("plan", None)
        p.pop("prompts", None)
        p.pop("video", None)
        return
    for sh in (p.get("plan") or {}).get("shots") or []:
        if n and sh["n"] != n:
            continue
        if "pictures" in order:
            takes.clear_pointer(sh, "picture")
        if "motion" in order:
            takes.clear_pointer(sh, "video")
    if "finish" in order:
        p.pop("video", None)


def do_plan(pid: str) -> None:
    p = store.load(pid)
    st = style_of(p)
    base.step(pid, "plan", status="working")
    seconds = float(p.get("seconds") or DEFAULT_SECONDS)
    plan = plan_for(base.sdict(p), p["subject"], st, seconds, base.logger(pid))
    aspect = p.get("aspect") or "16:9"
    prompts = {f"shot{sh['n']}": image_prompt(st, sh, aspect) for sh in plan["shots"]}
    prompts["plan"] = json.dumps(plan, indent=1)
    base.put(pid, plan=plan, prompts=prompts, title=plan["title"])
    note = (f"{len(plan['shots'])} shots, about {seconds_each(seconds, len(plan['shots'])):.0f}s each, "
            f"all locked to the {st['name']} look")
    found = house.review([house.card(sh["n"], sh["subject"], sh["action"], sh["camera"]) for sh in plan["shots"]])
    if plan.get("by_ai"):                  # the fallback is plain on purpose; its notes would only repeat the line below
        plan["house"] = {"found": [list(f) for f in found], "note": house.note_of(found)}
        base.put(pid, plan=plan)
        if found:
            note += ". " + plan["house"]["note"]
    if not plan.get("by_ai"):
        # Silence here is how a run of six near-identical stock photographs looks like it went fine.
        note += (". No AI writer answered, so this is the plain six-beat fallback plan built from your subject, not a "
                 "written film - add a writer in Models and run the plan again for something with a story in it")
    base.step(pid, "plan", status="done", note=note)


def do_pictures(pid: str) -> None:
    p = store.load(pid)
    st = style_of(p)
    s = base.sdict(p)
    w, h = _w_h(p)
    aspect = p.get("aspect") or "16:9"
    base.step(pid, "pictures", status="working")
    prev, fresh_count, models = b"", 0, []
    for sh in p["plan"]["shots"]:
        base.check(pid)
        if sh.get("picture") and store.file_path(pid, sh["picture"]):
            prev = base.read(pid, sh["picture"]) or prev
            continue
        chain = bool(prev) and not sh.get("fresh")
        seed = media.seed_of(pid, sh["n"], p.get("version", 1))

        def draw(as_edit: bool, salt: int = 0):
            prompt = edit_prompt(st, sh) if as_edit else image_prompt(st, sh, aspect)
            raw, meta = media.picture(prompt, [prev] if as_edit else [], w, h, seed + salt, f"{pid}-S{sh['n']}",
                                      s=s, negative=negative_for(st))
            return compose.fill(raw, w, h), meta      # bands cut and the frame filled before anything else sees it

        img, info = draw(chain)
        if chain and prev and compose.too_same(prev, img):
            base.logger(pid)({"text": f"Shot {sh['n']} came back as the shot before it; drew it fresh from the words instead.",
                              "kind": "warn"})
            img, info = draw(False, salt=977)
            chain = False
        fresh_count += not chain
        pseq = len([t for t in (sh.get("takes") or []) if t.get("kind") == "picture"]) + 1
        name = base.write(pid, f"S{sh['n']:02d}{'' if pseq == 1 else chr(96 + pseq)}.png", img)
        model = str(info.get("model") or "")
        models.append(model)

        def record(q, n=sh["n"], name=name, m=model, drawn=not chain):
            t = q["plan"]["shots"][n - 1]
            takes.add(t, "picture", name, model=m, note="drawn fresh" if drawn else "continued from the shot before")
        store.update(pid, record)
        prev = img
    total = len(p["plan"]["shots"])
    base.step(pid, "pictures", status="done", model=" + ".join(sorted({m for m in models if m})) or None,
              note=f"{total} shots drawn in the {st['name']} look: {fresh_count} fresh, {total - fresh_count} continued "
                   f"from the shot before")


def do_motion(pid: str) -> None:
    from .. import config
    from ..stickman import video
    from .asmr_cooking import MOVES, _macro_clip
    p = store.load(pid)
    st = style_of(p)
    s = base.sdict(p)
    w, h = _w_h(p)
    secs = _each(p)
    base.step(pid, "motion", status="working")
    d = store.pdir(pid)
    want_video = (p.get("motion") or "video") == "video" and video.ready(s)
    if (p.get("motion") or "video") == "video" and not want_video:
        store.say(pid, "No video model is ready (add a fal.ai key with credit in Settings), so each shot gets a slow "
                       "camera move and sound made in code. The film still gets made.", "warn")
    kinds: list[str] = []
    for sh in p["plan"]["shots"]:
        base.check(pid)
        if sh.get("video") and store.file_path(pid, sh["video"]):
            continue
        img = base.read(pid, sh.get("picture"))
        if not img:
            raise RuntimeError(f"shot {sh['n']} has no picture yet")
        vseq = len([t for t in (sh.get("takes") or []) if t.get("kind") == "video"]) + 1
        out = d / f"S{sh['n']:02d}{'' if vseq == 1 else chr(96 + vseq)}.mp4"
        made = False
        if want_video:
            try:
                out.write_bytes(video.clip(motion_prompt(st, sh, secs), [img], None, round(secs),
                                           p.get("aspect") or "16:9", audio=True))
                made, _ = True, kinds.append("Seedance 2.0")
                _meter("video", "Seedance 2.0", round(secs), pid, p.get("skill") or "")
            except Exception as e:  # noqa: BLE001 - a finished film beats a stopped run
                want_video = False
                store.say(pid, f"Shot {sh['n']}: the AI video failed ({str(e)[:160]}). Carrying on with camera moves and "
                               "sound made in code for the rest of this run.", "warn")
        if not made:
            still = d / f"{out.stem}_still.png"
            still.write_bytes(img)
            _macro_clip(still, out, w, h, secs, MOVES[(sh["n"] - 1) % len(MOVES)], config.ffmpeg())
            kinds.append("camera move")
            _meter("video", "camera move", round(secs), pid, p.get("skill") or "")

        def record_clip(q, n=sh["n"], name=out.name, how=kinds[-1] if kinds else ""):
            takes.add(q["plan"]["shots"][n - 1], "video", name, model=how)
        store.update(pid, record_clip)
    base.step(pid, "motion", status="done", model=" + ".join(sorted(set(kinds))) or None,
              note="" if set(kinds) == {"Seedance 2.0"} else
                   f"Slow camera moves, with the {st['name']} sound palette synthesised per shot.")


def do_finish(pid: str) -> None:
    import shutil

    from ..series import assemble
    from ..stickman import video
    from . import foley
    p = store.load(pid)
    st = style_of(p)
    w, h = _w_h(p)
    secs = _each(p)
    base.step(pid, "finish", status="working")
    d = store.pdir(pid)
    work = d / "work"
    work.mkdir(exist_ok=True)
    parts, total, made = [], 0.0, 0
    kinds_sound: set[str] = set()
    for sh in p["plan"]["shots"]:
        clip = d / (sh.get("video") or "")
        if not clip.is_file():
            raise RuntimeError(f"shot {sh['n']} has no clip yet")
        fit = assemble.fit_shot(clip, work / f"S{sh['n']:02d}_fit.mp4", secs, w, h)
        sfx = None
        if not video.has_audio(clip):
            how, cue = sound_plan(st, sh)
            sfx = work / f"S{sh['n']:02d}.wav"
            sfx.write_bytes(foley.wav(cue, secs, seed=sh["n"] * 17) if how == "foley"
                            else foley.room(secs, seed=sh["n"] * 17))
            kinds_sound.add(how)
            made += 1
        aud = assemble.shot_audio(work / f"S{sh['n']:02d}_a.wav", secs, None, sfx, line_at=0.0)
        parts.append({"video": fit, "audio": aud, "seconds": secs})
        total += secs
    joined = assemble.part(parts, work, work / "joined.mp4", w, h, None, [])
    shutil.copyfile(joined, d / "final.mp4")
    base.put(pid, video="final.mp4", finalSeconds=round(total, 1))
    note = f"{len(parts)} shots in the {st['name']} look"
    if not made:
        note += ", the shots carry their own sound"
    elif kinds_sound == {"foley"}:
        note += f", {made} carrying sound made in code"
    else:
        note += (f". {made} shot(s) have only quiet room tone: this look asks for a score "
                 f"({_trim(ambience(st, p['plan']['shots'][0]), 90)}) and AVOS has no music model, so it leaves the "
                 "track clear for you to drop one in rather than faking it")
    base.step(pid, "finish", status="done", note=note)


RUN = {"plan": do_plan, "pictures": do_pictures, "motion": do_motion, "finish": do_finish}


# ---------- one Skills-tab entry per style ----------
class StyleSkill:
    """One style, dressed as a skill module. Same STAGES, LABELS and RUN for all 66; only ID and INFO differ."""

    STAGES = STAGES
    LABELS = LABELS
    RUN = RUN
    last_stage = staticmethod(last_stage)
    reset = staticmethod(reset)
    outputs_of = staticmethod(outputs_of)

    def __init__(self, slug: str, st: dict) -> None:
        self.slug, self.style = slug, st
        self.ID = PREFIX + slug
        about = _join([st.get("essence") or st.get("quote") or "", "Good for: " + ", ".join(st["uses"]) if st.get("uses") else ""])
        self.INFO = {
            "id": self.ID, "name": st["name"], "group": f"Film · {st['cat']}", "kind": KIND,
            "made_for": st.get("quote") or st["name"],
            "about": about[:600],
            "input": "What the film is about, in a line",
            "outputs": [LABELS[s] for s in ("plan", "pictures", "finish")],
            "aspect": "16:9", "aspects": ["16:9", "9:16", "1:1"],
            "seconds": LENGTHS, "default_seconds": DEFAULT_SECONDS, "native_audio": True,
            "examples": [x for x in ([st.get("line")] + list(st.get("uses") or [])) if x][:4],
            "make": [["media", "Plan and film"], ["prompts", "The plan and prompts only"]],
            "cta": ["Write the shot plan", "Make the film"],
            "note": f"Every shot is locked to the {st['name']} look: the same look sentence, colour rule and list of "
                    "what the style is not goes into all of them, which is what makes a six-shot film hold together. "
                    "Needs an AI writer for the plan and a picture model for the shots; a video model is optional - "
                    "without one each shot gets a slow camera move and sound made in code.",
            "credit": "Style from the Lemo-Opuscar library by Lemomo (MIT); cover still by Lemomo, CC BY 4.0. "
                      "AVOS uses the style to lock the prompts; upstream renders the same look in code.",
        }
        self.INFO["lengths"] = [{"seconds": n, "scenes": shots_for(n), "each": round(seconds_each(n, shots_for(n)), 1)}
                                for n in LENGTHS]


def skills() -> dict[str, StyleSkill]:
    return {PREFIX + slug: StyleSkill(slug, st) for slug, st in sorted(STYLES.items())}
