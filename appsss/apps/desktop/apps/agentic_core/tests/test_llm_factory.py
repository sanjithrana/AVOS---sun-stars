import pytest

from agentic_core.models.llm.factory import get_llm_provider
from agentic_core.models.llm.groq_provider import GroqProvider
from agentic_core.models.llm.mock_provider import MockLLMProvider
from agentic_core.models.llm.ollama_provider import OllamaProvider
from agentic_core.models.llm.openai_provider import OpenAIProvider


@pytest.fixture(autouse=True)
def _clear_llm_env(monkeypatch):
    # Every test starts from a clean slate regardless of the environment
    # the test runner happens to have (e.g. a real OPENAI_API_KEY set
    # locally) so auto-detect/explicit-choice behaviour is deterministic.
    for var in ("LLM_PROVIDER", "OPENAI_API_KEY", "OPENAI_MODEL", "GROQ_API_KEY", "GROQ_MODEL"):
        monkeypatch.delenv(var, raising=False)


def test_no_choice_and_no_keys_returns_mock():
    provider = get_llm_provider(None)
    assert isinstance(provider, MockLLMProvider)


def test_explicit_mock_always_wins_even_with_keys_set(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-something")
    provider = get_llm_provider("mock")
    assert isinstance(provider, MockLLMProvider)


def test_explicit_ollama_needs_no_credential():
    provider = get_llm_provider("ollama")
    assert isinstance(provider, OllamaProvider)
    assert provider.base_url == "http://localhost:11434"


def test_ollama_reads_base_url_and_model_from_env(monkeypatch):
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434")
    monkeypatch.setenv("OLLAMA_MODEL", "llama3.2")
    provider = get_llm_provider("ollama")
    assert provider.base_url == "http://host.docker.internal:11434"
    assert provider.model == "llama3.2"


def test_explicit_groq_without_key_raises():
    with pytest.raises(ValueError, match="GROQ_API_KEY"):
        get_llm_provider("groq")


def test_explicit_groq_with_key_returns_groq_provider(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "gsk-test")
    provider = get_llm_provider("groq")
    assert isinstance(provider, GroqProvider)
    assert provider.model == "openai/gpt-oss-20b"


def test_explicit_openai_without_key_raises():
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        get_llm_provider("openai")


def test_explicit_openai_with_key_returns_openai_provider(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    provider = get_llm_provider("openai")
    assert isinstance(provider, OpenAIProvider)


def test_unknown_explicit_choice_raises():
    with pytest.raises(ValueError, match="Unknown LLM provider"):
        get_llm_provider("not-a-real-provider")


def test_env_default_used_when_no_explicit_choice(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    provider = get_llm_provider(None)
    assert isinstance(provider, OllamaProvider)


def test_explicit_choice_overrides_env_default(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    provider = get_llm_provider("mock")
    assert isinstance(provider, MockLLMProvider)


def test_auto_detect_prefers_openai_over_groq(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("GROQ_API_KEY", "gsk-test")
    provider = get_llm_provider(None)
    assert isinstance(provider, OpenAIProvider)


def test_auto_detect_falls_back_to_groq(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "gsk-test")
    provider = get_llm_provider(None)
    assert isinstance(provider, GroqProvider)


def test_llamacpp_local_gguf_server(monkeypatch):
    monkeypatch.setenv("LLAMACPP_URL", "http://127.0.0.1:8089/")
    monkeypatch.setenv("LLAMACPP_MODEL", "qwen2.5-7b-instruct-q4_k_m")
    p = get_llm_provider("llamacpp")
    assert p.name == "llamacpp" and p.base_url == "http://127.0.0.1:8089/v1" and p.model == "qwen2.5-7b-instruct-q4_k_m"


def test_answers_are_cached_for_a_while(monkeypatch):
    import asyncio

    from agentic_core.models.llm import cache

    cache.clear()
    monkeypatch.setenv("GROQ_API_KEY", "gsk-test")
    calls = []

    async def fake(self, prompt, *, system=None, max_tokens=1024, temperature=0.7):
        calls.append(prompt)
        return f"answer {len(calls)}"
    monkeypatch.setattr(GroqProvider, "complete", fake)
    p = get_llm_provider("groq")
    assert isinstance(p, GroqProvider)
    assert asyncio.run(p.complete("research volcanoes")) == "answer 1"
    assert asyncio.run(get_llm_provider("groq").complete("research volcanoes")) == "answer 1"   # a retry: no call
    assert asyncio.run(p.complete("something else")) == "answer 2" and len(calls) == 2
    monkeypatch.setenv("LLM_CACHE_TTL", "0")
    assert asyncio.run(p.complete("research volcanoes")) == "answer 3"
    cache.clear()
