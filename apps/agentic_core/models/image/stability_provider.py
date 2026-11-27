import httpx

from agentic_core.models.image.base import ImageProvider


class StabilityImageProvider(ImageProvider):
    """
    Stability AI's Stable Image API (platform.stability.ai) - a paid,
    credit-based API (new accounts get a one-time free credit grant,
    but it is NOT a renewing free tier). Wired in only as a last-resort
    paid fallback (Week 3 Day 16 follow-up) behind agentic_core.models.
    image.chain's free tier, gated by a hard daily spend cap - see
    ``paid_member`` in that module.

    Uses the "core" tier (``/v2beta/stable-image/generate/core``), the
    cheapest of Stability's image endpoints. ``Accept: image/*`` makes
    the response raw image bytes directly rather than a JSON+base64
    envelope.

    Cost: "core" is billed in Stability credits (roughly $0.03/image at
    the time this was written, credits purchased in bulk) - approximate,
    not fetched live from Stability's billing API, so treat the
    ``cost_per_call_usd`` passed to the chain as an estimate and check
    your actual usage on platform.stability.ai occasionally.
    """

    name = "stability"

    def __init__(
        self,
        api_key: str,
        timeout: float = 60.0,
    ) -> None:
        self.api_key = api_key
        self.timeout = timeout

    async def generate(
        self,
        prompt: str,
        *,
        width: int = 512,
        height: int = 512,
        seed: int | None = None,
    ) -> bytes:
        # "core" doesn't take width/height directly - aspect_ratio only
        # (a fixed set of ratios) - so those two are accepted for
        # interface parity with the other providers but not sent as-is.
        url = "https://api.stability.ai/v2beta/stable-image/generate/core"
        form: dict[str, str] = {"prompt": prompt, "output_format": "png"}
        if seed is not None:
            form["seed"] = str(seed)

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(
                    url,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Accept": "image/*",
                    },
                    data=form,
                )
            except httpx.ConnectError as exc:
                raise RuntimeError("Could not reach Stability AI.") from exc

        if response.status_code != 200:
            # Errors come back as JSON even with Accept: image/* set.
            try:
                detail = response.json().get("errors", [response.text])
            except ValueError:
                detail = [response.text]
            raise RuntimeError(f"Stability AI error ({response.status_code}): {detail}")

        return response.content
