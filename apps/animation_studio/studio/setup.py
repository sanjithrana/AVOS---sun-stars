"""What your keys do right now, and the one key that would help most.

The Home page asks this. Each job needs four things: a writer (text AI), pictures, video and a voice. Paste one key in
Settings and it is used for what that provider is good at, with free options filling the other roles:

  - a text key (Groq, Gemini, OpenRouter, OpenAI, Anthropic) becomes the writer for every new job (llm.auto_agent)
  - a fal.ai key draws pictures and makes AI video (Seedance, Kling, Wan, LTX, FLUX ...); a GPU server or ComfyUI
    runs the open models on your own card first (models.backend_for)
  - Cloudflare Workers AI is a free picture tier; Pollinations needs no key at all

So someone who pastes only a fal.ai key (for Seedance video) is told to add a free text model too, and someone with
only a Groq key is told that video needs fal.ai or a GPU. Nothing here calls a provider: it reads which keys are saved.
"""
from __future__ import annotations

import os
from typing import Any

from . import avos_settings

TEXT = [  # (key, name, free?)
    ("GROQ_API_KEY", "Groq", True), ("GEMINI_API_KEY", "Google Gemini", True), ("OPENROUTER_API_KEY", "OpenRouter", True),
    ("OPENAI_API_KEY", "OpenAI", False), ("ANTHROPIC_API_KEY", "Anthropic", False),
]
FREE_TEXT_TIP = ("Add a free text model so the writing is sharp: a Groq key (free, no card, one minute at console.groq.com/keys) "
                 "or a Gemini key (free at aistudio.google.com/apikey). Ollama on this computer works too, with no key.")


def _has(name: str) -> bool:
    return bool((os.environ.get(name) or "").strip())


def plan() -> dict[str, Any]:
    avos_settings.apply()
    from .llm import SPEC, default_agent
    roles: list[dict[str, Any]] = []
    tips: list[dict[str, str]] = []

    # writer
    texts = [(k, n, free) for k, n, free in TEXT if _has(k)]
    picked = os.environ.get("STUDIO_DEFAULT_AGENT") or ""
    agent = default_agent()
    label = SPEC.get(agent, {}).get("label", agent)
    if agent == "ollama":
        writer = {"role": "writer", "title": "Writing", "uses": "Ollama on this computer", "ok": None,
                  "note": "Free and private, but it needs Ollama running with a model downloaded. Without it the studio falls back to its own rules."}
    else:
        writer = {"role": "writer", "title": "Writing", "uses": label, "ok": True,
                  "note": "Picked by you in Settings." if picked else "Picked automatically because you saved this key."}
    roles.append(writer)

    fal = _has("FAL_KEY")
    gpu = bool(avos_settings.workers(enabled_only=True)) or _has("COMFYUI_URL")
    cf = _has("CLOUDFLARE_ACCOUNT_ID") and _has("CLOUDFLARE_API_TOKEN")
    own = _has("IMAGE_SERVICE_URL")

    # pictures
    if gpu:
        pics = ("Your GPU server", "Open models on your own card first" + (", then fal.ai" if fal else "") + ".", True)
    elif fal:
        pics = ("fal.ai", "FLUX, Qwen-Image and more, paid per picture from your fal.ai credit.", True)
    elif cf:
        pics = ("Cloudflare Workers AI", "Free tier, then Pollinations.", True)
    elif own:
        pics = ("Your image server", os.environ.get("IMAGE_SERVICE_URL", ""), True)
    else:
        pics = ("Pollinations", "Free with no key, but slow and sometimes busy.", None)
    roles.append({"role": "pictures", "title": "Pictures", "uses": pics[0], "note": pics[1], "ok": pics[2]})

    # video
    if gpu and fal:
        vid = ("Your GPU server, then fal.ai", "Open video models on your card; Seedance, Kling and others on fal.ai when you pick them.", True)
    elif gpu:
        vid = ("Your GPU server", "Wan, LTX and other open video models on your own card.", True)
    elif fal:
        vid = ("fal.ai", "Seedance, Kling, Wan, LTX: picked per shot, paid per second from your fal.ai credit.", True)
    else:
        vid = ("Drawn motion", "No AI video yet: shots move with camera moves and the studio's own animation engines.", None)
    roles.append({"role": "video", "title": "Video", "uses": vid[0], "note": vid[1], "ok": vid[2]})

    roles.append({"role": "voice", "title": "Voice", "uses": "Edge voices", "note": "Free narration in many languages and accents.", "ok": True})

    # the advice, most useful first
    if not texts and (fal or gpu or cf):
        what = "fal.ai" if fal else "Your GPU server" if gpu else "Cloudflare"
        tips.append({"id": "free-text", "title": "Add a free text model",
                     "text": f"{what} will make the pictures"
                             + (" and video" if fal or gpu else "") + ", but nothing writes the scripts yet. " + FREE_TEXT_TIP})
    elif not texts:
        tips.append({"id": "first-key", "title": "Paste one free key for much better videos",
                     "text": "Right now everything runs on free fallbacks. " + FREE_TEXT_TIP})
    if not (fal or gpu):
        tips.append({"id": "video", "title": "Want real AI video?",
                     "text": "A fal.ai key (pay as you go) unlocks Seedance, Kling, Wan and LTX for every shot. "
                             "A GPU server runs the open ones on your own card instead."})
    if not (fal or gpu or cf or own):
        tips.append({"id": "pictures", "title": "Faster free pictures",
                     "text": "Add a free Cloudflare account ID and API token (Workers AI) so pictures stop waiting on Pollinations."})
    if texts and all(not free for _, _, free in texts):
        tips.append({"id": "cost", "title": "Save on writing",
                     "text": f"{texts[0][1]} is paid per word. A free Groq or Gemini key writes almost as well; pick it in Settings if cost matters."})

    level = "best" if texts and (fal or gpu) else "good" if texts or fal or gpu else "starter"
    return {"level": level, "roles": roles, "tips": tips[:3], "keys": {k: _has(k) for k, _, _ in TEXT} | {"FAL_KEY": fal}}
