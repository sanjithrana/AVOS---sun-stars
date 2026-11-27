import os

from agentic_core.models.llm.base import LLMProvider
from agentic_core.models.llm.groq_provider import GroqProvider
from agentic_core.models.llm.mock_provider import MockLLMProvider
from agentic_core.models.llm.ollama_provider import OllamaProvider
from agentic_core.models.llm.openai_provider import OpenAIProvider

# Every name a project can pick in the New Project form / API, and every
# name LLM_PROVIDER may be set to. Keep this in sync with
# desktop/types/project.ts's LLM_PROVIDERS and with README/RUNBOOK docs.
KNOWN_PROVIDERS = ("mock", "openai", "ollama", "llamacpp", "colibri", "groq")


def get_llm_provider(provider: str | None = None) -> LLMProvider:
    p = _get_llm_provider(provider)
    if isinstance(p, MockLLMProvider):
        return p
    from agentic_core.models.llm import cache

    return cache.wrap(p)


def _get_llm_provider(provider: str | None = None) -> LLMProvider:
    """
    Return the configured LLM provider - the router between the
    Director/agents and whichever backend actually writes text.

    Selection order:
      1. ``provider`` - an explicit choice, e.g. a project's saved
         ``llm_provider`` field (per-project routing).
      2. ``LLM_PROVIDER`` env var - a deployment-wide default.
      3. Auto-detect: OPENAI_API_KEY, then GROQ_API_KEY, in that order
         (unchanged from before per-project selection existed, so
         existing deployments keep working with no config changes).
      4. MockLLMProvider - deterministic, offline, no credentials. This
         is also what an explicit ``provider="mock"`` selects, and it's
         always what runs in tests (see api/tests/conftest.py).

    Raises ValueError for an explicit choice that needs a credential
    that isn't set, rather than silently falling back to the mock - a
    person who picked "Groq" in the UI should see why it didn't run,
    not get a mock script that looks plausible.
    """
    from agentic_core import settings_store

    settings_store.apply()
    choice = provider or os.getenv("LLM_PROVIDER")

    custom = settings_store.custom_model(choice) if choice else None
    if custom and custom["task"] == "llm":
        key_env = custom.get("key_env")
        key = os.getenv(key_env) if key_env else "none"
        if not key:
            raise ValueError(f"Text model '{custom['name']}' needs the {key_env} key (Settings → API keys).")
        provider_ = OpenAIProvider(api_key=key, model=custom["model"], base_url=custom["base_url"], timeout=120.0)
        provider_.name = custom["id"]
        return provider_

    if choice == "mock":
        return MockLLMProvider()

    if choice == "openai":
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("LLM provider 'openai' selected but OPENAI_API_KEY is not set.")
        return OpenAIProvider(api_key=api_key, model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"))

    if choice == "ollama":
        return OllamaProvider(
            base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
            model=os.getenv("OLLAMA_MODEL", "llama3.1"),
        )

    if choice == "llamacpp":
        # llama.cpp's llama-server (a small GGUF model on your laptop) speaks the OpenAI API.
        base = (os.getenv("LLAMACPP_URL") or "http://localhost:8080").rstrip("/")
        p = OpenAIProvider(api_key="none", model=os.getenv("LLAMACPP_MODEL") or "local", base_url=f"{base}/v1", timeout=300.0)
        p.name = "llamacpp"
        return p

    if choice == "colibri":
        # Colibrì (github.com/JustVugg/colibri): huge MoE models streamed from SSD on a CPU, OpenAI API on port 8000.
        # Slow (a few tokens a second), so a long timeout.
        base = (os.getenv("COLIBRI_URL") or "http://localhost:8000").rstrip("/")
        p = OpenAIProvider(api_key="none", model=os.getenv("COLIBRI_MODEL") or "local", base_url=f"{base}/v1", timeout=1800.0)
        p.name = "colibri"
        return p

    if choice == "groq":
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("LLM provider 'groq' selected but GROQ_API_KEY is not set.")
        return GroqProvider(api_key=api_key, model=os.getenv("GROQ_MODEL", "openai/gpt-oss-20b"))

    if choice:
        raise ValueError(f"Unknown LLM provider '{choice}'. Known providers: {KNOWN_PROVIDERS} or a text model added in Settings.")

    # No explicit choice anywhere: auto-detect from whichever credential
    # exists, exactly like the pre-router behaviour.
    if os.getenv("OPENAI_API_KEY"):
        return OpenAIProvider(
            api_key=os.environ["OPENAI_API_KEY"],
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        )
    if os.getenv("GROQ_API_KEY"):
        return GroqProvider(
            api_key=os.environ["GROQ_API_KEY"],
            model=os.getenv("GROQ_MODEL", "openai/gpt-oss-20b"),
        )

    return MockLLMProvider()
