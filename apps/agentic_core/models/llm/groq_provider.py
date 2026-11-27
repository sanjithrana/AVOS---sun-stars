from agentic_core.models.llm.openai_provider import OpenAIProvider


class GroqProvider(OpenAIProvider):
    """
    Groq (https://console.groq.com) - an OpenAI-compatible Chat
    Completions endpoint, so this only changes the base URL, default
    model and vendor name; ``OpenAIProvider.complete`` does the rest.

    Free tier as of writing: no credit card required, ~30 requests/min
    and ~1,000/day per model (Groq enforces this server-side; nothing
    here rate-limits client-side). Get a key at console.groq.com/keys.

    Default model: Groq deprecated ``llama-3.1-8b-instant`` on
    2026-08-16 (console.groq.com/docs/deprecations) - a request against
    it now 404s. ``openai/gpt-oss-20b`` is Groq's own recommended
    free-tier replacement (fastest current production model, same
    131k-token context window). If Groq deprecates *this* one too,
    override with ``GROQ_MODEL`` rather than waiting on a code change.
    """

    name = "groq"

    def __init__(
        self,
        api_key: str,
        model: str = "openai/gpt-oss-20b",
        base_url: str = "https://api.groq.com/openai/v1",
        timeout: float = 60.0,
    ) -> None:
        super().__init__(api_key=api_key, model=model, base_url=base_url, timeout=timeout)
