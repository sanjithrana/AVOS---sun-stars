"""Settings > Test beside each key: one free read-only call per provider, faked here (no network)."""
import asyncio

import httpx
import pytest

from src.routes import keycheck


def run(name, handler, monkeypatch, **env):
    for k in list(keycheck.CHECKS) + list(keycheck.LOCAL) + ["OLLAMA_MODEL"]:
        monkeypatch.delenv(k, raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    seen = {}

    def h(req: httpx.Request):
        seen["url"], seen["headers"] = str(req.url), dict(req.headers)
        return handler(req)
    async def go():
        async with httpx.AsyncClient(transport=httpx.MockTransport(h)) as c:
            return await keycheck.check(name, c)
    return asyncio.run(go()), seen


def test_good_and_bad_keys(monkeypatch):
    r, seen = run("GROQ_API_KEY", lambda q: httpx.Response(200, json={"data": []}), monkeypatch, GROQ_API_KEY="gsk_x")
    assert r["ok"] and "accepted" in r["detail"] and seen["url"].startswith("https://api.groq.com/") and seen["headers"]["authorization"] == "Bearer gsk_x"
    r, _ = run("OPENAI_API_KEY", lambda q: httpx.Response(401), monkeypatch, OPENAI_API_KEY="sk-bad")
    assert not r["ok"] and "refused" in r["detail"]
    r, seen = run("ANTHROPIC_API_KEY", lambda q: httpx.Response(200, json={}), monkeypatch, ANTHROPIC_API_KEY="a")
    assert r["ok"] and seen["headers"]["x-api-key"] == "a"
    r, _ = run("FAL_KEY", lambda q: httpx.Response(404), monkeypatch, FAL_KEY="k")
    assert r["ok"]
    r, _ = run("CLOUDFLARE_API_TOKEN", lambda q: httpx.Response(200, json={"result": {"status": "disabled"}}), monkeypatch, CLOUDFLARE_API_TOKEN="t")
    assert not r["ok"] and "disabled" in r["detail"]


def test_missing_untestable_and_offline(monkeypatch):
    r, _ = run("GROQ_API_KEY", lambda q: httpx.Response(200), monkeypatch)
    assert not r["ok"] and "Nothing saved" in r["detail"]
    r, _ = run("MY_CUSTOM_KEY", lambda q: httpx.Response(200), monkeypatch, MY_CUSTOM_KEY="x")
    assert not r["ok"] and "no automatic test" in r["detail"]

    def down(q):
        raise httpx.ConnectError("no route")
    r, _ = run("OPENROUTER_API_KEY", down, monkeypatch, OPENROUTER_API_KEY="x")
    assert not r["ok"] and "Could not reach" in r["detail"]


def test_ollama(monkeypatch):
    tags = lambda q: httpx.Response(200, json={"models": [{"name": "qwen2.5:7b"}]})  # noqa: E731
    r, seen = run("OLLAMA_BASE_URL", tags, monkeypatch, OLLAMA_BASE_URL="http://host:11434/")
    assert r["ok"] and "qwen2.5:7b" in r["detail"] and seen["url"] == "http://host:11434/api/tags"
    r, _ = run("OLLAMA_MODEL", tags, monkeypatch, OLLAMA_BASE_URL="http://host:11434", OLLAMA_MODEL="llama3.2:3b")
    assert not r["ok"] and "ollama pull llama3.2:3b" in r["detail"]
    r, _ = run("OLLAMA_MODEL", tags, monkeypatch, OLLAMA_BASE_URL="http://host:11434", OLLAMA_MODEL="qwen2.5")
    assert r["ok"]


def test_route(monkeypatch, tmp_path):
    pytest.importorskip("agentic_core.models")
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from src.routes.settings import router
    app = FastAPI()
    app.include_router(router)
    monkeypatch.setenv("AVOS_SETTINGS_FILE", str(tmp_path / "s.json"))
    monkeypatch.delenv("STABILITY_API_KEY", raising=False)
    with TestClient(app) as c:
        r = c.post("/api/v1/settings/keys/STABILITY_API_KEY/test").json()
    assert r["ok"] is False and "Nothing saved" in r["detail"]
