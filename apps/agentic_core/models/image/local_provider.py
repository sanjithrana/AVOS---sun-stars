import base64

import httpx

from agentic_core.models.image.base import ImageProvider


class LocalImageProvider(ImageProvider):
    """
    Bring-your-own self-hosted image generator - the image equivalent of
    ``src.core.blender.client.HttpBlenderClient``. Points at an
    Automatic1111 / Stable Diffusion WebUI-compatible ``txt2img`` REST
    API (the de facto standard shape most local SD/Flux servers,
    including a bare ComfyUI wrapped with that endpoint, already speak):

        POST {base_url}/sdapi/v1/txt2img
        {"prompt": ..., "width": ..., "height": ..., "seed": ...}
        -> {"images": ["<base64 png>", ...]}

    Genuinely free and unlimited because it's your own GPU, not a
    vendor's - the tradeoff is you have to run it (see
    IMAGE_SERVICE_URL in RUNBOOK.md / .env.example).
    """

    name = "local"

    def __init__(self, base_url: str, timeout: float = 120.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    async def generate(
        self,
        prompt: str,
        *,
        width: int = 512,
        height: int = 512,
        seed: int | None = None,
    ) -> bytes:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(
                    f"{self.base_url}/sdapi/v1/txt2img",
                    json={
                        "prompt": prompt,
                        "width": width,
                        "height": height,
                        "seed": seed if seed is not None else -1,
                        "steps": 20,
                    },
                )
            except httpx.ConnectError as exc:
                raise RuntimeError(
                    f"Could not reach a local image service at {self.base_url}. "
                    "Set IMAGE_SERVICE_URL to a running Automatic1111/SD-WebUI-"
                    "compatible server."
                ) from exc

        response.raise_for_status()
        data = response.json()
        images = data.get("images") or []
        if not images:
            raise RuntimeError(f"Local image service at {self.base_url} returned no images.")
        return base64.b64decode(images[0])
