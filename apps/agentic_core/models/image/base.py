from abc import ABC, abstractmethod


class ImageProvider(ABC):
    """
    Vendor-agnostic boundary for text-to-image generation - the image
    equivalent of ``agentic_core.models.llm.base.LLMProvider``. A video
    "candidate" today is really a still frame standing in for a shot
    (see ``VideoGenerationService``); this is what can put a real,
    AI-generated picture behind that frame instead of the deterministic
    MOCK placeholder.

    name is used both as an asset tag (``renderer=<name>``) and as the
    project's stored ``image_provider`` choice.
    """

    name: str = "unknown"

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        *,
        width: int = 512,
        height: int = 512,
        seed: int | None = None,
    ) -> bytes:
        """Return the generated image's raw bytes (PNG or JPEG)."""
        raise NotImplementedError
