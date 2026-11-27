from abc import ABC, abstractmethod


class VideoProvider(ABC):
    """
    Vendor-agnostic boundary for text/image-to-video generation.

    Implementations (see factory.py for how a project picks one):

      motion    - free: animates the shot's AI image with a smooth
                  camera move (zoom/pan) using ffmpeg. No GPU, no key.
      replicate - paid: real AI video clips from a hosted model
                  (default bytedance/seedance-1-lite), image-to-video
                  from the shot's image.
      comfyui   - free on your own GPU: drives a ComfyUI server's API
                  with a workflow you export from ComfyUI (LTX-Video,
                  Wan 2.x, ...).
      local     - free on your own GPU: a custom JSON wrapper around
                  your own generator (POST /generate -> base64 mp4).

    ``image`` is the shot's still (the first video candidate's image)
    when one exists; image-to-video providers animate it so the clip
    matches the storyboard. ``duration_seconds`` is the shot's length on
    the narration timeline; providers may return a longer or shorter
    clip - the final render trims or extends each clip to fit.
    """

    name: str = "unknown"
    # Rough USD cost of one clip, recorded on the audit trail / budget.
    cost_per_clip_usd: float = 0.0

    @abstractmethod
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
        """Return the generated clip's raw bytes (mp4 preferred)."""
        raise NotImplementedError
