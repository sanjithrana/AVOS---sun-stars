import logging

import httpx

from agentic_core.models.llm.base import LLMProvider
from agentic_core.models.video.base import VideoProvider
from agentic_core.pipelines.blender.planner import plan_scene

logger = logging.getLogger(__name__)


class BlenderVideoProvider(VideoProvider):
    """
    Free 3D animation: each shot is turned into a 3D scene plan (the
    project's LLM picks environment, characters, animations, props and
    camera from what the Blender service has) and rendered by the AVOS
    Blender service (blender_service/server.py) - built-in mannequins, or
    your Mixamo characters and animations from apps/blender_assets.

    Not image-to-video: the shot's AI image isn't used for the clip.
    """

    name = "blender"
    cost_per_clip_usd = 0.0

    def __init__(self, base_url: str, *, llm: LLMProvider | None = None, environment_hint: str | None = None,
                 timeout: float = 1800.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.llm = llm
        self.environment_hint = environment_hint
        self.timeout = timeout
        self.last_scene: dict | None = None
        self._catalog: dict | None = None

    async def catalog(self, client: httpx.AsyncClient) -> dict:
        if self._catalog is None:
            response = await client.get(f"{self.base_url}/catalog")
            response.raise_for_status()
            self._catalog = response.json()
        return self._catalog

    async def generate(self, prompt: str, *, width: int = 720, height: int = 1280, seed: int | None = None,
                       duration_seconds: float = 4.0, image: bytes | None = None) -> bytes:
        # The compiled prompt is "<description> Characters: .. Objects: ..
        # Setting: .. Camera: .. Lighting: .. Style: .. Motion: ..". The
        # planner wants what happens, not the 2D-camera/lighting boilerplate.
        description = prompt.split(" Setting:")[0].split(" Motion:")[0]
        async with httpx.AsyncClient(timeout=httpx.Timeout(self.timeout, connect=10.0)) as client:
            try:
                catalog = await self.catalog(client)
                scene = await plan_scene(description, catalog=catalog, duration=duration_seconds, llm=self.llm,
                                         seed=seed, environment_hint=self.environment_hint)
                self.last_scene = scene
                logger.info("Blender scene (%s): %s", scene.get("planner"), scene)
                response = await client.post(f"{self.base_url}/render", json=scene)
            except httpx.ConnectError as exc:
                raise RuntimeError(
                    f"Could not reach the Blender render service at {self.base_url}. Start it with "
                    "`docker compose up -d blender`, or run blender_service/server.py with your own "
                    "Blender and set BLENDER_RENDER_URL."
                ) from exc
            except httpx.ReadTimeout as exc:
                raise RuntimeError(
                    f"The Blender render took longer than {self.timeout:.0f}s. Lower BLENDER_SAMPLES / "
                    "BLENDER_FPS, use BLENDER_ENGINE=workbench for previews, or render on a GPU."
                ) from exc
        if response.status_code >= 400:
            try:
                detail = response.json().get("error")
            except ValueError:
                detail = response.text[:300]
            raise RuntimeError(f"Blender render failed ({response.status_code}): {detail}")
        return response.content
