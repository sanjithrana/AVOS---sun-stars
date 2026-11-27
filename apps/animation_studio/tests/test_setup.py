"""Home's setup card: one key is used for what it is good at, and the advice names the missing role."""
from __future__ import annotations

import pytest

from studio import avos_settings, llm, setup

ALL = ("GROQ_API_KEY", "GEMINI_API_KEY", "OPENROUTER_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "FAL_KEY",
       "CLOUDFLARE_ACCOUNT_ID", "CLOUDFLARE_API_TOKEN", "IMAGE_SERVICE_URL", "COMFYUI_URL", "STUDIO_DEFAULT_AGENT")


@pytest.fixture
def keys(monkeypatch):
    for k in ALL:
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr(avos_settings, "apply", lambda *a, **k: None)
    monkeypatch.setattr(avos_settings, "workers", lambda enabled_only=False: [])
    return monkeypatch


def role(p, r):
    return next(x for x in p["roles"] if x["role"] == r)


def test_nothing_saved_runs_on_free_fallbacks_and_asks_for_one_key(keys):
    p = setup.plan()
    assert p["level"] == "starter" and role(p, "writer")["uses"].startswith("Ollama") and role(p, "pictures")["uses"] == "Pollinations"
    assert p["tips"][0]["id"] == "first-key" and "Groq" in p["tips"][0]["text"]


def test_a_video_key_alone_gets_a_free_text_model_suggested(keys):
    keys.setenv("FAL_KEY", "x")
    p = setup.plan()
    assert role(p, "video")["uses"] == "fal.ai" and "Seedance" in role(p, "video")["note"] and role(p, "pictures")["uses"] == "fal.ai"
    assert p["tips"][0]["id"] == "free-text" and "fal.ai will make the pictures and video" in p["tips"][0]["text"]


def test_a_text_key_becomes_the_writer_by_itself(keys):
    keys.setenv("GEMINI_API_KEY", "x")
    assert llm.default_agent() == "gemini"
    keys.setenv("GROQ_API_KEY", "x")
    assert llm.default_agent() == "groq"                         # free tiers first
    keys.setenv("STUDIO_DEFAULT_AGENT", "gemini")
    assert llm.default_agent() == "gemini"                       # your own pick always wins
    p = setup.plan()
    assert role(p, "writer")["uses"] == "Gemini" and any(t["id"] == "video" for t in p["tips"])


def test_text_and_video_together_is_the_best_setup(keys):
    keys.setenv("GROQ_API_KEY", "x")
    keys.setenv("FAL_KEY", "x")
    p = setup.plan()
    assert p["level"] == "best" and not any(t["id"] in ("free-text", "first-key", "video") for t in p["tips"])
