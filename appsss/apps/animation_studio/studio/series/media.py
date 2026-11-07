"""Every picture, voice and clip a Series needs, from the open models on your GPUs, with honest fallbacks.

    character sheet   Qwen-Image-Edit 2511 (style pictures / your upload as references) → text-to-image
    location plate    Qwen-Image-Edit 2511 (style pictures)                                → text-to-image
    keyframe          Qwen-Image-Edit 2511 with the shot's character sheets + location     → text-to-image
    voice sample      your recording → Indic Parler-TTS (from the description) → an Edge voice
    line              Chatterbox / IndicF5 cloning the approved sample (emotion per line) → Indic Parler-TTS → Edge
    talking shot      InfiniteTalk (lip-sync to the line) → LongCat Avatar → the keyframe with a slow push-in
    action shot       Wan 2.2 I2V (≤ 5 s) / LTX-2.3 (longer) → the keyframe with a camera move
    sound effects     HunyuanVideo-Foley (watches the clip)                                → none
    music             your theme → ACE-Step 1.5                                             → none

Each call returns (data, info) where info says which model made it and whether it was a fallback, so the part
review can tell you exactly what was used.
"""
from __future__ import annotations

import asyncio
import hashlib
import io
import math
import os
import struct
import subprocess
import tempfile
import wave
from pathlib import Path
from typing import Any

from .. import avos_settings, config, models
from ..creative import compiler as C, dna as DNA, scene as SG
from . import languages

NEG = "text, letters, watermark, speech bubble, caption, blurry, deformed, extra limbs, extra fingers, duplicate character, character sheet layout"
STYLE_KEEP = "Keep exactly the art style of the reference pictures: line weight, colours, shading and proportions."


class Fallback(Exception):
    """No open model could do it; the message says why (shown on the part review)."""


def _ready(mid: str) -> bool:
    try:
        return models.ready(mid)[0]
    except Exception:  # noqa: BLE001 - unknown model / catalog missing
        return False


STEP_LABELS = {"pictures": "Character sheets, places and frames", "motion": "Action shots (image to video)",
               "lipsync": "Talking shots (lip-sync)", "lines": "Voices (lines)", "sfx": "Sound effects and ambience",
               "music": "Music"}
BACKEND_LABELS = {"gpu": "Your GPU (worker)", "comfyui": "Your ComfyUI server", "fal": "fal.ai (API key)",
                  "cloudflare": "Cloudflare (free key)", "replicate": "Replicate (API key)"}


def model_options(s: dict) -> list[dict[str, Any]]:
    """For the Models panel: per step, your choice and every model that can do it, where it can run and why not."""
    lang = s.get("language") or "en"
    out = []
    for step, label in STEP_LABELS.items():
        ids = languages.line_models(lang) if step == "lines" else STEP_MODELS[step]
        if step in CUSTOM_TASK:        # the models you added in Settings → Add a model show up beside the built-in ones
            ids = [*ids, *[m["id"] for m in avos_settings.custom_models(CUSTOM_TASK[step]) if m["id"] not in ids]]
        opts = []
        for mid in ids:
            try:
                m = models.get(mid)
                avail = models.available(mid)
            except Exception as e:  # noqa: BLE001 - not in the catalog
                opts.append({"id": mid, "name": mid, "ready": False, "why": str(e)[:200], "backends": {}})
                continue
            ok, why = models.ready(mid)
            opts.append({"id": mid, "name": m["name"], "ready": ok, "backend": why if ok else None, "why": None if ok else why,
                         "backends": {b: {"label": BACKEND_LABELS.get(b, b), "why": r} for b, r in avail.items()},
                         "price": (m.get("fal") or {}).get("price"), "custom": bool(m.get("custom"))})
        extra = [{"id": "edge", "name": "Edge voices (free, online)", "ready": _edge_installed(), "backends": {}}] if step == "lines" else []
        if step in ("music", "sfx"):
            extra.append({"id": "off", "name": "Off", "ready": True, "backends": {}})
        model, backend = choice(s, step)
        out.append({"step": step, "label": label, "model": model, "backend": backend or "auto", "options": opts + extra})
    return out


def ready_report(lang: str) -> dict[str, Any]:
    """For the Series page: which step will use which model right now."""
    def first(ids: list[str]) -> str | None:
        return next((m for m in ids if _ready(m)), None)
    return {
        "pictures": first(["qwen-image-edit"]),
        "picturesFallback": first(["qwen-image", "z-image", "flux-schnell"]),
        "voiceDesign": first(languages.design_models(lang)),
        "lines": first(languages.line_models(lang)),
        "lipsync": first(["infinitetalk", "longcat-avatar"]),
        "motion": first(["wan-2.2", "ltx-2.3"]),
        "sfx": first(["hunyuan-foley"]),
        "music": first(["ace-step"]),
        "edge": _edge_installed(),
        "languages": {"lines": languages.line_models(lang), "design": languages.design_models(lang)},
    }


# ---------- your model choices (Series / Film page → Models: per step a model and where it runs) ----------
STEP_MODELS: dict[str, list[str]] = {
    "pictures": ["qwen-image-edit", "z-image", "qwen-image", "flux-schnell"],
    "motion": ["wan-2.2", "ltx-2.3"],
    "lipsync": ["infinitetalk", "longcat-avatar"],
    "music": ["ace-step"],
    "sfx": ["hunyuan-foley"],
}


CUSTOM_TASK = {"pictures": "image", "motion": "video", "lipsync": "avatar"}   # step → the task of models you add in Settings


def choice(s: dict | None, step: str) -> tuple[str, str | None]:
    """(model or "auto" / "off" / "edge", backend or None) you picked for a step."""
    c = (((s or {}).get("settings") or {}).get("models") or {}).get(step) or {}
    b = c.get("backend")
    return str(c.get("model") or "auto"), (b if b and b != "auto" else None)


def strict(s: dict | None, step: str) -> bool:
    """You picked one specific model for this step: use only that model (no other model, no free chain, no still-picture stand-in)."""
    return choice(s, step)[0] not in ("auto", "off", "edge")


def local_only(s: dict | None) -> bool:
    """"This PC only": models may run only on your own GPU worker / ComfyUI, never on fal.ai or Cloudflare."""
    return bool((((s or {}).get("settings") or {}).get("local_only")))


LOCAL_BACKENDS = ("gpu", "comfyui")


def ordered(s: dict | None, step: str, default: list[str]) -> list[str]:
    m, _ = choice(s, step)
    if m in ("auto", "off", "edge"):
        return list(default)
    return [m] if strict(s, step) else [m, *[x for x in default if x != m]]


def where(s: dict | None, step: str, mid: str) -> str | None:
    """The place a model runs. Raises ModelUnavailable (with the exact reason) when your pick can't be honoured:
    a place you chose is down, or "this PC only" is on and no local worker has the model."""
    m, b = choice(s, step)
    b = b if m in (mid, "auto") else None
    if not local_only(s) and not (b and m == mid):
        return b
    try:
        avail = models.available(mid)
    except Exception:  # noqa: BLE001 - unknown model: let the normal path say so
        return b
    allowed = [b] if b else list(LOCAL_BACKENDS)
    if local_only(s):
        allowed = [x for x in allowed if x in LOCAL_BACKENDS]
    for x in allowed:
        if x in avail and avail[x] is None:
            return x
    name = models.get(mid)["name"]
    why = "; ".join(f"{x}: {avail[x]}" for x in allowed if avail.get(x)) or "it has no local version"
    place = "this PC" if local_only(s) else (b or "that place")
    raise models.ModelUnavailable(f"{name} is set to run only on {place}, but it can't right now ({why}). Other providers were NOT tried.")


def usable(s: dict | None, step: str, mid: str) -> bool:
    try:
        where(s, step, mid)
    except Exception:  # noqa: BLE001
        return False
    return _ready(mid) if not (local_only(s) or strict(s, step)) else True


def seed_of(*parts: Any) -> int:
    return int(hashlib.sha1("|".join(map(str, parts)).encode()).hexdigest()[:8], 16)


def _t2i(prompt: str, w: int, h: int, seed: int, prefer: list[str] | None = None, s: dict | None = None) -> tuple[bytes, str]:
    errors: list[str] = []
    only = strict(s, "pictures")
    order = ordered(s, "pictures", []) if only else [*ordered(s, "pictures", []), *(prefer or []), *models.route_image(prompt)]
    for mid in dict.fromkeys(order):
        if mid == "qwen-image-edit" and not only:
            continue
        if only or _ready(mid):
            try:
                return models.image(mid, prompt, w, h, seed, backend=where(s, "pictures", mid)), mid
            except Exception as e:  # noqa: BLE001 - a provider failing (no credit, a refused key, down): try the next one
                errors.append(f"{mid}: {str(e)[:200]}")
    if only or local_only(s):                       # you picked this model / this PC: nothing else is tried
        raise Fallback("The picture model you chose could not draw it: " + (" | ".join(errors) or "it isn't set up") +
                       " (Other providers were not tried because you picked this model. Change the pictures model to Automatic to allow them.)")
    from ..render.images import free_picture, generate_plate    # the free chain: Cloudflare FLUX.2 / FLUX.1, then Pollinations
    got = free_picture(prompt, w, h, seed)                       # with the seed and the size (one face seed per character)
    if got:
        return got
    with tempfile.TemporaryDirectory() as t:
        out = generate_plate(prompt, Path(t) / "x.png", w, h)
        if out:
            return out.read_bytes(), "free picture chain"
    down = any(k in e for e in errors for k in ("Errno 101", "unreachable", "Name or service not known", "Temporary failure in name resolution", "ConnectError"))
    raise Fallback("No picture model could draw it" + (": " + " | ".join(errors) if errors else
                   " (set up Qwen-Image-Edit on a GPU worker, or any image model on the Models page).") +
                   (" The studio cannot reach the internet from Docker (VPN, firewall or DNS). Test: docker exec avos-animation-studio python -c \"import httpx;print(httpx.get('https://api.cloudflare.com/cdn-cgi/trace').text[:80])\"" if down else ""))


def _edit(prompt: str, refs: list[bytes], w: int, h: int, seed: int, tag: str, priority: int = 5, s: dict | None = None,
          negative: str | None = None) -> bytes:
    keys = ("image", "image2", "image3", "image4")
    return models.run_model("qwen-image-edit", task="edit", want="image", prompt=prompt, w=w, h=h, seed=seed,
                            steps=int(os.environ["SERIES_EDIT_STEPS"]) if os.environ.get("SERIES_EDIT_STEPS") else None, negative=negative or NEG,
                            inputs={k: v for k, v in zip(keys, refs[:4])}, timeout=900, priority=priority, tag=tag,
                            backend=where(s, "pictures", "qwen-image-edit"))


def refs_supported(s: dict | None) -> bool:
    """True when the picture model will actually look at reference pictures (an edit model is ready); otherwise faces can drift."""
    picked, _ = choice(s, "pictures")
    from ..render.images import cloudflare_ready
    return bool((models.uses_references(picked) and _ready(picked)) or (picked in ("auto", "qwen-image-edit") and _ready("qwen-image-edit"))
                or (picked == "auto" and not local_only(s) and cloudflare_ready()))


def ref_prompt(prompt: str, n: int) -> str:
    """Tell a reference model what each attached picture is (image 0 = the character, then prop / set) before the shot."""
    if n <= 0:
        return prompt
    lead = ("Image 0 is the character reference: draw exactly this character, same face, hair, glasses, skin, outfit, colours and "
            "the same art style. ")
    if n > 1:
        lead += "The other images are references for the props and the set: keep their shape, colour and style. "
    return lead + "New picture: " + prompt


def picture(prompt: str, refs: list[bytes], w: int, h: int, seed: int, tag: str, priority: int = 5, s: dict | None = None,
            negative: str | None = None) -> tuple[bytes, dict]:
    """A picture from reference pictures when the edit model is ready (and you didn't pick a text-to-image model),
    else from the text alone."""
    picked, _ = choice(s, "pictures")
    if refs and models.uses_references(picked) and _ready(picked):       # a reference-editing model you added in Settings
        try:
            return models.image_edit(picked, prompt, refs, w, h, seed), {"model": picked, "fallback": False}
        except Exception as e:  # noqa: BLE001 - a provider failing: draw from the text instead (said on the shot)
            if strict(s, "pictures"):
                raise Fallback(f"{picked} failed: {str(e)[:200]} (no other model was tried, you picked this one)") from e
            data, mid = _t2i(prompt, w, h, seed, prefer=["qwen-image"], s=s)
            return data, {"model": mid, "fallback": True, "note": f"{picked} failed ({str(e)[:120]}): drawn from text only"}
    if refs and picked in ("auto", "qwen-image-edit") and _ready("qwen-image-edit"):
        try:
            return _edit(prompt, refs, w, h, seed, tag, priority, s, negative), {"model": "qwen-image-edit", "fallback": False}
        except Exception as e:  # noqa: BLE001 - the edit model failing: draw from the text instead (said on the shot)
            if strict(s, "pictures"):
                raise Fallback(f"Qwen-Image-Edit failed: {str(e)[:200]} (no other model was tried, you picked this one)") from e
            data, mid = _t2i(prompt, w, h, seed, prefer=["qwen-image"], s=s)
            return data, {"model": mid, "fallback": True, "note": f"Qwen-Image-Edit failed ({str(e)[:120]}): drawn from text only"}
    if refs and picked == "auto" and not local_only(s):         # free: Cloudflare FLUX.2 [klein] draws FROM the portrait, prop and set
        from ..render.images import cloudflare_flux2, cloudflare_ready
        if cloudflare_ready():
            img = cloudflare_flux2(ref_prompt(prompt, len(refs[:4])), w, h, seed, refs[:4])
            if img:
                return img, {"model": "Cloudflare FLUX.2 klein (from references)", "fallback": False}
    # nothing to draw from yet (a first character sheet without style pictures): the best text-to-image model is right
    data, mid = _t2i(prompt, w, h, seed, prefer=["qwen-image"], s=s)
    return data, ({"model": mid, "fallback": True, "note": "drawn from text only (Qwen-Image-Edit isn't ready): looks may drift"}
                  if refs else {"model": mid, "fallback": False})


# ---------- characters and places ----------
def _style(s: dict) -> str:
    """The series' look as one clause: its Design DNA (or, before the DNA exists, the style notes)."""
    if s.get("dna"):
        return DNA.style_clause(s["dna"])
    return "Art style: " + ((s.get("style") or {}).get("prompt") or (s.get("style") or {}).get("description") or "clean 2D cartoon") + "."


SHEET_NEG = NEG.replace(", character sheet layout", "") + ", inconsistent proportions between views, different outfit in each view, cropped feet, cropped head"


def sheet_prompt(s: dict, c: dict, has_upload: bool, note: str = "") -> str:
    """A real model sheet: the turnaround every later shot is drawn from (so it must be clean, consistent and complete)."""
    style = _style(s)
    who = (f"the character from picture 1 ({c['name']})" if has_upload else
           f"a NEW original character named {c['name']}: {c.get('look') or ''}")
    extra = f" Personality shows in the resting pose and face: {c['personality']}." if c.get("personality") else ""
    return (f"Professional animation character model sheet of {who}. Outfit: {c.get('outfit') or 'as described'}. "
            f"Age {c.get('age') or 'as described'}.{extra} "
            f"Top row: full-body turnaround in a relaxed neutral stance with arms slightly away from the body, in order: front view, "
            f"three-quarter view, side view, back view, all the same height and standing on one ground line. "
            f"Bottom row: head close-ups with six expressions: neutral, happy, angry, sad, surprised, scared; and one close-up of the hands. "
            f"Identical face, hair, proportions and outfit colours in every view, simple flat colours so the design can be redrawn "
            f"consistently, clean silhouette. Plain light grey background, even soft lighting, no shadows on the ground, no text, "
            f"no labels. {style} {STYLE_KEEP if (s.get('style') or {}).get('refs') or has_upload else ''} "
            f"{('Change: ' + note) if note else ''}").strip()


def character_sheet(s: dict, c: dict, style_refs: list[bytes], upload: bytes | None, version: int, note: str = "") -> tuple[bytes, dict]:
    refs = ([upload] if upload else []) + style_refs[: 3 - (1 if upload else 0)]
    return picture(sheet_prompt(s, c, bool(upload), note), refs, 1344, 768, seed_of(s["id"], c["id"], version),
                   tag=f"{s['title']} · {c['name']} sheet", priority=0, s=s, negative=SHEET_NEG)


def location_plate(s: dict, loc: dict, style_refs: list[bytes], version: int, note: str = "") -> tuple[bytes, dict]:
    style = _style(s)
    w, h = s["format"]["width"], s["format"]["height"]
    prompt = (f"Background art for an animated series: {loc['name']}, {loc.get('description') or ''}. Empty scene, no people, "
              f"wide establishing view, eye level, daytime, no text. {style} {STYLE_KEEP if style_refs else ''} "
              f"{('Change: ' + note) if note else ''}").strip()
    return picture(prompt, style_refs[:3], w, h, seed_of(s["id"], loc["id"], version), tag=f"{s['title']} · {loc['name']}", priority=0, s=s)


def names_of(s: dict) -> dict[str, str]:
    return {c["id"]: c["name"] for c in s.get("characters") or []}


def stage_of(s: dict, shot: dict) -> dict:
    """The shot's scene graph (shots planned before v14 get one from their framing and subjects)."""
    st = shot.get("stage")
    if isinstance(st, dict) and "camera" in st:
        return st
    return SG.normalize_scene({"actors": [{"id": shot.get("speaker"), "speaking": True, "expression": shot.get("emotion") or "neutral"}]
                               if shot.get("speaker") else []}, subjects=shot.get("subjects") or [], framing=shot.get("framing"),
                              location=shot.get("location", ""), time=shot.get("time", "day"))


def blueprint_of(s: dict, shot: dict) -> dict:
    bp = shot.get("blueprint")
    if isinstance(bp, dict) and "camera" in bp:
        return bp
    stage = stage_of(s, shot)
    return SG.normalize_motion({"tracks": [{"target": (shot.get("subjects") or [None])[0], "keys": [{"t": 0, "action": shot.get("motion") or ""}]}]},
                               stage, duration=float(shot.get("seconds") or 3), speaker=shot.get("speaker"))


def keyframe_prompt(s: dict, shot: dict, refs_said: list[str], note: str = "") -> str:
    locs = {x["id"]: x for x in s.get("locations") or []}
    loc = locs.get(shot.get("location") or "", {})
    stage = stage_of(s, shot)
    return C.keyframe_prompt(stage, s.get("dna") or {}, names_of(s), refs_said,
                             f"{loc.get('name', shot.get('location'))}: {loc.get('description', '')}".strip(": "), note)


def keyframe(s: dict, shot: dict, sheets: dict[str, bytes], plate: bytes | None, seed: int, tag: str, note: str = "") -> tuple[bytes, dict]:
    """The shot's first frame, drawn from the approved character sheets + the place, compiled from the scene graph."""
    cast = names_of(s)
    stage = stage_of(s, shot)
    subj = [a["id"] for a in stage["actors"] if a["id"] in sheets][: (2 if plate else 3)]
    refs, said = [], []
    for c in subj:
        refs.append(sheets[c])
        said.append(f"{cast[c]}'s character sheet")
    if plate:
        refs.append(plate)
        said.append(f"the location ({shot.get('location')})")
    prompt = keyframe_prompt(s, shot, said, note)
    W, H = s["format"]["width"], s["format"]["height"]
    if not refs:
        data, mid = _t2i(prompt, W, H, seed, s=s)
        return data, {"model": mid, "fallback": mid != "qwen-image-edit", "prompt": prompt}
    data, info = picture(prompt, refs, W, H, seed, tag, s=s)
    return data, {**info, "prompt": prompt}


def modify_keyframe(s: dict, shot: dict, key: bytes, instruction: str, sheets: dict[str, bytes], seed: int, tag: str) -> tuple[bytes, dict]:
    """Genjutsu-style edit: change one thing in the frame (an object, an outfit, the light) and keep the rest."""
    if not _ready("qwen-image-edit"):
        raise Fallback("Modify shot needs Qwen-Image-Edit on a GPU worker.")
    cast = names_of(s)
    refs, said = [key], ["the current frame"]
    for c in (shot.get("subjects") or [])[:2]:
        ins = instruction.lower()
        if c in sheets and (c.lower() in ins or cast.get(c, "").lower() in ins):
            refs.append(sheets[c])
            said.append(f"{cast[c]}'s character sheet")
    prompt = ("; ".join(f"picture {i + 1} is {x}" for i, x in enumerate(said)) +
              f". Edit picture 1: {instruction}. Change ONLY that; keep everything else exactly the same: composition, camera, "
              f"characters, poses, expressions, background, lighting and art style. {_style(s)} No text.")
    W, H = s["format"]["width"], s["format"]["height"]
    return _edit(prompt, refs, W, H, seed, tag, priority=0, s=s), {"model": "qwen-image-edit", "fallback": False, "prompt": prompt, "edit": instruction}


# ---------- voices ----------
SAMPLE_TEXT = {
    "hi": "नमस्ते! मेरा नाम {name} है। आज का दिन बहुत मज़ेदार होने वाला है, बस देखते जाओ!",
    "en": "Hi! I'm {name}. Trust me, today is going to be a very interesting day.",
    "ta": "வணக்கம்! என் பெயர் {name}. இன்று ஒரு சுவாரஸ்யமான நாள்!",
    "te": "నమస్తే! నా పేరు {name}. ఈ రోజు చాలా సరదాగా ఉండబోతోంది!",
    "bn": "নমস্কার! আমার নাম {name}। আজকের দিনটা খুব মজার হবে!",
    "mr": "नमस्कार! माझं नाव {name} आहे. आजचा दिवस खूप मजेदार असणार आहे!",
    "es": "¡Hola! Soy {name}. Hoy va a ser un día muy interesante.",
    "fr": "Salut ! Je m'appelle {name}. Aujourd'hui va être une journée intéressante.",
}
EXAGGERATION = {"neutral": 0.5, "happy": 0.65, "excited": 0.85, "angry": 0.9, "shout": 1.1, "sad": 0.4, "whisper": 0.3,
                "scared": 0.7, "surprised": 0.8, "sarcastic": 0.6, "worried": 0.55, "laugh": 0.9}
EDGE_STYLE = {"angry": ("+8%", "+6Hz"), "shout": ("+10%", "+10Hz"), "excited": ("+10%", "+8Hz"), "happy": ("+5%", "+4Hz"),
              "sad": ("-10%", "-6Hz"), "whisper": ("-8%", "-4Hz"), "scared": ("+6%", "+8Hz"), "surprised": ("+6%", "+10Hz")}


def sample_text(s: dict, c: dict) -> str:
    v = c.get("voice") or {}
    if v.get("sampleText"):
        return v["sampleText"]
    tts = languages.get(s.get("language") or "en").tts
    return (SAMPLE_TEXT.get(tts) or SAMPLE_TEXT["en"]).format(name=c["name"])


def voice_description(c: dict) -> str:
    v = (c.get("voice") or {}).get("description") or ""
    base = f"A {c.get('gender') if c.get('gender') in ('male', 'female') else ''} speaker, {c.get('age') or 'adult'}, expressive and natural".replace("  ", " ")
    return (v or base).rstrip(". ") + ". Studio-quality recording, very clear audio, close to the microphone, no background noise, no reverb."


def edge_voice(s: dict, c: dict, index: int) -> dict:
    """A distinct Edge voice for each character: by gender (child voices for kids), then a pitch/speed offset."""
    lg = languages.get(s.get("language") or "en")
    kid = bool(c.get("age")) and any(ch.isdigit() for ch in str(c.get("age"))) and int("".join(ch for ch in str(c["age"]) if ch.isdigit())[:2] or 30) < 14
    pool = (lg.edge_child if kid and lg.edge_child else lg.edge_female if c.get("gender") == "female" else lg.edge_male) or lg.edge_male
    voice = pool[index % len(pool)]
    shift = [0, 12, -10, 20, -18, 6][(index // max(1, len(pool))) % 6] + (14 if kid else 0)
    return {"edge": voice, "pitch": f"{shift:+d}Hz", "rate": "+0%"}


def _edge_installed() -> bool:
    try:
        import importlib.util
        return importlib.util.find_spec("edge_tts") is not None
    except ImportError:
        return False


def edge_say(text: str, voice: dict, emotion: str = "neutral") -> bytes:
    """Edge TTS → WAV (needs internet)."""
    import edge_tts  # type: ignore

    rate, pitch = EDGE_STYLE.get(emotion, ("+0%", "+0Hz"))
    p0 = int(str(voice.get("pitch") or "+0Hz").replace("Hz", "")) + int(pitch.replace("Hz", ""))
    with tempfile.TemporaryDirectory() as t:
        mp3, wav = Path(t) / "a.mp3", Path(t) / "a.wav"

        async def go() -> None:
            await edge_tts.Communicate(text, voice.get("edge") or "en-US-GuyNeural", rate=rate, pitch=f"{p0:+d}Hz").save(str(mp3))
        asyncio.run(go())
        if not mp3.is_file() or mp3.stat().st_size < 500:
            raise Fallback("Edge TTS returned nothing (needs internet).")
        _ff(["-i", str(mp3), "-ac", "1", "-ar", "24000", str(wav)])
        return wav.read_bytes()


def design_voice(s: dict, c: dict, index: int, upload: bytes | None, tag: str) -> tuple[bytes, dict]:
    """The character's voice sample (what you approve; every line is then cloned from it)."""
    text = sample_text(s, c)
    lang = s.get("language") or "en"
    if upload:
        return to_wav(upload), {"model": "your recording", "fallback": False, "sampleText": c.get("voice", {}).get("sampleText") or ""}
    for mid in ([] if choice(s, "lines")[0] == "edge" else languages.design_models(lang)):
        if _ready(mid):
            data = models.run_model(mid, task="speech", want="audio", prompt=text, seed=seed_of(s["id"], c["id"], index),
                                    options={"language": languages.get(lang).tts, "description": voice_description(c)},
                                    timeout=600, priority=0, tag=tag)
            return data, {"model": mid, "fallback": False, "sampleText": text}
    if _edge_installed():
        ev = edge_voice(s, c, index)
        try:
            return edge_say(text, ev), {"model": "edge", "fallback": True, "sampleText": text, **ev}
        except Exception as e:  # noqa: BLE001 - offline
            raise Fallback(f"No voice model for {languages.get(lang).name} is ready and Edge TTS failed ({e}).") from e
    raise Fallback(f"No voice model for {languages.get(lang).name} is ready (GPU worker speech backend) and Edge TTS isn't installed.")


def say_line(s: dict, c: dict, text: str, emotion: str, seed: int, tag: str) -> tuple[bytes, dict]:
    """One line in the character's approved voice."""
    v = c.get("voice") or {}
    sample = Path(store_path(s, v.get("sample"))) if v.get("sample") else None
    lang = s.get("language") or "en"
    tts = languages.get(lang).tts
    errors = []
    picked, _ = choice(s, "lines")
    for mid in ([] if picked == "edge" else ordered(s, "lines", languages.line_models(lang))):
        if not _ready(mid):
            continue
        opts: dict[str, Any] = {"language": tts, "exaggeration": EXAGGERATION.get(emotion, 0.5)}
        inputs: dict[str, bytes] = {}
        if mid in ("chatterbox", "indicf5"):
            if not (sample and sample.is_file()):
                continue
            inputs["audio"] = sample.read_bytes()
            opts["ref_text"] = v.get("sampleText") or ""
            if mid == "indicf5" and not opts["ref_text"]:
                continue
        else:   # Indic Parler-TTS speaks from the description
            opts["description"] = voice_description(c) + (f" The speaker sounds {emotion}." if emotion != "neutral" else "")
        try:
            data = models.run_model(mid, task="speech", want="audio", prompt=text, seed=seed, inputs=inputs, options=opts,
                                    timeout=600, tag=tag, backend=where(s, "lines", mid))
            return data, {"model": mid, "fallback": False}
        except Exception as e:  # noqa: BLE001 - try the next voice model
            errors.append(f"{mid}: {e}")
    if v.get("edge") and _edge_installed():
        try:
            return edge_say(text, v, emotion), {"model": "edge", "fallback": True, "note": "; ".join(errors)[:300]}
        except Exception as e:  # noqa: BLE001
            errors.append(f"edge: {e}")
    raise Fallback("No voice could speak this line. " + "; ".join(errors)[:400])


def store_path(s: dict, rel_path: str | None) -> str:
    from . import store
    return str(store.sdir(s["id"]) / (rel_path or ""))


# ---------- motion ----------
def frames_for(mid: str, seconds: float) -> tuple[int, int]:
    fps = 25 if mid in ("ltx-2.3", "infinitetalk", "longcat-avatar") else 16
    mult = 8 if mid == "ltx-2.3" else 4
    n = max(9, round(seconds * fps) + 1)
    n = math.ceil((n - 1) / mult) * mult + 1
    cap = {"wan-2.2": 81, "ltx-2.3": 481}.get(mid, 100000)
    while n > cap:
        n -= mult
    return n, fps


def motion_prompt(s: dict, shot: dict, model: str, note: str = "") -> str:
    locs = {x["id"]: x for x in s.get("locations") or []}
    loc = locs.get(shot.get("location") or "", {})
    return C.motion_prompt(blueprint_of(s, shot), stage_of(s, shot), s.get("dna") or {}, names_of(s), model, note,
                           shot.get("emotion") or "", loc.get("name", shot.get("location") or ""), str(shot.get("sfx") or ""))


def planned_motion(s: dict, shot: dict, lipsync: bool) -> dict:
    """Stage 5 before anything moves: which model will animate the shot and exactly what it will be told."""
    order = ordered(s, "lipsync", ["infinitetalk", "longcat-avatar"]) if lipsync else \
        ordered(s, "motion", ["wan-2.2", "ltx-2.3"] if float(shot.get("seconds") or 3) <= 5.2 else ["ltx-2.3", "wan-2.2"])
    mid = next((m for m in order if _ready(m)), None)
    return {"model": mid or "still", "prompt": motion_prompt(s, shot, mid or order[0], shot.get("note") or ""), "negative": DNA.negative(s.get("dna") or {})}


def talking(s: dict, shot: dict, key: bytes, line: bytes, seconds: float, seed: int, tag: str, note: str = "") -> tuple[bytes, dict]:
    errors: list[str] = []
    for mid in ordered(s, "lipsync", ["infinitetalk", "longcat-avatar"]):
        if _ready(mid):
            prompt = motion_prompt(s, shot, mid, note)
            n, fps = frames_for(mid, seconds)
            try:
                data = models.run_model(mid, task="avatar", want="video", prompt=prompt, w=s["format"]["width"], h=s["format"]["height"],
                                        seconds=seconds, frames=n, fps=fps, seed=seed, inputs={"image": key, "audio": line},
                                        negative=DNA.negative(s.get("dna") or {}), timeout=2400, tag=tag, backend=where(s, "lipsync", mid))
            except Exception as e:  # noqa: BLE001 - a provider failing (no credit, offline): the next model, else the still
                errors.append(f"{mid}: {str(e)[:160]}")
                continue
            return data, {"model": mid, "fallback": False, "prompt": prompt}
    return still_motion(s, key, seconds, still_kind(s, shot, "push")), {"model": "still", "fallback": True,
                                                                        "note": "; ".join(errors)[:300] or "no lip-sync model ready: still picture with the camera move"}


def action(s: dict, shot: dict, key: bytes, seconds: float, seed: int, tag: str, note: str = "") -> tuple[bytes, dict]:
    errors: list[str] = []
    for mid in ordered(s, "motion", ["wan-2.2", "ltx-2.3"] if seconds <= 5.2 else ["ltx-2.3", "wan-2.2"]):
        if _ready(mid):
            prompt = motion_prompt(s, shot, mid, note)
            n, fps = frames_for(mid, seconds)
            try:
                data = models.run_model(mid, task="video", want="video", prompt=prompt, w=s["format"]["width"], h=s["format"]["height"],
                                        seconds=seconds, frames=n, fps=fps, seed=seed, inputs={"image": key},
                                        negative=DNA.negative(s.get("dna") or {}), timeout=2400, tag=tag, backend=where(s, "motion", mid))
            except Exception as e:  # noqa: BLE001 - a provider failing (no credit, offline): the next model, else the still
                errors.append(f"{mid}: {str(e)[:160]}")
                continue
            return data, {"model": mid, "fallback": False, "prompt": prompt}
    return still_motion(s, key, seconds, still_kind(s, shot, "pan")), {"model": "still", "fallback": True,
                                                                       "note": "; ".join(errors)[:300] or "no video model ready: still picture with the camera move"}


def restyle_keep_motion(s: dict, shot: dict, clip: bytes, key: bytes, seconds: float, seed: int, tag: str) -> tuple[bytes, dict] | None:
    """Keep the exact movement of the old clip, rebuild its look from the new first frame (Wan VACE). None if not set up."""
    if not _ready("wan-vace"):
        return None
    prompt = motion_prompt(s, shot, "wan-vace")
    n, fps = frames_for("wan-vace", seconds)
    data = models.run_model("wan-vace", task="control", want="video", prompt=prompt, w=s["format"]["width"], h=s["format"]["height"],
                            seconds=seconds, frames=max(81, n), fps=fps, seed=seed, inputs={"image": key, "video": clip}, timeout=2400, tag=tag)
    return data, {"model": "wan-vace", "fallback": False, "prompt": prompt, "kept": "motion of the previous take"}


def motion_transfer(s: dict, shot: dict, key: bytes, driver: bytes, seconds: float, seed: int, tag: str) -> tuple[bytes, dict]:
    """A reference video drives the character in the keyframe (body, gestures, camera), Genjutsu-style."""
    for mid in ("wan-2.2-animate", "wan-vace"):
        if _ready(mid):
            prompt = motion_prompt(s, shot, mid)
            n, fps = frames_for(mid, seconds)
            data = models.run_model(mid, task="avatar" if mid == "wan-2.2-animate" else "control", want="video", prompt=prompt,
                                    w=s["format"]["width"], h=s["format"]["height"], seconds=seconds, frames=n, fps=fps, seed=seed,
                                    inputs={"image": key, "video": driver}, timeout=2400, tag=tag)
            return data, {"model": mid, "fallback": False, "prompt": prompt, "driver": True}
    raise Fallback("Motion transfer needs Wan 2.2 Animate (or Wan VACE) on a GPU worker.")


STILL_MOVES = {"push_in": "push", "zoom_in": "push", "pull_out": "pull", "pan_right": "pan", "truck_right": "pan", "orbit_right": "pan",
               "pan_left": "panl", "truck_left": "panl", "orbit_left": "panl", "tilt_up": "up", "crane_up": "up", "tilt_down": "down",
               "crane_down": "down", "static": "hold", "handheld": "hold"}


def still_kind(s: dict, shot: dict, default: str) -> str:
    """The no-GPU stand-in follows the shot's own camera move."""
    try:
        return STILL_MOVES.get(blueprint_of(s, shot)["camera"]["move"], default)
    except Exception:  # noqa: BLE001
        return default


def still_motion(s: dict, key: bytes, seconds: float, kind: str) -> bytes:
    """The keyframe with a gentle camera move (the no-GPU stand-in for a clip)."""
    W, H, fps = s["format"]["width"], s["format"]["height"], 24
    n = max(1, int(seconds * fps))
    with tempfile.TemporaryDirectory() as t:
        src, out = Path(t) / "k.png", Path(t) / "m.mp4"
        src.write_bytes(key)
        u = f"(on/{n})"
        cx, cy = "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"
        z, x, y = {"push": (f"1+0.12*{u}", cx, cy), "pull": (f"1.12-0.12*{u}", cx, cy),
                   "pan": ("1.1", f"(iw-iw/zoom)*{u}", cy), "panl": ("1.1", f"(iw-iw/zoom)*(1-{u})", cy),
                   "up": ("1.1", cx, f"(ih-ih/zoom)*(1-{u})"), "down": ("1.1", cx, f"(ih-ih/zoom)*{u}"),
                   "hold": ("1.04", cx, cy)}.get(kind, (f"1+0.12*{u}", cx, cy))
        _ff(["-loop", "1", "-i", str(src), "-vf", f"scale={W * 2}:{H * 2}:force_original_aspect_ratio=increase,crop={W * 2}:{H * 2},"
             f"zoompan=z='{z}':x='{x}':y='{y}':d={n}:s={W}x{H}:fps={fps},format=yuv420p",
             "-frames:v", str(n), "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", str(out)])
        return out.read_bytes()


# ---------- sound ----------
def sfx(shot: dict, clip: bytes, seconds: float, tag: str, s: dict | None = None) -> tuple[bytes | None, dict]:
    if choice(s, "sfx")[0] == "off":
        return None, {"model": None, "fallback": False, "note": "sound effects off (your choice)"}
    if not shot.get("sfx") or not _ready("hunyuan-foley"):
        return None, {"model": None, "fallback": bool(shot.get("sfx")), "note": "no sound-effects model ready" if shot.get("sfx") else ""}
    data = models.run_model("hunyuan-foley", task="sound", want="audio", prompt=shot["sfx"], seconds=seconds,
                            inputs={"video": clip}, timeout=900, tag=tag)
    return data, {"model": "hunyuan-foley", "fallback": False}


def music(s: dict, cue: str, seconds: float, tag: str) -> tuple[bytes | None, dict]:
    """The part's score: your theme, else ACE-Step from the sound designer's cue (instrumental)."""
    theme = (s.get("music") or {}).get("theme")
    if theme:
        p = Path(store_path(s, theme))
        if p.is_file():
            return to_wav(p.read_bytes()), {"model": "your theme", "fallback": False}
    if choice(s, "music")[0] == "off":
        return None, {"model": None, "fallback": False, "note": "music off (your choice)"}
    if (s.get("music") or {}).get("off") or not _ready("ace-step"):
        return None, {"model": None, "fallback": not (s.get("music") or {}).get("off"), "note": "no music model ready"}
    prompt = (f"{cue}. Instrumental score for an animated film, no vocals; a clear melodic hook with a steady groove, "
              f"quiet and sparse in the mid-range so spoken dialogue stays clear, dynamic build with a short natural ending; clean professional mix.")
    data = models.run_model("ace-step", task="music", want="audio", prompt=prompt, seconds=min(240.0, max(20.0, seconds)),
                            options={"lyrics": "[instrumental]"}, timeout=900, tag=tag)
    return data, {"model": "ace-step", "fallback": False, "prompt": prompt}


def ambience(clip: bytes, text: str, seconds: float, tag: str, s: dict | None = None) -> tuple[bytes | None, dict]:
    """A scene's room tone (HunyuanVideo-Foley on the scene's opening clip); looped quietly under the whole scene."""
    if choice(s, "sfx")[0] == "off":
        return None, {"model": None, "fallback": False, "note": "sound off (your choice)"}
    if not text or not _ready("hunyuan-foley"):
        return None, {"model": None, "fallback": bool(text), "note": "no sound-effects model ready" if text else ""}
    data = models.run_model("hunyuan-foley", task="sound", want="audio", prompt=f"ambience only, no voices: {text}",
                            seconds=seconds, inputs={"video": clip}, timeout=900, tag=tag)
    return data, {"model": "hunyuan-foley", "fallback": False, "prompt": text}


def strip(clip: Path, out: Path, seconds: float) -> Path:
    """Start, middle and end frames side by side (what shot QA looks at for motion)."""
    t = [0.05, max(0.1, seconds / 2), max(0.1, seconds - 0.15)]
    ins: list[str] = []
    for x in t:
        ins += ["-ss", f"{x:.2f}", "-i", str(clip)]
    _ff([*ins, "-filter_complex", "[0:v]scale=-2:360[a];[1:v]scale=-2:360[b];[2:v]scale=-2:360[c];[a][b][c]hstack=inputs=3",
         "-frames:v", "1", str(out)])
    return out


# ---------- small audio / ffmpeg helpers ----------
def _ff(args: list[str], timeout: float = 900) -> None:
    r = subprocess.run([config.ffmpeg(), "-y", "-loglevel", "error", *args], capture_output=True, text=True, timeout=timeout)
    if r.returncode:
        raise RuntimeError(r.stderr[-500:])


def probe_seconds(p: Path) -> float:
    r = subprocess.run([config.ffprobe(), "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
                       capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def to_wav(data: bytes) -> bytes:
    """Any audio → 24 kHz mono WAV."""
    if data[:4] == b"RIFF" and data[8:12] == b"WAVE":
        try:
            with wave.open(io.BytesIO(data)) as w:
                if w.getnchannels() == 1 and w.getframerate() == 24000:
                    return data
        except wave.Error:
            pass
    with tempfile.TemporaryDirectory() as t:
        src, out = Path(t) / "in.bin", Path(t) / "out.wav"
        src.write_bytes(data)
        _ff(["-i", str(src), "-ac", "1", "-ar", "24000", str(out)])
        return out.read_bytes()


def silence(seconds: float, rate: int = 24000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x00\x00" * max(1, int(seconds * rate)))
    return buf.getvalue()


def wav_seconds(data: bytes) -> float:
    try:
        with wave.open(io.BytesIO(data)) as w:
            return w.getnframes() / float(w.getframerate())
    except (wave.Error, EOFError):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / "a.bin"
            p.write_bytes(data)
            return probe_seconds(p)


def wav_rms(data: bytes) -> float:
    try:
        with wave.open(io.BytesIO(data)) as w:
            if w.getsampwidth() != 2:
                return 1.0
            raw = w.readframes(w.getnframes())
    except (wave.Error, EOFError):
        return 1.0
    n = len(raw) // 2
    if not n:
        return 0.0
    step = max(1, n // 20000)
    vals = struct.unpack(f"<{n}h", raw[: n * 2])[::step]
    return math.sqrt(sum(v * v for v in vals) / len(vals)) / 32768.0
