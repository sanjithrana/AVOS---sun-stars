"""Test one API key or local address from Settings: is it accepted, and is the service reachable?

Each check is one free, read-only request (list models, who am I, verify token). Nothing is generated and nothing costs
credits. The key is read from the process environment after settings_store.apply(), so the test uses exactly what the
studio will use: the value saved in Settings, otherwise apps/.env."""
from __future__ import annotations

import os
import time
from typing import Any, Callable

import httpx

Check = Callable[[str], tuple[str, str, dict[str, str]]]


def _bearer(url: str) -> Check:
    return lambda v: ("GET", url, {"Authorization": f"Bearer {v}"})


CHECKS: dict[str, Check] = {
    "OPENAI_API_KEY": _bearer("https://api.openai.com/v1/models"),
    "GROQ_API_KEY": _bearer("https://api.groq.com/openai/v1/models"),
    "OPENROUTER_API_KEY": _bearer("https://openrouter.ai/api/v1/key"),
    "REPLICATE_API_TOKEN": _bearer("https://api.replicate.com/v1/account"),
    "STABILITY_API_KEY": _bearer("https://api.stability.ai/v1/user/account"),
    "CLOUDFLARE_API_TOKEN": _bearer("https://api.cloudflare.com/client/v4/user/tokens/verify"),
    "HF_TOKEN": _bearer("https://huggingface.co/api/whoami-v2"),
    "GEMINI_API_KEY": lambda v: ("GET", f"https://generativelanguage.googleapis.com/v1beta/models?key={v}", {}),
    "ANTHROPIC_API_KEY": lambda v: ("GET", "https://api.anthropic.com/v1/models", {"x-api-key": v, "anthropic-version": "2023-06-01"}),
    # fal.ai has no "who am I" call: ask for the status of a request that does not exist. A bad key gets 401/403,
    # a good one gets past the key check (404 or 422). Nothing is queued.
    "FAL_KEY": lambda v: ("GET", "https://queue.fal.run/fal-ai/flux/dev/requests/00000000-0000-0000-0000-000000000000/status", {"Authorization": f"Key {v}"}),
}
LOCAL: dict[str, str] = {
    "OLLAMA_BASE_URL": "/api/tags",
    "LLAMACPP_URL": "/v1/models",
    "IMAGE_SERVICE_URL": "/sdapi/v1/sd-models",
    "COMFYUI_URL": "/system_stats",
}
NAMES = {"OPENAI_API_KEY": "OpenAI", "GROQ_API_KEY": "Groq", "OPENROUTER_API_KEY": "OpenRouter", "REPLICATE_API_TOKEN": "Replicate",
         "STABILITY_API_KEY": "Stability AI", "CLOUDFLARE_API_TOKEN": "Cloudflare", "HF_TOKEN": "Hugging Face", "GEMINI_API_KEY": "Google Gemini",
         "ANTHROPIC_API_KEY": "Anthropic", "FAL_KEY": "fal.ai"}


def testable(name: str) -> bool:
    return name in CHECKS or name in LOCAL or name == "OLLAMA_MODEL"


def _ollama_url() -> str:
    return (os.getenv("OLLAMA_BASE_URL") or "http://localhost:11434").rstrip("/")


async def check(name: str, client: httpx.AsyncClient | None = None) -> dict[str, Any]:
    """{"ok": bool, "detail": str, "ms": int}. Never raises."""
    name = name.strip().upper()
    if not testable(name):
        return {"ok": False, "detail": "There is no automatic test for this one. Use it in a run to check it.", "ms": 0}
    value = (os.getenv(name) or "").strip()
    if name == "OLLAMA_MODEL":
        value = value or "(not set)"
    elif not value:
        return {"ok": False, "detail": "Nothing saved yet. Paste it and press Save first.", "ms": 0}
    own = client is None
    c = client or httpx.AsyncClient(timeout=10, follow_redirects=True)
    t0 = time.monotonic()
    try:
        if name in LOCAL or name == "OLLAMA_MODEL":
            base = _ollama_url() if name == "OLLAMA_MODEL" else value.rstrip("/")
            r = await c.get(base + LOCAL.get(name, "/api/tags"))
            ms = int((time.monotonic() - t0) * 1000)
            if r.status_code != 200:
                return {"ok": False, "detail": f"{base} answered {r.status_code}. Is it the right address?", "ms": ms}
            if name in ("OLLAMA_BASE_URL", "OLLAMA_MODEL"):
                models = [m.get("name", "") for m in (r.json().get("models") or [])]
                if name == "OLLAMA_MODEL":
                    want = os.getenv("OLLAMA_MODEL") or ""
                    if not want:
                        return {"ok": False, "detail": "No model name saved yet.", "ms": ms}
                    hit = any(m == want or m.split(":")[0] == want.split(":")[0] for m in models)
                    return {"ok": hit, "detail": f"{want} is downloaded and ready." if hit else f"{want} is not downloaded. Run: ollama pull {want}", "ms": ms}
                return {"ok": True, "detail": f"Ollama is running with {len(models)} model{'s' if len(models) != 1 else ''}" + (f": {', '.join(models[:4])}" if models else ". Download one: ollama pull qwen2.5:7b"), "ms": ms}
            return {"ok": True, "detail": f"Reachable at {base}.", "ms": ms}
        method, url, headers = CHECKS[name](value)
        r = await c.request(method, url, headers=headers)
        ms = int((time.monotonic() - t0) * 1000)
        who = NAMES.get(name, name)
        if r.status_code in (401, 403):
            return {"ok": False, "detail": f"{who} refused this key ({r.status_code}). Copy it again from the provider's page.", "ms": ms}
        if r.status_code == 429:
            return {"ok": True, "detail": f"{who} accepted the key but says you are over the rate limit right now.", "ms": ms}
        if r.status_code == 402:
            return {"ok": False, "detail": f"{who} accepted the key but the account has no credit.", "ms": ms}
        if name == "FAL_KEY" and r.status_code in (200, 400, 404, 422):
            return {"ok": True, "detail": "fal.ai accepted the key.", "ms": ms}
        if name == "CLOUDFLARE_API_TOKEN" and r.status_code == 200:
            st = ((r.json() or {}).get("result") or {}).get("status")
            return {"ok": st == "active", "detail": "Cloudflare token is active." if st == "active" else f"Cloudflare says the token is {st or 'not active'}.", "ms": ms}
        if r.status_code == 200:
            return {"ok": True, "detail": f"{who} accepted the key.", "ms": ms}
        if r.status_code == 400 and name == "GEMINI_API_KEY":
            return {"ok": False, "detail": "Google says this key is not valid.", "ms": ms}
        return {"ok": False, "detail": f"{who} answered {r.status_code}. Try again in a minute.", "ms": ms}
    except httpx.HTTPError as e:
        return {"ok": False, "detail": f"Could not reach the service ({type(e).__name__}). Check the internet connection or the address.", "ms": int((time.monotonic() - t0) * 1000)}
    except ValueError:
        return {"ok": False, "detail": "The service answered something unexpected.", "ms": int((time.monotonic() - t0) * 1000)}
    finally:
        if own:
            await c.aclose()
