"""Settings shared by Facts and Animations (keys, GPU server, models you add) and running the models you add,
against simulated fal.ai / Replicate / OpenAI-compatible servers."""
import asyncio
import json
import os
from pathlib import Path

import httpx
import pytest

from agentic_core import settings_store as S
from agentic_core.models import catalog, custom_models, fal_client
from agentic_core.models.image.factory import get_image_provider
from agentic_core.models.llm import openai_provider
from agentic_core.models.llm.factory import get_llm_provider
from agentic_core.models.video.factory import get_video_provider, is_image_to_video

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 32
MP4 = b"\x00\x00\x00\x18ftypmp42" + b"0" * 32
WAV = b"RIFF\x00\x00\x00\x00WAVEfmt " + b"0" * 32


def _run(c):
    return asyncio.run(c)


@pytest.fixture(autouse=True)
def store(monkeypatch, tmp_path):
    for k in ("FAL_KEY", "REPLICATE_API_TOKEN", "COMFYUI_URL", "MODEL_BACKEND", "DEEPSEEK_KEY", "OPENAI_API_KEY", "GROQ_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("AVOS_SETTINGS_FILE", str(tmp_path / "settings.json"))
    monkeypatch.setenv("COMFYUI_WORKFLOW_DIR", str(tmp_path / "wf"))
    (tmp_path / "wf").mkdir()
    S._ORIG.clear(); S._SET.clear()
    yield tmp_path
    S.save(S._empty())     # puts the environment back
    S._ORIG.clear(); S._SET.clear()


def _mock(monkeypatch, module, handler):
    real = httpx.AsyncClient
    monkeypatch.setattr(module.httpx, "AsyncClient", lambda *a, **k: real(*a, **{**k, "transport": httpx.MockTransport(handler)}))


def test_keys_saved_in_settings_win_over_env_and_clearing_restores_env(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "from-dot-env")
    S.set_env({"GROQ_API_KEY": "gsk_from_settings_1234", "FAL_KEY": "fal-abc-123456"})
    assert os.environ["GROQ_API_KEY"] == "gsk_from_settings_1234" and os.environ["FAL_KEY"] == "fal-abc-123456"
    row = next(k for k in S.public()["keys"] if k["name"] == "GROQ_API_KEY")
    assert row["source"] == "settings" and row["value"].endswith("1234") and "gsk_" not in row["value"]   # masked
    S.set_env({"GROQ_API_KEY": None, "FAL_KEY": ""})
    assert os.environ["GROQ_API_KEY"] == "from-dot-env" and "FAL_KEY" not in os.environ
    assert next(k for k in S.public()["keys"] if k["name"] == "GROQ_API_KEY")["source"] == ".env"
    with pytest.raises(ValueError, match="CAPITALS"):
        S.set_env({"bad name": "x"})
    S.set_env({"MY_CUSTOM_KEY": "v"})
    assert any(k["name"] == "MY_CUSTOM_KEY" and k["group"] == "Custom" for k in S.public()["keys"])


def test_gpu_settings_feed_comfyui_and_backend(monkeypatch):
    S.set_gpu("http://203.0.113.9:8188/", "fal")
    assert os.environ["COMFYUI_URL"] == "http://203.0.113.9:8188" and os.environ["MODEL_BACKEND"] == "fal"
    S.set_gpu(None, "auto")
    assert "MODEL_BACKEND" not in os.environ
    with pytest.raises(ValueError):
        S.set_gpu("gpu-box", None)


def test_model_definitions_are_validated():
    ids = catalog.builtin_ids()
    with pytest.raises(ValueError, match="already used"):
        S.upsert_model({"id": "wan-2.2", "task": "video", "kind": "fal", "endpoint": "fal-ai/x"}, ids)
    with pytest.raises(ValueError, match="endpoint"):
        S.upsert_model({"id": "x1", "task": "image", "kind": "fal", "endpoint": "not an endpoint"}, ids)
    with pytest.raises(ValueError, match="Text models"):
        S.upsert_model({"id": "x2", "task": "image", "kind": "openai", "base_url": "http://a/v1", "model": "m"}, ids)
    with pytest.raises(ValueError, match="JSON"):
        S.upsert_model({"id": "x3", "task": "image", "kind": "fal", "endpoint": "fal-ai/x", "inputs": "{bad"}, ids)
    S.upsert_model({"id": "flux-pro", "name": "FLUX Pro", "task": "image", "kind": "fal", "endpoint": "fal-ai/flux-pro/v1.1"}, ids)
    m = S.custom_model("flux-pro")
    assert m["key_env"] == "FAL_KEY" and m["inputs"]["prompt"] == "{{prompt}}"
    # it shows up in the catalog, the Models page and readiness
    assert catalog.get("flux-pro")["custom"] and "flux-pro" in [x["id"] for x in catalog.models("image")]
    assert "flux-pro" not in [x["id"] for x in catalog.models("image", include_custom=False)]
    row = next(r for r in catalog.status()["models"] if r["id"] == "flux-pro")
    assert not row["ready"] and "FAL_KEY" in row["missing"] and "definition" not in row
    S.delete_model("flux-pro")
    assert S.custom_model("flux-pro") is None


def test_template_filling_drops_missing_files():
    tpl = {"prompt": "{{prompt}}, cinematic", "image_url": "{{image_url}}", "audio_url": "{{audio_url}}", "n": "{{seed}}",
           "size": {"w": "{{width}}"}, "list": ["{{image_url}}", "x"]}
    out = S.fill(tpl, {"prompt": "a cat", "image_url": "data:img", "audio_url": None, "seed": 7, "width": 720})
    assert out == {"prompt": "a cat, cinematic", "image_url": "data:img", "n": 7, "size": {"w": 720}, "list": ["data:img", "x"]}
    assert S.uses({"a": "{{ audio_url }}"}, "audio_url")


def test_custom_fal_image_model_runs(monkeypatch):
    monkeypatch.setenv("FAL_KEY", "k")
    S.upsert_model({"id": "flux-pro", "task": "image", "kind": "fal", "endpoint": "fal-ai/flux-pro/v1.1",
                    "inputs": {"prompt": "{{prompt}}", "image_size": "portrait_16_9", "seed": "{{seed}}"}}, catalog.builtin_ids())
    jobs = []

    def handler(req):
        if req.url.host == "files.example":
            return httpx.Response(200, content=PNG)
        if req.method == "POST":
            jobs.append((req.url.path, json.loads(req.content)))
            return httpx.Response(200, json={"request_id": "r", "status_url": "https://queue.fal.run/x/requests/r/status",
                                             "response_url": "https://queue.fal.run/x/requests/r"})
        if req.url.path.endswith("/status"):
            return httpx.Response(200, json={"status": "COMPLETED"})
        return httpx.Response(200, json={"images": [{"url": "https://files.example/o.png"}]})

    _mock(monkeypatch, fal_client, handler)
    p = get_image_provider("flux-pro")
    assert _run(p.generate("a fox", width=720, height=1280, seed=3)) == PNG
    assert jobs == [("/fal-ai/flux-pro/v1.1", {"prompt": "a fox", "image_size": "portrait_16_9", "seed": 3})]


def test_custom_replicate_avatar_gets_presenter_and_audio(monkeypatch):
    monkeypatch.setenv("REPLICATE_API_TOKEN", "r8_x")
    S.upsert_model({"id": "my-talker", "task": "avatar", "kind": "replicate", "endpoint": "someone/talker",
                    "inputs": {"face": "{{image_url}}", "speech": "{{audio_url}}"}, "output": "video"}, catalog.builtin_ids())
    sent = {}

    def handler(req):
        if req.url.host == "files.example":
            return httpx.Response(200, content=MP4)
        if req.method == "POST":
            sent.update(path=req.url.path, body=json.loads(req.content), auth=req.headers["authorization"])
            return httpx.Response(201, json={"id": "p1", "status": "starting", "urls": {"get": "https://api.replicate.com/v1/predictions/p1"}})
        return httpx.Response(200, json={"id": "p1", "status": "succeeded", "output": {"video": "https://files.example/v.mp4"}})

    _mock(monkeypatch, custom_models, handler)
    _mock(monkeypatch, fal_client, handler)
    real_sleep = asyncio.sleep
    monkeypatch.setattr(custom_models.asyncio, "sleep", lambda s: real_sleep(0))
    p = get_video_provider("my-talker")
    assert p.needs_presenter and p.wants_audio == "required" and is_image_to_video("my-talker")
    assert _run(p.generate("hi", image=PNG, audio=WAV, duration_seconds=3)) == MP4
    assert sent["path"] == "/v1/models/someone/talker/predictions" and sent["auth"] == "Bearer r8_x"
    assert sent["body"]["input"]["face"].startswith("data:image/png") and sent["body"]["input"]["speech"].startswith("data:audio/wav")


def test_custom_comfyui_video_model_needs_its_workflow(monkeypatch, store):
    S.set_gpu("http://gpu:8188", None)
    S.upsert_model({"id": "my-wan-lora", "task": "video", "kind": "comfyui"}, catalog.builtin_ids())
    with pytest.raises(ValueError, match="Upload its ComfyUI workflow"):
        get_video_provider("my-wan-lora")
    (store / "wf" / "my-wan-lora.json").write_text("{}")
    assert get_video_provider("my-wan-lora").name == "my-wan-lora"


def test_custom_openai_compatible_text_model(monkeypatch):
    S.upsert_model({"id": "deepseek", "name": "DeepSeek", "task": "llm", "kind": "openai", "base_url": "https://api.deepseek.com/v1",
                    "model": "deepseek-chat", "key_env": "DEEPSEEK_KEY"}, catalog.builtin_ids())
    with pytest.raises(ValueError, match="DEEPSEEK_KEY"):
        get_llm_provider("deepseek")
    S.set_env({"DEEPSEEK_KEY": "sk-ds"})
    seen = {}

    def handler(req):
        seen.update(url=str(req.url), body=json.loads(req.content), auth=req.headers["authorization"])
        return httpx.Response(200, json={"choices": [{"message": {"content": "ready"}}]})

    _mock(monkeypatch, openai_provider, handler)
    llm = get_llm_provider("deepseek")
    assert _run(llm.complete("hi")) == "ready" and llm.name == "deepseek"
    assert seen["url"] == "https://api.deepseek.com/v1/chat/completions" and seen["body"]["model"] == "deepseek-chat"
    assert seen["auth"] == "Bearer sk-ds"
    # a local server with no key (LM Studio)
    S.upsert_model({"id": "lmstudio", "task": "llm", "kind": "openai", "base_url": "http://localhost:1234/v1", "model": "qwen"}, catalog.builtin_ids())
    assert get_llm_provider("lmstudio").base_url == "http://localhost:1234/v1"


def test_studio_copy_is_identical():
    here = Path(__file__).resolve().parents[2]
    assert (here / "agentic_core" / "settings_store.py").read_text() == (here / "animation_studio" / "studio" / "avos_settings.py").read_text()
