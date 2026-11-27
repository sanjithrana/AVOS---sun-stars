import httpx

from agentic_core.models.image.base import ImageProvider


class ReplicateImageProvider(ImageProvider):
    """
    Replicate (replicate.com) - a paid, pay-per-use hosted-model API,
    NOT a free tier. Wired in only as a last-resort paid fallback (Week
    3 Day 16 follow-up) behind agentic_core.models.image.chain's free
    tier, gated by a hard daily spend cap so it can never run away into
    a surprise bill - see ``paid_member`` in that module.

    Runs FLUX.1 [schnell] (``black-forest-labs/flux-schnell``) via the
    "official model" prediction endpoint, which doesn't need a version
    hash pinned. ``Prefer: wait`` makes the call synchronous (blocks up
    to ~60s for the result) instead of returning immediately and
    needing separate polling.

    Cost: roughly $0.003/image at the time this was written (Replicate
    bills per second of GPU time, this model is fast) - approximate,
    not fetched live from Replicate's billing API, so treat the
    ``cost_per_call_usd`` passed to the chain as an estimate and check
    your actual usage on replicate.com/account/billing occasionally.
    """

    name = "replicate"

    def __init__(
        self,
        api_token: str,
        model: str = "black-forest-labs/flux-schnell",
        timeout: float = 90.0,
    ) -> None:
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
        url = f"https://api.replicate.com/v1/models/{self.model}/predictions"
        model_input: dict[str, object] = {"prompt": prompt, "output_format": "png"}
        if seed is not None:
            model_input["seed"] = seed

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(
                    url,
                    headers={
                        "Authorization": f"Bearer {self.api_token}",
                        "Content-Type": "application/json",
                        "Prefer": "wait",
                    },
                    json={"input": model_input},
                )
            except httpx.ConnectError as exc:
                raise RuntimeError("Could not reach Replicate.") from exc

            response.raise_for_status()
            data = response.json()

            if data.get("status") == "failed":
                raise RuntimeError(f"Replicate prediction failed: {data.get('error')}")
            if data.get("status") != "succeeded":
                # "Prefer: wait" timed out before completion (rare for
                # schnell, possible under load) - not treated as a hard
                # failure here since it did start billing; surfaced so
                # the caller/chain falls through rather than hanging.
                raise RuntimeError(
                    f"Replicate prediction did not complete in time (status={data.get('status')})."
                )

            output = data.get("output")
            image_url = output[0] if isinstance(output, list) else output
            if not image_url:
                raise RuntimeError("Replicate returned no image output.")

            image_response = await client.get(image_url)
            image_response.raise_for_status()
            return image_response.content
