"""
ImageProviderChain - Week 3 Day 16 follow-up ("if one daily limit is
over, use another one", then "add paid providers as a last-resort
fallback with a hard spend cap"). Uses fake in-process providers (no
real network) and monkeypatches agentic_core.models.quota so the
chain's skip/fallback decisions are deterministic and don't depend on a
real Redis or on the wall-clock UTC day.
"""

import pytest

from agentic_core.models.image.base import ImageProvider
from agentic_core.models.image.chain import ImageProviderChain, free_member, paid_member


class FakeProvider(ImageProvider):
    def __init__(self, name: str, *, fail: bool = False, payload: bytes = b"img-bytes"):
        self.name = name
        self.fail = fail
        self.payload = payload
        self.calls = 0

    async def generate(self, prompt, *, width=512, height=512, seed=None):
        self.calls += 1
        if self.fail:
            raise RuntimeError(f"{self.name} is down")
        return self.payload


@pytest.fixture
def fake_quota(monkeypatch):
    """In-memory quota/spend stores the test controls directly, swapped
    in for the chain's real get_usage/increment_usage/get_spend/add_spend
    calls."""
    counts: dict[tuple[str, str], int] = {}
    spend: dict[tuple[str, str], float] = {}

    async def fake_get_usage(namespace, provider):
        return counts.get((namespace, provider), 0)

    async def fake_increment_usage(namespace, provider):
        counts[(namespace, provider)] = counts.get((namespace, provider), 0) + 1
        return counts[(namespace, provider)]

    async def fake_get_spend(namespace, key):
        return spend.get((namespace, key), 0.0)

    async def fake_add_spend(namespace, key, amount):
        spend[(namespace, key)] = spend.get((namespace, key), 0.0) + amount
        return spend[(namespace, key)]

    monkeypatch.setattr("agentic_core.models.image.chain.get_usage", fake_get_usage)
    monkeypatch.setattr("agentic_core.models.image.chain.increment_usage", fake_increment_usage)
    monkeypatch.setattr("agentic_core.models.image.chain.get_spend", fake_get_spend)
    monkeypatch.setattr("agentic_core.models.image.chain.add_spend", fake_add_spend)
    return {"counts": counts, "spend": spend}


# -- free tier ---------------------------------------------------------------


@pytest.mark.asyncio
async def test_uses_the_first_provider_when_it_has_room(fake_quota):
    first = FakeProvider("first", payload=b"from-first")
    second = FakeProvider("second", payload=b"from-second")
    chain = ImageProviderChain([free_member(first, 5), free_member(second)])

    result = await chain.generate("a fox")

    assert result == b"from-first"
    assert first.calls == 1
    assert second.calls == 0


@pytest.mark.asyncio
async def test_falls_through_once_the_first_providers_daily_quota_is_used_up(fake_quota):
    first = FakeProvider("first", payload=b"from-first")
    second = FakeProvider("second", payload=b"from-second")
    chain = ImageProviderChain([free_member(first, 2), free_member(second)])

    # Use up first's quota (2/day) without calling through the chain,
    # simulating requests made earlier today.
    fake_quota["counts"][("image", "first")] = 2

    result = await chain.generate("a fox")

    assert result == b"from-second"
    assert first.calls == 0  # skipped entirely, not even attempted
    assert second.calls == 1


@pytest.mark.asyncio
async def test_falls_through_when_a_provider_raises_even_with_quota_remaining(fake_quota):
    first = FakeProvider("first", fail=True)
    second = FakeProvider("second", payload=b"from-second")
    chain = ImageProviderChain([free_member(first, 5), free_member(second)])

    result = await chain.generate("a fox")

    assert result == b"from-second"
    assert first.calls == 1  # actually attempted, then failed over


@pytest.mark.asyncio
async def test_provider_with_no_daily_limit_is_never_skipped_on_quota(fake_quota):
    unlimited = FakeProvider("unlimited", payload=b"from-unlimited")
    fake_quota["counts"][("image", "unlimited")] = 10_000  # would blow any real cap
    chain = ImageProviderChain([free_member(unlimited)])

    result = await chain.generate("a fox")

    assert result == b"from-unlimited"


@pytest.mark.asyncio
async def test_successful_call_increments_the_used_providers_quota(fake_quota):
    provider = FakeProvider("tracked")
    chain = ImageProviderChain([free_member(provider, 5)])

    await chain.generate("a fox")

    assert fake_quota["counts"][("image", "tracked")] == 1


@pytest.mark.asyncio
async def test_all_free_providers_exhausted_or_failing_falls_through_to_error(fake_quota):
    quota_exhausted = FakeProvider("exhausted")
    failing = FakeProvider("failing", fail=True)
    chain = ImageProviderChain([free_member(quota_exhausted, 0), free_member(failing)])

    with pytest.raises(RuntimeError, match="every configured provider"):
        await chain.generate("a fox")


def test_empty_chain_is_rejected_at_construction():
    with pytest.raises(ValueError, match="at least one provider"):
        ImageProviderChain([])


# -- paid tier -----------------------------------------------------------


@pytest.mark.asyncio
async def test_paid_provider_used_only_after_free_tier_fails(fake_quota):
    free = FakeProvider("free", fail=True)
    paid = FakeProvider("paid", payload=b"from-paid")
    chain = ImageProviderChain([
        free_member(free),
        paid_member(paid, cost_per_call_usd=0.01, daily_spend_cap_usd=1.00),
    ])

    result = await chain.generate("a fox")

    assert result == b"from-paid"
    assert free.calls == 1
    assert paid.calls == 1


@pytest.mark.asyncio
async def test_paid_provider_skipped_once_spend_cap_would_be_exceeded(fake_quota):
    free = FakeProvider("free", fail=True)
    paid = FakeProvider("paid", payload=b"from-paid")
    chain = ImageProviderChain([
        free_member(free),
        paid_member(paid, cost_per_call_usd=0.05, daily_spend_cap_usd=0.10),
    ])

    # Already spent $0.08 today - one more $0.05 call would total $0.13,
    # over the $0.10 cap, so the paid provider must be skipped.
    fake_quota["spend"][("image", "paid_total")] = 0.08

    with pytest.raises(RuntimeError, match="every configured provider"):
        await chain.generate("a fox")

    assert paid.calls == 0  # never even attempted


@pytest.mark.asyncio
async def test_successful_paid_call_adds_to_the_shared_spend_total(fake_quota):
    paid = FakeProvider("paid")
    chain = ImageProviderChain([paid_member(paid, cost_per_call_usd=0.03, daily_spend_cap_usd=1.00)])

    await chain.generate("a fox")
    await chain.generate("a fox")

    assert fake_quota["spend"][("image", "paid_total")] == pytest.approx(0.06)


@pytest.mark.asyncio
async def test_two_paid_providers_share_one_spend_cap_not_one_each(fake_quota):
    """The whole point of a shared key: provider A using most of the
    cap must stop provider B from running too, since the cap is a
    total-dollars-per-day ceiling, not a per-vendor allowance."""
    provider_a = FakeProvider("provider_a", fail=True)
    provider_b = FakeProvider("provider_b", payload=b"from-b")
    chain = ImageProviderChain([
        paid_member(provider_a, cost_per_call_usd=0.09, daily_spend_cap_usd=0.10),
        paid_member(provider_b, cost_per_call_usd=0.09, daily_spend_cap_usd=0.10),
    ])

    # provider_a is attempted (room for it: 0 + 0.09 <= 0.10) but fails
    # before ever recording spend, so provider_b is still checked
    # against the same cap and also has room - both may run in this
    # single call since provider_a's failure didn't spend anything.
    result = await chain.generate("a fox")
    assert result == b"from-b"

    # Now simulate provider_a having actually succeeded and spent its
    # share first (as a prior call would have recorded).
    fake_quota["spend"][("image", "paid_total")] = 0.09
    provider_b.fail = True
    with pytest.raises(RuntimeError):
        await chain.generate("a fox")
    assert provider_b.calls == 1  # still just the one call from before
