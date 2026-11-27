import os

from agentic_core.models.video.base import VideoProvider
from agentic_core.models.video.blender_provider import BlenderVideoProvider
from agentic_core.models.video.comfyui_provider import ComfyUIVideoProvider
from agentic_core.models.video.fal_provider import DEFAULT_MODEL as FAL_DEFAULT_MODEL
from agentic_core.models.video.fal_provider import FalVideoProvider
from agentic_core.models.video.local_provider import LocalVideoProvider
from agentic_core.models.video.motion_provider import MotionVideoProvider
from agentic_core.models.video.replicate_provider import ReplicateVideoProvider

# Keep in sync with desktop/types/project.ts's VIDEO_PROVIDERS.
#   blender   free  - real 3D scenes rendered by the AVOS Blender service
#   motion    free  - AI image + smooth camera move (ffmpeg), no GPU/key
#   fal       paid  - real AI clips via fal.ai, Kling by default (FAL_KEY)
#   replicate paid  - real AI clips (REPLICATE_API_TOKEN)
#   comfyui   free  - your own GPU via ComfyUI's API (COMFYUI_URL)
#   local     free  - your own generator behind a small JSON API
#   best      open models from the AVOS model catalog (catalog.json): Wan 2.2 per
#             shot, LTX-2.3 for long shots, free motion when none is set up
#   wan-2.2 / ltx-2.3 / wan-vace          one catalog video model
#   avatar    a talking presenter per shot: LongCat Avatar, InfiniteTalk for long
#   longcat-avatar / infinitetalk         one catalog avatar model
#   (catalog models run on your GPU server via ComfyUI, else on fal.ai)
CATALOG_VIDEO_CHOICES = ("wan-2.2", "ltx-2.3", "wan-vace", "longcat-avatar", "infinitetalk")
KNOWN_PROVIDERS = ("blender", "motion", "fal", "replicate", "comfyui", "local", "best", "avatar", *CATALOG_VIDEO_CHOICES)

# Providers that animate the shot's still image, so the project needs a
# real image provider (the free chain is used when none was picked).
IMAGE_TO_VIDEO_PROVIDERS = frozenset({"motion", "fal", "replicate", "comfyui", "best", "avatar", *CATALOG_VIDEO_CHOICES})


def _float_env(name: str, default: float) -> float:
    try:
        return float(os.getenv(name) or default)
    except ValueError:
        return default


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name) or default)
    except ValueError:
        return default


def is_image_to_video(choice: str | None) -> bool:
    """Does this video choice animate the shot's picture (so the project needs real images)?"""
    if not choice:
        return False
    if choice in IMAGE_TO_VIDEO_PROVIDERS:
        return True
    from agentic_core import settings_store

    c = settings_store.custom_model(choice)
    return bool(c and c["task"] in ("video", "avatar") and (c["kind"] == "comfyui" or c["task"] == "avatar"
                                                           or settings_store.uses(c.get("inputs"), "image_url")))


def resolve_video_choice(provider: str | None) -> str | None:
    """The project's choice, else the VIDEO_PROVIDER env default; None
    or "mock" means no per-shot clips (the final render then animates
    the shot images itself)."""
    choice = (provider or os.getenv("VIDEO_PROVIDER") or "").strip().lower()
    return None if choice in ("", "mock") else choice


def get_video_provider(provider: str | None, *, llm_provider: str | None = None,
                       environment_hint: str | None = None) -> VideoProvider | None:
    """Return the configured VideoProvider, or None to skip per-shot clip
    generation. llm_provider (the project's) is used by 'blender' to plan
    each 3D scene."""
    from agentic_core import settings_store

    settings_store.apply()
    choice = resolve_video_choice(provider)

    if choice is None:
        return None

    custom = settings_store.custom_model(choice)
    if custom and custom["task"] in ("video", "avatar"):
        from agentic_core.models import catalog
        from agentic_core.models.custom_models import CustomVideoProvider

        catalog.backend_for(choice)
        return CustomVideoProvider(choice)

    if choice == "blender":
        from agentic_core.models.llm.factory import get_llm_provider

        try:
            llm = get_llm_provider(llm_provider)
        except Exception:  # noqa: BLE001 - the keyword planner covers it
            llm = None
        return BlenderVideoProvider(
            os.getenv("BLENDER_RENDER_URL") or "http://blender:8090",
            llm=llm,
            environment_hint=environment_hint,
            timeout=_float_env("BLENDER_RENDER_TIMEOUT", 1800.0),
        )

    if choice == "motion":
        return MotionVideoProvider()

    if choice in ("best", "avatar"):
        from agentic_core.models import catalog
        from agentic_core.models.video.catalog_video import BestVideoProvider

        provider = BestVideoProvider("video" if choice == "best" else "avatar")
        if choice == "avatar" and not provider.ready():
            reasons = "; ".join(f"{m}: {catalog.available_backends(m)}" for m in ("longcat-avatar", "infinitetalk"))
            raise catalog.ModelUnavailable(
                "Video 'avatar' needs LongCat Avatar or InfiniteTalk: set FAL_KEY, or export their workflow to your "
                f"GPU server's ComfyUI ({reasons}).")
        return provider

    if choice in CATALOG_VIDEO_CHOICES:
        from agentic_core.models import catalog
        from agentic_core.models.video.catalog_video import CatalogVideoProvider

        catalog.backend_for(choice)  # raises ModelUnavailable (a ValueError) saying how to set it up
        return CatalogVideoProvider(choice)

    if choice == "fal":
        key = os.getenv("FAL_KEY")
        if not key:
            raise ValueError(
                "Video provider 'fal' selected but FAL_KEY is not set "
                "(create one at fal.ai/dashboard/keys and add it to apps/.env)."
            )
        return FalVideoProvider(
            api_key=key,
            model=os.getenv("FAL_VIDEO_MODEL") or FAL_DEFAULT_MODEL,
            cost_per_clip_usd=_float_env("FAL_VIDEO_COST_USD", 0.25),
            timeout=_float_env("FAL_VIDEO_TIMEOUT", 900.0),
        )

    if choice == "replicate":
        token = os.getenv("REPLICATE_API_TOKEN")
        if not token:
            raise ValueError(
                "Video provider 'replicate' selected but REPLICATE_API_TOKEN is not set "
                "(get one at replicate.com/account/api-tokens and add it to apps/.env)."
            )
        return ReplicateVideoProvider(
            api_token=token,
            model=os.getenv("REPLICATE_VIDEO_MODEL") or "bytedance/seedance-1-lite",
            resolution=os.getenv("REPLICATE_VIDEO_RESOLUTION") or "480p",
            cost_per_clip_usd=_float_env("REPLICATE_VIDEO_COST_USD", 0.15),
            timeout=_float_env("REPLICATE_VIDEO_TIMEOUT", 900.0),
        )

    if choice == "comfyui":
        base_url = os.getenv("COMFYUI_URL")
        if not base_url:
            raise ValueError(
                "Video provider 'comfyui' selected but COMFYUI_URL is not set "
                "(e.g. http://host.docker.internal:8188)."
            )
        return ComfyUIVideoProvider(
            base_url=base_url,
            workflow_path=os.getenv("COMFYUI_WORKFLOW") or "/app/comfyui_workflows/video.json",
            fps=_int_env("COMFYUI_FPS", 24),
            frame_multiple=_int_env("COMFYUI_FRAME_MULTIPLE", 8),
            max_frames=_int_env("COMFYUI_MAX_FRAMES", 121),
            timeout=_float_env("COMFYUI_TIMEOUT", 1800.0),
        )

    if choice == "local":
        base_url = os.getenv("VIDEO_SERVICE_URL")
        if not base_url:
            raise ValueError("Video provider 'local' selected but VIDEO_SERVICE_URL is not set.")
        return LocalVideoProvider(base_url=base_url)

    raise ValueError(f"Unknown video provider '{choice}'. Known providers: {KNOWN_PROVIDERS} or a video model added in Settings.")
