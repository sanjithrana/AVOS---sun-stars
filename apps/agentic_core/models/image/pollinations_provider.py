import asyncio
from urllib.parse import quote

import httpx

from agentic_core.models.image.base import ImageProvider


class PollinationsProvider(ImageProvider):
    """
    pollinations.ai's original no-key, no-signup endpoint
    (``image.pollinations.ai/prompt/...``) - genuinely free (not a
    trial): no account, no card, no expiring credits. It's rate-limited
    per IP (roughly one image per several seconds) and carries no
    uptime guarantee, which is the honest tradeoff for "actually free"
    rather than "free until the trial credits run out". In practice
    this means an occasional transient 5xx/timeout even when nothing is
    misconfigured - retried a couple of times below before giving up,
    rather than surfacing a one-off blip as a hard error.

    Note this is a *different, older* Pollinations endpoint from the
    newer key-gated ``gen.pollinations.ai`` "Pollen credits" API - this
    one deliberately stays on the endpoint that needs no key at all.
    """

    name = "pollinations"

    def __init__(
        self,
        base_url: str = "https://image.pollinations.ai",
        model: str = "flux",
        timeout: float = 60.0,
        max_attempts: int = 3,
        retry_backoff_seconds: float = 2.0,
        token: str | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.max_attempts = max_attempts
        self.retry_backoff_seconds = retry_backoff_seconds
        # Optional: a Pollinations account token (POLLINATIONS_TOKEN) for
        # when the anonymous tier refuses a request.
        self.token = token

    async def generate(
        self,
        prompt: str,
        *,
        width: int = 512,
        height: int = 512,
        seed: int | None = None,
    ) -> bytes:
        url = f"{self.base_url}/prompt/{quote(prompt)}"
        params = {
            "width": width,
            "height": height,
            "model": self.model,
            "nologo": "true",
        }
        if seed is not None:
            params["seed"] = seed

        headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        last_exc: Exception | None = None
        for attempt in range(1, self.max_attempts + 1):
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                try:
                    response = await client.get(url, params=params, headers=headers)
                except (httpx.ConnectError, httpx.TimeoutException) as exc:
                    last_exc = exc
                else:
                    if response.status_code in (401, 402, 403):
                        # Not a blip - retrying won't help.
                        raise RuntimeError(
                            f"Pollinations refused the request ({response.status_code}): its free "
                            "anonymous tier no longer serves this. Use the 'free' image provider "
                            "(Cloudflare first) or set POLLINATIONS_TOKEN."
                        )
                    if response.status_code < 500 and response.status_code != 429:
                        response.raise_for_status()
                        return response.content
                    last_exc = httpx.HTTPStatusError(
                        f"{response.status_code} server error", request=response.request, response=response
                    )

            if attempt < self.max_attempts:
                await asyncio.sleep(self.retry_backoff_seconds * attempt)

        raise RuntimeError(
            f"Pollinations at {self.base_url} failed after {self.max_attempts} attempts "
            "(no uptime guarantee on this free endpoint - try again shortly)."
        ) from last_exc
