"""
Daily request quotas for free-tier providers whose free allowance
renews every 24h (Cloudflare Workers AI's 10,000 neurons/day, etc.) -
shared by the provider fallback chains (agentic_core.models.image.chain,
and any future video equivalent) so a provider that's used up today's
free quota is skipped in favor of the next one in the chain, rather
than erroring out or silently spilling over into a billed tier.

Backed by Redis (already a required service in this stack - see
api/src/core/events/event_bus.py's ADR) so the count survives an
api/worker restart and is shared across every process hitting the same
provider. Redis is a "life is easier with it" choice here, not a hard
dependency: if it's unreachable, this degrades to a process-local,
in-memory count (silently, the same best-effort philosophy as
EventBus.publish) rather than blocking every generation call - a
single-process undercount is a far smaller problem than the whole
fallback chain failing because Redis had a bad moment.
"""

import logging
import os
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

_KEY_PREFIX = "avos:quota"
_SECONDS_PER_DAY = 86400
_memory_counts: dict[str, int] = {}


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _key(namespace: str, provider: str) -> str:
    return f"{_KEY_PREFIX}:{namespace}:{provider}:{_today()}"


async def _redis_client():
    import redis.asyncio as redis  # local import: keep agentic_core usable without redis installed

    return redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))


async def get_usage(namespace: str, provider: str) -> int:
    """How many calls this provider has already made today."""
    key = _key(namespace, provider)
    try:
        client = await _redis_client()
        try:
            value = await client.get(key)
            return int(value) if value is not None else 0
        finally:
            await client.aclose()
    except Exception:  # noqa: BLE001 - Redis being down must not block generation
        logger.debug("Quota: Redis unreachable, reading in-memory count for %s", key)
        return _memory_counts.get(key, 0)


async def increment_usage(namespace: str, provider: str) -> int:
    """Record one more call for this provider today; returns the new count."""
    key = _key(namespace, provider)
    try:
        client = await _redis_client()
        try:
            pipe = client.pipeline()
            pipe.incr(key)
            # 2 days, not 1: cheap to let a key linger a bit past
            # midnight UTC rather than risk trimming it before a
            # request that started just before the boundary reads it.
            pipe.expire(key, _SECONDS_PER_DAY * 2)
            results = await pipe.execute()
            return int(results[0])
        finally:
            await client.aclose()
    except Exception:  # noqa: BLE001 - Redis being down must not block generation
        logger.debug("Quota: Redis unreachable, using in-memory count for %s", key)
        _memory_counts[key] = _memory_counts.get(key, 0) + 1
        return _memory_counts[key]


# -- Dollar spend tracking (paid fallback tiers) -----------------------------
#
# Same shape as the request-count functions above, but for a running
# USD total rather than a call count - what a paid-provider spend cap
# (agentic_core.models.image.chain's paid_member) checks against before
# ever making a billed call.

_memory_spend: dict[str, float] = {}


def _spend_key(namespace: str, provider: str) -> str:
    return f"{_KEY_PREFIX}:spend:{namespace}:{provider}:{_today()}"


async def get_spend(namespace: str, provider: str) -> float:
    """Total USD spent on this provider (or shared spend key) today."""
    key = _spend_key(namespace, provider)
    try:
        client = await _redis_client()
        try:
            value = await client.get(key)
            return float(value) if value is not None else 0.0
        finally:
            await client.aclose()
    except Exception:  # noqa: BLE001 - Redis being down must not block generation
        logger.debug("Quota: Redis unreachable, reading in-memory spend for %s", key)
        return _memory_spend.get(key, 0.0)


async def add_spend(namespace: str, provider: str, amount_usd: float) -> float:
    """Record ``amount_usd`` more spend today; returns the new running total."""
    key = _spend_key(namespace, provider)
    try:
        client = await _redis_client()
        try:
            pipe = client.pipeline()
            pipe.incrbyfloat(key, amount_usd)
            pipe.expire(key, _SECONDS_PER_DAY * 2)
            results = await pipe.execute()
            return float(results[0])
        finally:
            await client.aclose()
    except Exception:  # noqa: BLE001 - Redis being down must not block generation
        logger.debug("Quota: Redis unreachable, using in-memory spend for %s", key)
        _memory_spend[key] = _memory_spend.get(key, 0.0) + amount_usd
        return _memory_spend[key]
