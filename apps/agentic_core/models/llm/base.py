from abc import ABC, abstractmethod


class LLMProvider(ABC):
    """
    Vendor-agnostic boundary for text generation.

    Every agent/pipeline that needs an LLM depends on this interface,
    never on a concrete SDK. This keeps agentic_core testable offline
    and swappable between providers (or a deterministic mock) without
    touching call sites.
    """

    name: str = "unknown"

    @abstractmethod
    async def complete(
        self,
        prompt: str,
        *,
        system: str | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ) -> str:
        """Return a single completion string for the given prompt."""
        raise NotImplementedError
