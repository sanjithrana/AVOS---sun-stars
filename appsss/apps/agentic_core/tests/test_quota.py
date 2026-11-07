"""
agentic_core.models.quota - the daily-count tracker behind the image
provider fallback chain. Runs against whatever REDIS_URL points to in
this environment (a real Redis, matching how the rest of the stack
tests against real infra); the in-memory fallback path is exercised
separately by forcing Redis to be unreachable.
"""

import uuid

import pytest

from agentic_core.models import quota


def _namespace() -> str:
    # A fresh, random namespace per test so tests never collide on the
    # same Redis key even when run in the same UTC day.
    return f"test-{uuid.uuid4().hex[:8]}"


@pytest.mark.asyncio
async def test_usage_starts_at_zero():
    ns = _namespace()
    assert await quota.get_usage(ns, "providerA") == 0


@pytest.mark.asyncio
async def test_increment_usage_increases_and_persists():
    ns = _namespace()
    assert await quota.increment_usage(ns, "providerA") == 1
    assert await quota.increment_usage(ns, "providerA") == 2
    assert await quota.get_usage(ns, "providerA") == 2


@pytest.mark.asyncio
async def test_usage_is_isolated_per_provider():
    ns = _namespace()
    await quota.increment_usage(ns, "providerA")
    await quota.increment_usage(ns, "providerA")
    await quota.increment_usage(ns, "providerB")

    assert await quota.get_usage(ns, "providerA") == 2
    assert await quota.get_usage(ns, "providerB") == 1


@pytest.mark.asyncio
async def test_usage_is_isolated_per_namespace():
    provider = "shared-provider-name"
    ns1, ns2 = _namespace(), _namespace()
    await quota.increment_usage(ns1, provider)

    assert await quota.get_usage(ns1, provider) == 1
    assert await quota.get_usage(ns2, provider) == 0


@pytest.mark.asyncio
async def test_falls_back_to_in_memory_counting_when_redis_is_unreachable(monkeypatch):
    async def broken_client():
        raise ConnectionError("Redis unreachable (simulated)")

    monkeypatch.setattr(quota, "_redis_client", broken_client)
    ns = _namespace()

    assert await quota.get_usage(ns, "providerA") == 0
    assert await quota.increment_usage(ns, "providerA") == 1
    assert await quota.increment_usage(ns, "providerA") == 2
    assert await quota.get_usage(ns, "providerA") == 2
