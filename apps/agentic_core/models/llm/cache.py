"""Answer cache for text models: the same request (provider, model, system, prompt, settings) within LLM_CACHE_TTL
seconds (default 1 h) gets the stored answer instead of another model call. Temporal retries, a re-run research
step or the Studio asking again then cost nothing and return at once. LLM_CACHE_TTL=0 turns it off.
In memory, per process, at most 256 answers."""
from __future__ import annotations

import hashlib
import os
import time
from collections import OrderedDict

from agentic_core.models.llm.base import LLMProvider

MAX_ENTRIES = 256
_store: "OrderedDict[str, tuple[float, str]]" = OrderedDict()


def ttl() -> float:
    try:
        return float(os.getenv("LLM_CACHE_TTL") or 3600)
    except ValueError:
        return 3600.0


def wrap(provider: LLMProvider) -> LLMProvider:
    """Give this provider instance a cached `complete` (it stays the same class, so isinstance checks hold)."""
    if getattr(provider, "_cached", False):
        return provider
    inner = provider.complete

    async def complete(prompt: str, *, system: str | None = None, max_tokens: int = 1024,
                       temperature: float = 0.7) -> str:
        life = ttl()
        if life <= 0:
            return await inner(prompt, system=system, max_tokens=max_tokens, temperature=temperature)
        key = hashlib.sha256("\x1f".join([provider.name, str(getattr(provider, "model", "")),
                                          str(getattr(provider, "base_url", "")), system or "", prompt,
                                          str(max_tokens), str(temperature)]).encode()).hexdigest()
        hit = _store.get(key)
        if hit and time.monotonic() - hit[0] < life:
            _store.move_to_end(key)
            return hit[1]
        text = await inner(prompt, system=system, max_tokens=max_tokens, temperature=temperature)
        if text:
            _store[key] = (time.monotonic(), text)
            while len(_store) > MAX_ENTRIES:
                _store.popitem(last=False)
        return text

    provider.complete = complete            # type: ignore[method-assign]
    provider._cached = True                  # type: ignore[attr-defined]
    return provider


def clear() -> None:
    _store.clear()
