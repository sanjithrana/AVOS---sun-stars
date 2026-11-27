import os

from agentic_core.models.image.base import ImageProvider
from agentic_core.models.image.chain import ImageProviderChain, free_member, paid_member
from agentic_core.models.image.cloudflare_provider import CloudflareImageProvider
from agentic_core.models.image.local_provider import LocalImageProvider
from agentic_core.models.image.pollinations_provider import PollinationsProvider
from agentic_core.models.image.replicate_provider import ReplicateImageProvider
from agentic_core.models.image.stability_provider import StabilityImageProvider

# Keep in sync with desktop/types/project.ts's IMAGE_PROVIDERS.
# "mock" isn't listed here - it isn't a real ImageProvider, it's the
# absence of one (VideoGenerationService's existing deterministic PNG
# placeholder, unchanged).
#   best / z-image / qwen-image / flux-schnell: the open models from the AVOS model catalog
#   (agentic_core/models/catalog.json), on your GPU server (ComfyUI), Cloudflare (FLUX) or fal.ai.
CATALOG_CHOICES = ("best", "z-image", "qwen-image", "flux-schnell")
KNOWN_PROVIDERS = ("free", "pollinations", "cloudflare", "local", "replicate", "stability", "chain", *CATALOG_CHOICES)

# Default cap for Cloudflare's slot in the "chain" provider: 10,000
# free neurons/day at ~4.8 neurons per flux-1-schnell image is roughly
# 2,000 images/day; capping the chain's own counter well under that
# (not exactly at it) leaves headroom for other things sharing the same
# Cloudflare account and for the neurons-per-image estimate being
# approximate. Override with CLOUDFLARE_DAILY_IMAGE_LIMIT.
DEFAULT_CLOUDFLARE_DAILY_IMAGE_LIMIT = 1500

# Replicate/Stability are PAID APIs, not free - see those providers'
# docstrings. These are rough per-image cost estimates (not fetched
# live from either vendor's billing API) used only to decide whether a
# call would exceed IMAGE_PAID_DAILY_SPEND_CAP_USD; check your actual
# bill occasionally and override via env if these drift.
DEFAULT_REPLICATE_COST_USD = 0.003
DEFAULT_STABILITY_COST_USD = 0.03
# Hard ceiling on TOTAL paid-image spend per day, shared across every
# paid provider in the chain combined (not per-vendor) - the point of
# asking for "a hard spend cap" is a real dollar ceiling, not one per
# API. Override with IMAGE_PAID_DAILY_SPEND_CAP_USD.
DEFAULT_PAID_DAILY_SPEND_CAP_USD = 0.50


def _build_pollinations() -> PollinationsProvider:
    return PollinationsProvider(
        model=os.getenv("POLLINATIONS_MODEL", "flux"),
        token=os.getenv("POLLINATIONS_TOKEN") or None,
    )


def _cloudflare_limit() -> int:
    env = os.getenv("CLOUDFLARE_DAILY_IMAGE_LIMIT")
    return int(env) if env else DEFAULT_CLOUDFLARE_DAILY_IMAGE_LIMIT


def build_free_chain() -> ImageProviderChain:
    """Free-only chain, most reliable first: Cloudflare Workers AI (a real
    free daily allowance, when configured) -> Pollinations (no key, but
    no uptime guarantee and it now refuses some anonymous requests with
    402) -> your own server (IMAGE_SERVICE_URL). Never calls a paid API.
    This is what the video providers fall back to when a project didn't
    pick an image provider."""
    members = []
    cloudflare = _build_cloudflare()
    if cloudflare is not None:
        members.append(free_member(cloudflare, daily_request_limit=_cloudflare_limit()))
    members.append(free_member(_build_pollinations()))
    local = _build_local()
    if local is not None:
        members.append(free_member(local))
    return ImageProviderChain(members)


def _build_cloudflare() -> CloudflareImageProvider | None:
    """None (not an error) when Cloudflare isn't configured - lets the
    "chain" provider skip it silently rather than every deployment
    needing a Cloudflare account just to use Pollinations."""
    account_id = os.getenv("CLOUDFLARE_ACCOUNT_ID")
    api_token = os.getenv("CLOUDFLARE_API_TOKEN")
    if not account_id or not api_token:
        return None
    return CloudflareImageProvider(
        account_id=account_id,
        api_token=api_token,
        model=os.getenv("CLOUDFLARE_IMAGE_MODEL", "@cf/black-forest-labs/flux-1-schnell"),
    )


def _build_local() -> LocalImageProvider | None:
    base_url = os.getenv("IMAGE_SERVICE_URL")
    if not base_url:
        return None
    return LocalImageProvider(base_url=base_url)


def _build_replicate() -> ReplicateImageProvider | None:
    api_token = os.getenv("REPLICATE_API_TOKEN")
    if not api_token:
        return None
    return ReplicateImageProvider(
        api_token=api_token,
        model=os.getenv("REPLICATE_IMAGE_MODEL", "black-forest-labs/flux-schnell"),
    )


def _build_stability() -> StabilityImageProvider | None:
    api_key = os.getenv("STABILITY_API_KEY")
    if not api_key:
        return None
    return StabilityImageProvider(api_key=api_key)


def get_image_provider(provider: str | None) -> ImageProvider | None:
    """
    Return the configured ImageProvider, or None to keep using the
    existing deterministic MOCK placeholder frames.

    Unlike get_llm_provider, there is no auto-detect fallback here: a
    project that never picked an image provider (the common case today)
    must keep generating byte-identical mock thumbnails, matching every
    existing test's expectations. Only an explicit choice (a project's
    saved ``image_provider``, or IMAGE_PROVIDER for a deployment-wide
    default) turns real generation on.
    """
    from agentic_core import settings_store

    settings_store.apply()
    choice = provider or os.getenv("IMAGE_PROVIDER")

    if not choice or choice == "mock":
        return None

    if settings_store.custom_model(choice) and settings_store.custom_model(choice)["task"] == "image":
        from agentic_core.models import catalog
        from agentic_core.models.custom_models import CustomImageProvider

        catalog.backend_for(choice)
        return CustomImageProvider(choice)

    if choice == "free":
        return build_free_chain()

    if choice == "best":
        from agentic_core.models.image.catalog_image import BestImageProvider

        return BestImageProvider()

    if choice in CATALOG_CHOICES:
        from agentic_core.models import catalog
        from agentic_core.models.image.catalog_image import CatalogImageProvider

        catalog.backend_for(choice)  # raises ModelUnavailable (a ValueError) saying how to set it up
        return CatalogImageProvider(choice)

    if choice == "pollinations":
        return _build_pollinations()

    if choice == "cloudflare":
        cloudflare = _build_cloudflare()
        if cloudflare is None:
            raise ValueError(
                "Image provider 'cloudflare' selected but CLOUDFLARE_ACCOUNT_ID/"
                "CLOUDFLARE_API_TOKEN are not set."
            )
        return cloudflare

    if choice == "local":
        local = _build_local()
        if local is None:
            raise ValueError("Image provider 'local' selected but IMAGE_SERVICE_URL is not set.")
        return local

    if choice == "replicate":
        replicate = _build_replicate()
        if replicate is None:
            raise ValueError("Image provider 'replicate' selected but REPLICATE_API_TOKEN is not set.")
        return replicate

    if choice == "stability":
        stability = _build_stability()
        if stability is None:
            raise ValueError("Image provider 'stability' selected but STABILITY_API_KEY is not set.")
        return stability

    if choice == "chain":
        # Free tier, tried first, in order: Pollinations (no key, no
        # formal daily cap - the zero-setup default) -> Cloudflare
        # Workers AI (a real ~2,000/day free allowance, needs an
        # account) -> self-hosted (unlimited, needs your own server).
        # Only members that are actually configured are included -
        # Pollinations always is, so "chain" always has at least one
        # provider even with nothing else set up.
        cloudflare_limit_env = os.getenv("CLOUDFLARE_DAILY_IMAGE_LIMIT")
        cloudflare_limit = (
            int(cloudflare_limit_env) if cloudflare_limit_env else DEFAULT_CLOUDFLARE_DAILY_IMAGE_LIMIT
        )

        members = [free_member(_build_pollinations())]
        cloudflare = _build_cloudflare()
        if cloudflare is not None:
            members.append(free_member(cloudflare, daily_request_limit=cloudflare_limit))
        local = _build_local()
        if local is not None:
            members.append(free_member(local))

        # Paid tier, ONLY as a last resort after every free member
        # above, gated by one shared daily spend cap across both paid
        # providers combined (see chain.py's PAID_SPEND_KEY) - added
        # only when their API keys are actually configured, so a
        # deployment with no paid keys set behaves exactly like the
        # free-only chain from before this tier existed.
        spend_cap_env = os.getenv("IMAGE_PAID_DAILY_SPEND_CAP_USD")
        spend_cap = float(spend_cap_env) if spend_cap_env else DEFAULT_PAID_DAILY_SPEND_CAP_USD

        replicate = _build_replicate()
        if replicate is not None:
            cost_env = os.getenv("REPLICATE_IMAGE_COST_USD")
            cost = float(cost_env) if cost_env else DEFAULT_REPLICATE_COST_USD
            members.append(paid_member(replicate, cost_per_call_usd=cost, daily_spend_cap_usd=spend_cap))

        stability = _build_stability()
        if stability is not None:
            cost_env = os.getenv("STABILITY_IMAGE_COST_USD")
            cost = float(cost_env) if cost_env else DEFAULT_STABILITY_COST_USD
            members.append(paid_member(stability, cost_per_call_usd=cost, daily_spend_cap_usd=spend_cap))

        return ImageProviderChain(members)

    raise ValueError(f"Unknown image provider '{choice}'. Known providers: {KNOWN_PROVIDERS} or an image model added in Settings.")
