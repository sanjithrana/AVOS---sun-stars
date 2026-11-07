"""Paid / keyed providers that just failed for a reason that won't fix itself in a second: an empty balance, a
locked account, a bad key, a used-up quota. The provider is skipped for a while so AVOS falls through to your GPU,
a free tier or the next model, and the Models page / Series panel say why. Shared by the API and the Animation Studio
through a file next to the shared settings (provider_health.json); changing the provider's key clears it.

    kind = classify(403, '{"detail":"User is locked. Reason: Exhausted balance."}')   # → "billing"
    mark("fal", kind, detail)
    down("fal")   # → "fal.ai: no credit left (User is locked. Reason: Exhausted balance). Top up at …, or …"

An identical copy lives in animation_studio/studio/provider_health.py.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import time
from pathlib import Path
from typing import Any

TTL = {"billing": 3600.0, "auth": 3600.0, "quota": 900.0}
KEYS = {"fal": "FAL_KEY", "cloudflare": "CLOUDFLARE_API_TOKEN", "replicate": "REPLICATE_API_TOKEN", "groq": "GROQ_API_KEY",
        "gemini": "GEMINI_API_KEY", "openai": "OPENAI_API_KEY", "openrouter": "OPENROUTER_API_KEY"}
NAMES = {"fal": "fal.ai", "cloudflare": "Cloudflare Workers AI", "replicate": "Replicate", "groq": "Groq", "gemini": "Gemini",
         "openai": "OpenAI", "openrouter": "OpenRouter"}
FIX = {"fal": "Top up at fal.ai/dashboard/billing or put a new key in Settings → API keys",
       "cloudflare": "Check the account id and token in Settings → API keys (the free tier resets daily)",
       "replicate": "Add credit at replicate.com/account/billing"}
_lock = threading.Lock()


def _file() -> Path:
    env = os.environ.get("AVOS_SETTINGS_FILE")
    if env:
        return Path(env).with_name("provider_health.json")
    if Path("/data/settings").is_dir():
        return Path("/data/settings/provider_health.json")
    here = Path(__file__).resolve()
    apps = next((p for p in here.parents if (p / "docker-compose.yml").is_file()), here.parents[1])
    return apps / ".avos" / "provider_health.json"


def _read() -> dict[str, Any]:
    try:
        return json.loads(_file().read_text("utf-8"))
    except (OSError, ValueError):
        return {}


def _write(d: dict[str, Any]) -> None:
    p = _file()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(d, indent=1), "utf-8")
        os.replace(tmp, p)
    except OSError:
        pass


def _key_fp(provider: str) -> str:
    k = os.environ.get(KEYS.get(provider, ""), "")
    return hashlib.sha1(k.encode()).hexdigest()[:10] if k else ""


def classify(status: int, text: str = "") -> str | None:
    t = (text or "").lower()
    if status == 402 or re.search(r"exhausted balance|insufficient (?:balance|credit|funds)|no credit|out of credit|billing|"
                                  r"payment required|user is locked", t):
        return "billing"
    if status in (401, 403):
        return "auth"
    if status == 429 and re.search(r"quota|daily|limit exceeded|neurons", t):
        return "quota"
    return None


def short(text: str) -> str:
    try:
        d = json.loads(text)
        text = d.get("detail") or d.get("error") or d.get("message") or text
        if isinstance(text, (dict, list)):
            text = json.dumps(text)
    except (ValueError, AttributeError):
        pass
    return re.sub(r"\s+", " ", str(text)).strip()[:160]


def mark(provider: str, kind: str, detail: str = "") -> str:
    with _lock:
        d = _read()
        d[provider] = {"kind": kind, "detail": short(detail), "at": time.time(), "key": _key_fp(provider)}
        _write(d)
    return message(provider, d[provider])


def message(provider: str, row: dict[str, Any]) -> str:
    name = NAMES.get(provider, provider)
    what = {"billing": "no credit left", "auth": "the key was refused", "quota": "the free quota is used up"}.get(row["kind"], row["kind"])
    fix = FIX.get(provider, "Check the key in Settings → API keys")
    return f"{name}: {what}" + (f" ({row['detail']})" if row.get("detail") else "") + f". {fix}, or use your GPU / another provider."


def down(provider: str) -> str | None:
    row = _read().get(provider)
    if not row:
        return None
    if time.time() - float(row.get("at") or 0) > TTL.get(row.get("kind"), 900.0) or row.get("key") != _key_fp(provider):
        return None
    return message(provider, row)


def clear(provider: str | None = None) -> None:
    with _lock:
        d = _read()
        if provider is None:
            d = {}
        else:
            d.pop(provider, None)
        _write(d)


def snapshot() -> dict[str, str]:
    return {p: m for p in _read() if (m := down(p))}
