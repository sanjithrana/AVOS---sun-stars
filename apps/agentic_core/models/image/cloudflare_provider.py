import base64
import os

import httpx

from agentic_core.models.image.base import ImageProvider


class CloudflareImageProvider(ImageProvider):
    """
    Cloudflare Workers AI (developers.cloudflare.com/workers-ai) - a
    real, renewing free daily allowance (10,000 "neurons"/day on the
    free Workers plan, no credit card for that free allocation), unlike
    every hosted image API researched for the Week 3 Day 16 follow-up
    request (Stability AI, Replicate, Leonardo.ai, Fal.ai, Clipdrop -
    every one of those is pay-per-use or a one-time trial credit that
    never renews, not a free tier).

    Uses FLUX.1 [schnell] (``@cf/black-forest-labs/flux-1-schnell``),
    the cheapest model on the platform (~4.8 neurons per 512x512 tile),
    so 10,000 neurons/day is roughly 2,000 images - comfortable
    headroom for a fallback-chain slot behind Pollinations (see
    agentic_core.models.image.chain).

    Needs a free Cloudflare account: an Account ID (dashboard sidebar)
    and an API Token (My Profile -> API Tokens -> the "Workers AI"
    template is enough scope). No card is required for this specific
    free allocation as of the research behind this feature; Cloudflare's
    own signup flow is the source of truth if that ever changes.

    The plain REST API (not the Workers-binding SDK) is used here, same
    shape as every other provider in this package: one HTTP call, no
    new runtime dependency.
    """

    name = "cloudflare"

    def __init__(
        self,
        account_id: str,
        api_token: str,
        model: str = "@cf/black-forest-labs/flux-1-schnell",
        timeout: float = 60.0,
    ) -> None:
        self.account_id = account_id
        self.api_token = api_token
        self.model = model
        self.timeout = timeout

    async def generate(
        self,
        prompt: str,
        *,
        width: int = 512,
        height: int = 512,
        seed: int | None = None,
    ) -> bytes:
        # flux-1-schnell's REST body only takes prompt/steps (no
        # width/height - it generates at a fixed resolution), so those
        # two parameters are accepted for interface parity with the
        # other providers but intentionally not sent.
        url = (
            f"https://api.cloudflare.com/client/v4/accounts/{self.account_id}"
            f"/ai/run/{self.model}"
        )
        body: dict[str, object] = {"prompt": prompt, "steps": 4}
        # flux-1-schnell rejects a "seed" field outright ("Additional or
        # unevaluated properties '/seed' not allowed"), so seed is only sent
        # to models that accept it. Set CLOUDFLARE_IMAGE_SEED=1 for those.
        if seed is not None and os.getenv("CLOUDFLARE_IMAGE_SEED", "") == "1":
            body["seed"] = int(seed) % 2_147_483_647  # the API rejects 64-bit seeds

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(
                    url,
                    headers={"Authorization": f"Bearer {self.api_token}"},
                    json=body,
                )
            except httpx.ConnectError as exc:
                raise RuntimeError("Could not reach Cloudflare Workers AI.") from exc

        if response.status_code >= 400:
            try:
                errors = response.json().get("errors") or []
                detail = errors[0].get("message") if errors else response.text[:200]
            except ValueError:
                detail = response.text[:200]
            hint = " Check CLOUDFLARE_ACCOUNT_ID / CLOUDFLARE_API_TOKEN." if response.status_code in (401, 403) else ""
            raise RuntimeError(f"Cloudflare Workers AI error {response.status_code}: {detail}.{hint}")

        content_type = response.headers.get("content-type", "")
        if content_type.startswith("image/"):
            # Some Workers AI models respond with raw image bytes
            # rather than the usual JSON envelope.
            return response.content

        data = response.json()
        if data.get("success") is False:
            errors = data.get("errors") or [{"message": "unknown error"}]
            raise RuntimeError(f"Cloudflare Workers AI error: {errors[0].get('message')}")

        result = data.get("result", data)
        image_b64 = result.get("image")
        if not image_b64:
            raise RuntimeError("Cloudflare Workers AI returned no image data.")
        return base64.b64decode(image_b64)
