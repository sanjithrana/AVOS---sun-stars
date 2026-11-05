"""Settings page API: keys, GPU server, models you add, ComfyUI workflow upload; projects can use the models you add."""
import json

import pytest
from fastapi.testclient import TestClient

from agentic_core import settings_store
from src.main import app


@pytest.fixture
def client(monkeypatch, tmp_path):
    for k in ("FAL_KEY", "COMFYUI_URL", "MODEL_BACKEND", "MY_KEY"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("AVOS_SETTINGS_FILE", str(tmp_path / "s.json"))
    monkeypatch.setenv("COMFYUI_WORKFLOW_DIR", str(tmp_path / "wf"))
    settings_store._ORIG.clear(); settings_store._SET.clear()
    with TestClient(app) as c:
        yield c
    settings_store.save(settings_store._empty())     # puts the environment back
    settings_store._ORIG.clear(); settings_store._SET.clear()


def test_keys_are_saved_and_masked(client):
    body = client.get("/api/v1/settings").json()
    assert {"FAL_KEY", "OPENAI_API_KEY", "REPLICATE_API_TOKEN"} <= {k["name"] for k in body["keys"]}
    body = client.put("/api/v1/settings/keys", json={"FAL_KEY": "fal-secret-9876", "MY_KEY": "abc"}).json()
    fal = next(k for k in body["keys"] if k["name"] == "FAL_KEY")
    assert fal["set"] and fal["source"] == "settings" and fal["value"].endswith("9876") and "secret" not in fal["value"]
    assert any(k["name"] == "MY_KEY" for k in body["keys"])
    # the Models page now sees the key
    assert next(m for m in client.get("/api/v1/models").json()["models"] if m["id"] == "z-image")["ready"]
    assert client.put("/api/v1/settings/keys", json={"bad key": "x"}).status_code == 400
    body = client.put("/api/v1/settings/keys", json={"FAL_KEY": ""}).json()
    assert not next(k for k in body["keys"] if k["name"] == "FAL_KEY")["set"]


def test_gpu_server(client):
    assert client.put("/api/v1/settings/gpu", json={"comfyui_url": "not a url"}).status_code == 400
    body = client.put("/api/v1/settings/gpu", json={"comfyui_url": "http://127.0.0.1:9", "model_backend": "comfyui"}).json()
    assert body["gpu"] == {"comfyui_url": "http://127.0.0.1:9", "model_backend": "comfyui"}
    r = client.post("/api/v1/settings/gpu/test").json()
    assert not r["ok"] and "Can't reach" in r["detail"]


def test_add_model_upload_workflow_and_delete(client, tmp_path):
    r = client.post("/api/v1/settings/models", json={"id": "my-wan-lora", "name": "My Wan LoRA", "task": "video", "kind": "comfyui"})
    assert r.status_code == 200 and r.json()["models"][0]["workflow"] == "my-wan-lora.json"
    assert client.post("/api/v1/settings/models", json={"id": "wan-2.2", "task": "video", "kind": "fal", "endpoint": "a/b"}).status_code == 400
    # regular saves and workflows without placeholders are refused with a clear reason
    bad = client.put("/api/v1/settings/models/my-wan-lora/workflow", content=json.dumps({"nodes": [], "links": []}))
    assert bad.status_code == 400 and "Export (API)" in bad.json()["error"]["message"]
    nop = client.put("/api/v1/settings/models/my-wan-lora/workflow", content=json.dumps({"1": {"class_type": "X", "inputs": {}}}))
    assert nop.status_code == 400 and "{{PROMPT}}" in nop.json()["error"]["message"]
    wf = {"1": {"class_type": "LoadImage", "inputs": {"image": "{{IMAGE}}"}}, "2": {"class_type": "CLIPTextEncode", "inputs": {"text": "{{PROMPT}}"}}}
    ok = client.put("/api/v1/settings/models/my-wan-lora/workflow", content=json.dumps(wf)).json()
    assert ok["uploaded"]["placeholders"] == ["{{PROMPT}}", "{{IMAGE}}"] and "my-wan-lora.json" in ok["workflows"]
    assert (tmp_path / "wf" / "my-wan-lora.json").is_file()
    # built-in catalog models take uploads too
    assert client.put("/api/v1/settings/models/wan-2.2/workflow", content=json.dumps(wf)).status_code == 200
    client.put("/api/v1/settings/gpu", json={"comfyui_url": "http://gpu:8188"})
    models = {m["id"]: m for m in client.get("/api/v1/models").json()["models"]}
    assert models["my-wan-lora"]["ready"] and models["my-wan-lora"]["custom"] and models["wan-2.2"]["backend"] == "comfyui"
    assert client.post("/api/v1/settings/models/my-wan-lora/test").json()["ok"]
    assert client.delete("/api/v1/settings/models/my-wan-lora").status_code == 200
    assert not (tmp_path / "wf" / "my-wan-lora.json").exists()
    assert client.delete("/api/v1/settings/models/nope").status_code == 404


def test_text_model_test_reports_missing_key(client):
    client.post("/api/v1/settings/models", json={"id": "deepseek", "task": "llm", "kind": "openai", "base_url": "https://api.deepseek.com/v1",
                                                 "model": "deepseek-chat", "key_env": "DEEPSEEK_KEY"})
    r = client.post("/api/v1/settings/models/deepseek/test").json()
    assert not r["ok"] and "DEEPSEEK_KEY" in r["detail"]


from packages.contracts.project import ProjectCreate  # noqa: E402
from src.errors import APIException  # noqa: E402
from src.services.project_service import ProjectService  # noqa: E402
from tests.conftest import requires_db  # noqa: E402


@requires_db
@pytest.mark.asyncio
async def test_projects_accept_models_you_added(db_session, clean_db, monkeypatch, tmp_path):
    monkeypatch.setenv("AVOS_SETTINGS_FILE", str(tmp_path / "s.json"))
    ids = {"wan-2.2"}
    settings_store.upsert_model({"id": "my-flux", "task": "image", "kind": "fal", "endpoint": "fal-ai/flux-pro"}, ids)
    settings_store.upsert_model({"id": "my-talker", "task": "avatar", "kind": "fal", "endpoint": "fal-ai/x/talk"}, ids)
    settings_store.upsert_model({"id": "deepseek", "task": "llm", "kind": "openai", "base_url": "http://x/v1", "model": "m"}, ids)
    svc = ProjectService(db_session)
    p = await svc.create_project(ProjectCreate(name="t", topic="Volcanoes", duration=15, aspect_ratio="9:16",
                                               llm_provider="deepseek", image_provider="my-flux", video_provider="my-talker"))
    assert p.video_provider == "my-talker"
    with pytest.raises(APIException) as err:
        await svc.create_project(ProjectCreate(name="t", topic="x", duration=15, aspect_ratio="9:16", image_provider="my-talker"))
    assert "model added in Settings" in err.value.message
