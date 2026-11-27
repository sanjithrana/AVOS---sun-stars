"""
Fallback chain across multiple image providers, each with its own daily
limit (Week 3 Day 16 follow-up: "if one daily limit is over, use
another one"). Two kinds of member:

  - free_member(provider, daily_request_limit=None) - gated by a count
    of calls today (agentic_core.models.quota); daily_request_limit=None
    means "no renewing quota to track" (e.g. Pollinations, which
    publishes no daily cap, only per-IP rate limiting) - such a
    provider is always eligible on the quota check, so a failure is the
    only thing that moves the chain on.
  - paid_member(provider, cost_per_call_usd, daily_spend_cap_usd) - a
    real, billed API (Replicate, Stability AI, etc.), gated instead by
    a shared dollar spend cap for the whole paid tier (not per-provider
    - the point is "never spend more than $X/day total", not "$X/day
    per vendor"). Added ONLY as a last resort after every free member
    has been tried, per the explicit ask: a hard cap so a paid fallback
    can never run away into a surprise bill.

Providers are tried in order regardless of kind; one over its limit
(request count or spend) is skipped without being called, and one that
raises is skipped in favor of the next. This is what turns "several
separately-free (or cheap) APIs" into one image backend that doesn't go
down or run out for the rest of the day.
"""

import logging
from dataclasses import dataclass

from agentic_core.models.image.base import ImageProvider
from agentic_core.models.quota import add_spend, get_spend, get_usage, increment_usage

logger = logging.getLogger(__name__)

QUOTA_NAMESPACE = "image"
# Every paid member shares this one counter, so the spend cap is a real
# total-dollars-per-day ceiling across all paid providers combined, not
# a separate allowance per vendor.
PAID_SPEND_KEY = "paid_total"


@dataclass(frozen=True)
class ChainMember:
    provider: ImageProvider
    daily_request_limit: int | None = None
    cost_per_call_usd: float | None = None
    daily_spend_cap_usd: float | None = None

    @property
    def is_paid(self) -> bool:
        return self.cost_per_call_usd is not None


def free_member(provider: ImageProvider, daily_request_limit: int | None = None) -> ChainMember:
    return ChainMember(provider, daily_request_limit=daily_request_limit)


def paid_member(provider: ImageProvider, *, cost_per_call_usd: float, daily_spend_cap_usd: float) -> ChainMember:
    return ChainMember(
        provider,
        cost_per_call_usd=cost_per_call_usd,
        daily_spend_cap_usd=daily_spend_cap_usd,
    )


class ImageProviderChain(ImageProvider):
    name = "chain"

    def __init__(self, members: list[ChainMember]) -> None:
        if not members:
            raise ValueError("ImageProviderChain needs at least one provider.")
        self.members = members

    async def generate(
        self,
        prompt: str,
        *,
        width: int = 512,
        height: int = 512,
        seed: int | None = None,
    ) -> bytes:
        last_exc: Exception | None = None

        for member in self.members:
            provider = member.provider

            if member.is_paid:
                spent = await get_spend(QUOTA_NAMESPACE, PAID_SPEND_KEY)
                if spent + member.cost_per_call_usd > member.daily_spend_cap_usd:
                    logger.info(
                        "Image chain: skipping paid provider '%s' - would exceed today's "
                        "$%.2f spend cap (spent $%.4f, this call ~$%.4f).",
                        provider.name, member.daily_spend_cap_usd, spent, member.cost_per_call_usd,
                    )
                    continue
            elif member.daily_request_limit is not None:
                used = await get_usage(QUOTA_NAMESPACE, provider.name)
                if used >= member.daily_request_limit:
                    logger.info(
                        "Image chain: skipping '%s' - daily quota used (%d/%d).",
                        provider.name, used, member.daily_request_limit,
                    )
                    continue

            try:
                result = await provider.generate(prompt, width=width, height=height, seed=seed)
            except Exception as exc:  # noqa: BLE001 - any provider failure falls through to the next
                logger.warning("Image chain: '%s' failed (%s), trying the next provider.", provider.name, exc)
                last_exc = exc
                continue

            if member.is_paid:
                await add_spend(QUOTA_NAMESPACE, PAID_SPEND_KEY, member.cost_per_call_usd)
                logger.info("Image chain: used paid provider '%s' (~$%.4f).", provider.name, member.cost_per_call_usd)
            elif member.daily_request_limit is not None:
                await increment_usage(QUOTA_NAMESPACE, provider.name)

            return result

        raise RuntimeError(
            "Image chain: every configured provider is over its daily quota/spend cap or failed."
        ) from last_exc
