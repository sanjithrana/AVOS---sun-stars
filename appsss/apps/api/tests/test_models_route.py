"""GET /api/v1/models: the model catalog for the Models page and the New Project pickers."""
from fastapi.testclient import TestClient

from src.main import app


def test_models_route_lists_catalog_with_readiness(monkeypatch, tmp_path):
    monkeypatch.delenv("FAL_KEY", raising=False)
    monkeypatch.delenv("MODEL_BACKEND", raising=False)
    monkeypatch.setenv("COMFYUI_WORKFLOW_DIR", str(tmp_path))
    with TestClient(app) as c:
        body = c.get("/api/v1/models").json()
    assert set(body["tasks"]) == {"image", "video", "avatar", "control", "reference", "speech", "sound"}
    ids = {m["id"]: m for m in body["models"]}
    assert ids["wan-2.2"]["fal"]["endpoint"] == "fal-ai/wan/v2.2-a14b/image-to-video"
    assert not ids["wan-2.2"]["ready"] and "FAL_KEY" in ids["wan-2.2"]["missing"]
    monkeypatch.setenv("FAL_KEY", "k")
    with TestClient(app) as c:
        ids = {m["id"]: m for m in c.get("/api/v1/models").json()["models"]}
    assert ids["wan-2.2"]["ready"] and ids["wan-2.2"]["backend"] == "fal"
    assert not ids["scail-2"]["ready"]                                   # GPU server only
    assert not ids["chatterbox"]["ready"] and ids["chatterbox"]["backends"] == {}    # a GPU worker's speech backend only
