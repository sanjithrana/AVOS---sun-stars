import base64

import httpx

from agentic_core.models.video.base import VideoProvider


class LocalVideoProvider(VideoProvider):
    """
    Bring-your-own self-hosted video generator - same shape as
    ``agentic_core.models.image.local_provider.LocalImageProvider``, for
    a local ComfyUI/similar server wrapped with a small JSON API:

        POST {base_url}/generate
        {"prompt": ..., "width": ..., "height": ..., "seed": ...,
         "duration_seconds": ..., "image": "<base64 png/jpg, or null>"}
        -> {"video": "<base64 mp4>"}

    Genuinely free (your own GPU), not a hosted vendor API - see
    VIDEO_SERVICE_URL in RUNBOOK.md / .env.example. There's no
    standard REST shape for self-hosted video generators the way
    Automatic1111 standardized text-to-image, so this thin JSON contract
    is this repo's own - adapt your ComfyUI workflow's HTTP wrapper to
    match it, or adjust this client to match a workflow you already run.
    """

    name = "local"

    def __init__(self, base_url: str, timeout: float = 600.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    async def generate(
        self,
        prompt: str,
        *,
        width: int = 512,
        height: int = 512,
        seed: int | None = None,
        duration_seconds: float = 2.0,
        image: bytes | None = None,
    ) -> bytes:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(
                    f"{self.base_url}/generate",
                    json={
                        "prompt": prompt,
                        "width": width,
                        "height": height,
                        "seed": seed if seed is not None else -1,
                        "duration_seconds": duration_seconds,
                        "image": base64.b64encode(image).decode() if image else None,
                    },
                )
            except httpx.ConnectError as exc:
                raise RuntimeError(
                    f"Could not reach a local video service at {self.base_url}. "
                    "Set VIDEO_SERVICE_URL to a running self-hosted video generator."
                ) from exc

        response.raise_for_status()
        data = response.json()
        video_b64 = data.get("video")
        if not video_b64:
            raise RuntimeError(f"Local video service at {self.base_url} returned no video.")
        return base64.b64decode(video_b64)
