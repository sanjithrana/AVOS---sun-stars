"""Model Fabric in the API: a shot generated on a real AVOS GPU worker (mock backend, pretend RTX 4090), every run
stored in gpu_jobs and broadcast as GPU_JOB_* events, QA scores fed back for learned routing, the GPU page API,
generation limits per project, and the repair ladder stopping at the attempt limit."""
import json
import socket
import sys
import threading
import time
from pathlib import Path

import pytest
import uvicorn
from fastapi.testclient import TestClient
from sqlalchemy import select

from agentic_core import settings_store
from agentic_core.agents.repair.classifier import build_repair_plan
from agentic_core.model_fabric import performance, workers
from packages.contracts.qa import QADimension, QADimensionResult, QAResult, QAStatus
from src.database.models.gpu_job import GpuJob
from src.services import fabric_service
from src.services.qa_service import QACommitteeService as QAService
from src.services.video_generation_service import VideoGenerationService
from tests.conftest import CapturingEventBus, requires_db
from tests.test_video_generation_real_provider import _ready_shot

WORKER_DIR = Path(__file__).resolve().parents[2] / "gpu_worker"
RTX4090 = '{"name": "NVIDIA GeForce RTX 4090", "vram_gb": 24, "compute_capability": "8.9"}'


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def gpu_worker_url(tmp_path_factory):
    """A real GPU worker process-in-a-thread: mock backend, pretend RTX 4090, quick jobs."""
    sys.path.insert(0, str(WORKER_DIR))
    from worker import config, gpu
    from worker.adapters.mock import MockAdapter
    from worker.app import create_app
    from worker.jobs import Queue

    config.FAKE_GPU, config.MOCK_SECONDS, config.TOKEN = RTX4090, 0.2, "secret-token"
    config.RESULTS = tmp_path_factory.mktemp("worker") / "results"
    config.COMFYUI_WORKFLOWS = tmp_path_factory.mktemp("worker-wf")
    config.MODELS_DIR = str(tmp_path_factory.mktemp("worker-models"))
    gpu._smi = lambda: None
    gpu._cache.update(t=0.0, gpu=None)
    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(create_app(Queue({"mock": MockAdapter()})), host="127.0.0.1", port=port,
                                           log_level="warning"))
    t = threading.Thread(target=server.run, daemon=True)
    t.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    t.join(timeout=5)


@pytest.fixture
def fabric_env(monkeypatch, tmp_path, gpu_worker_url):
    for k in ("FAL_KEY", "COMFYUI_URL", "MODEL_BACKEND", "CLOUDFLARE_ACCOUNT_ID", "CLOUDFLARE_API_TOKEN", "GPU_WORKER_TOKEN"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("AVOS_SETTINGS_FILE", str(tmp_path / "settings.json"))
    monkeypatch.setenv("COMFYUI_WORKFLOW_DIR", str(tmp_path / "wf"))
    settings_store._ORIG.clear(); settings_store._SET.clear()
    settings_store.set_env({"GPU_WORKER_TOKEN": "secret-token"})
    settings_store.upsert_worker({"id": "home-4090", "name": "RTX 4090 at home", "url": gpu_worker_url, "cost_per_hour": 0.4})
    workers.forget()
    performance.update({})
    bus = CapturingEventBus()
    monkeypatch.setattr("src.services.fabric_service.get_event_bus", lambda: bus)
    yield bus
    settings_store.save(settings_store._empty())
    settings_store._ORIG.clear(); settings_store._SET.clear()
    workers.forget()
    performance.update({})


@requires_db
@pytest.mark.asyncio
async def test_shot_runs_on_the_gpu_worker_and_every_run_is_recorded(db_session, clean_db, captured_events, tmp_path, fabric_env):
    project, shot, proxy_id, registry = await _ready_shot(db_session, tmp_path, image_provider="z-image",
                                                          video_provider="wan-2.2")
    result = await VideoGenerationService(db_session, registry=registry).generate(shot.id, physics_proxy_asset_id=proxy_id)
    await db_session.commit()
    assert len(result["candidates"]) == 3

    rows = (await db_session.execute(select(GpuJob).where(GpuJob.shot_id == str(shot.id)))).scalars().all()
    assert sorted(r.task for r in rows) == ["image", "image", "image", "video"]
    for r in rows:
        assert (r.backend, r.worker_id, r.gpu, r.adapter, r.status) == ("gpu", "home-4090", "NVIDIA GeForce RTX 4090", "mock", "done")
        assert r.precision in ("bf16", "fp8") and r.project_id == str(project.id) and r.gpu_seconds is not None
        assert r.cost_usd is not None and r.where == "NVIDIA GeForce RTX 4090"
    video = next(r for r in rows if r.task == "video")
    assert video.model == "wan-2.2" and video.precision == "fp8"     # 28 GB at bf16 doesn't fit a 24 GB card
    # the worker reports whether the model was already loaded: all three pictures first (Z-Image loads once and
    # stays loaded), then the clip (Wan 2.2 loads once)
    assert sum(1 for r in rows if r.task == "image" and r.warm) == 2

    kinds = fabric_env.types()
    assert kinds.count("GPU_JOB_QUEUED") == 4 and kinds.count("GPU_JOB_COMPLETED") == 4 and "GPU_JOB_STARTED" in kinds
    done = next(e for e in fabric_env.events if e.event_type.value == "GPU_JOB_COMPLETED")
    assert done.project_id == str(project.id) and done.payload["status"] == "done"

    # QA feeds the router: the score lands on the version's runs and in the learned performance
    qa = await QAService(db_session, registry=registry).run(shot.id)
    await db_session.commit()
    rows = (await db_session.execute(select(GpuJob).where(GpuJob.shot_id == str(shot.id)))).scalars().all()
    assert all(r.qa_score == pytest.approx(qa["score"]) for r in rows)
    learned = await fabric_service.load_performance()
    stats = learned[performance.key("z-image", "NVIDIA GeForce RTX 4090")]
    assert stats["runs"] == 3 and stats["ok"] == 3 and stats["unit_seconds"] > 0 and stats["avg_qa"] == pytest.approx(qa["score"])


@requires_db
@pytest.mark.asyncio
async def test_a_failing_worker_falls_back_and_the_failure_is_recorded(db_session, clean_db, captured_events, tmp_path,
                                                                      fabric_env, monkeypatch):
    from agentic_core.model_fabric import scheduler

    real = scheduler.run_on_worker
    calls = {"n": 0}

    async def flaky(placement, job, **kw):
        calls["n"] += 1
        if job.task == "video" and calls.get("failed") is None:
            calls["failed"] = True
            raise scheduler.WorkerJobError("CUDA out of memory")
        return await real(placement, job, **kw)

    monkeypatch.setattr(scheduler, "run_on_worker", flaky)
    _, shot, proxy_id, registry = await _ready_shot(db_session, tmp_path, image_provider="z-image", video_provider="wan-2.2")
    # only one place can run Wan 2.2 here (no fal.ai key, no ComfyUI server), so the error reaches the shot (the
    # workflow then gives that shot an animated still and a warning); the failed run is on record either way
    with pytest.raises(Exception, match="CUDA out of memory"):
        await VideoGenerationService(db_session, registry=registry).generate(shot.id, physics_proxy_asset_id=proxy_id)
    rows = (await db_session.execute(select(GpuJob).where(GpuJob.task == "video"))).scalars().all()
    assert [r.status for r in rows] == ["error"] and "CUDA out of memory" in rows[0].error
    assert "GPU_JOB_FAILED" in fabric_env.types()

    # with fal.ai set up as well, the same failure moves the clip to the next placement
    monkeypatch.setenv("FAL_KEY", "k")
    calls.pop("failed")
    seen = []

    async def fake_fal(endpoint, data, timeout=0):
        seen.append(endpoint)
        return {"video": {"url": "http://x/v.mp4"}}

    async def fake_download(url):
        return b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 32

    from agentic_core.models import fal_client
    monkeypatch.setattr(fal_client, "run", fake_fal)
    monkeypatch.setattr(fal_client, "download", fake_download)
    _, shot2, proxy2, registry2 = await _ready_shot(db_session, tmp_path, image_provider="z-image", video_provider="wan-2.2")
    await VideoGenerationService(db_session, registry=registry2).generate(shot2.id, physics_proxy_asset_id=proxy2)
    rows = (await db_session.execute(select(GpuJob).where(GpuJob.shot_id == str(shot2.id), GpuJob.task == "video")
                                     .order_by(GpuJob.created_at))).scalars().all()
    assert [(r.backend, r.status) for r in rows] == [("gpu", "error"), ("fal", "done")] and seen


@requires_db
def test_gpu_page_api(fabric_env, test_engine):
    from src.main import app

    with TestClient(app) as c:
        page = c.get("/api/v1/gpu").json()
        w = page["workers"][0]
        assert w["online"] and w["gpu"]["name"] == "NVIDIA GeForce RTX 4090" and "mock" in w["adapters"]
        assert page["limits"]["preference"] == "balanced" and page["tokenSet"]

        t = c.post("/api/v1/gpu/workers/home-4090/test").json()
        assert "RTX 4090" in t["summary"] and "wan-2.2" in t["summary"]

        plan = c.post("/api/v1/gpu/route", json={"task": "video", "seconds": 5}).json()
        top = plan["placements"][0]
        assert top["backend"] == "gpu" and top["worker_id"] == "home-4090" and top["reasons"]
        assert any(r["backend"] == "fal" for r in plan["rejected"])          # no FAL_KEY: explained, not hidden
        cheap = c.post("/api/v1/gpu/route", json={"task": "video", "seconds": 5,
                                                    "limits": {"max_cost_per_shot": 0.0001}}).json()
        assert not cheap["placements"] and any("per-shot limit" in r["why"] for r in cheap["rejected"])

        assert c.put("/api/v1/gpu/limits", json={"preference": "fastest"}).status_code == 400
        assert c.put("/api/v1/gpu/limits", json={"preference": "speed", "max_attempts": 2}).json()["max_attempts"] == 2
        assert c.post("/api/v1/gpu/workers", json={"name": "x", "url": "ftp://nope"}).status_code == 400
        added = c.post("/api/v1/gpu/workers", json={"name": "Pod", "url": "http://127.0.0.1:9", "cost_per_hour": 0.69}).json()
        pod = next(x for x in added if x["name"] == "Pod")
        assert not pod["online"] and "Can't reach" in pod["error"]
        assert len(c.delete(f"/api/v1/gpu/workers/{pod['id']}").json()) == 1

        proj = c.post("/api/v1/projects", json={"name": "P", "topic": "Volcanoes", "duration": 30,
                                                "aspect_ratio": "9:16", "generation_policy": {"preference": "quality"}}).json()
        assert proj["generation_policy"] == {"preference": "quality"}
        r = c.put(f"/api/v1/gpu/projects/{proj['id']}/limits", json={"max_cost_per_shot": 0.5, "preferred_model": "ltx-2.3"}).json()
        assert r["effective"]["max_cost_per_shot"] == 0.5 and r["effective"]["preference"] == "speed"
        assert c.put(f"/api/v1/gpu/projects/{proj['id']}/limits", json={"preferred_model": "nope"}).status_code == 422
        assert isinstance(c.get("/api/v1/gpu/jobs").json(), list)
        # a workflow uploaded in Settings is sent to the worker's ComfyUI backend
        wf = {"1": {"class_type": "CLIPTextEncode", "inputs": {"text": "{{PROMPT}}"}}}
        assert c.put("/api/v1/settings/models/wan-2.2/workflow", content=json.dumps(wf)).status_code == 200
        pushed = c.post("/api/v1/gpu/workers/home-4090/workflows").json()
        assert pushed["sent"] == ["wan-2.2"] and not pushed["failed"]
        assert "rows" in c.get("/api/v1/gpu/performance").json()


def _failing_qa() -> QAResult:
    return QAResult(shot_id="00000000-0000-0000-0000-000000000000", video_asset_id="00000000-0000-0000-0000-000000000001",
                    status=QAStatus.FAIL, score=0.3, confidence=0.9,
                    dimensions=[QADimensionResult(dimension=QADimension.VISUAL, score=0.3, confidence=1.0)])


def test_repair_ladder_respects_the_attempt_limit():
    assert build_repair_plan(_failing_qa(), attempt=1)["rung"] == "MICRO"
    assert build_repair_plan(_failing_qa(), attempt=2, max_attempts=3)["rung"] == "MACRO"
    assert build_repair_plan(_failing_qa(), attempt=1, max_attempts=1)["rung"] == "HUMAN_REQUIRED"
    assert build_repair_plan(_failing_qa(), attempt=1, max_attempts=2)["rung"] == "MICRO"
    assert build_repair_plan(_failing_qa(), attempt=2, max_attempts=2)["rung"] == "HUMAN_REQUIRED"


# ---------- Models page → Download (to this PC and onto a GPU worker) ----------
@pytest.fixture
def fake_hf(monkeypatch):
    """A tiny Hugging Face: /<repo>/resolve/main/<path>, with Range support."""
    import http.server

    blobs = {"split/model_fp8.safetensors": b"M" * 300_000, "split/model_bf16.safetensors": b"B" * 500_000,
             "split/vae.safetensors": b"V" * 2000, "split/lora.safetensors": b"L" * 1000}

    class H(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            path = self.path.split("/resolve/main/", 1)[-1]
            data = blobs.get(path)
            if data is None:
                self.send_response(404); self.end_headers(); return
            start = int(self.headers["Range"].split("=")[1].split("-")[0]) if self.headers.get("Range") else 0
            body = data[start:]
            self.send_response(206 if start else 200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    monkeypatch.setenv("HF_ENDPOINT", f"http://127.0.0.1:{srv.server_address[1]}")
    f = lambda p, folder: {"repo": "org/r", "path": p, "folder": folder, "size": len(blobs[p])}  # noqa: E731
    fake = {"wan-2.2": {"template": "t", "verified": True, "default": "fp8",
                        "variants": {"fp8": [f("split/model_fp8.safetensors", "diffusion_models")],
                                     "bf16": [f("split/model_bf16.safetensors", "diffusion_models")]},
                        "shared": [f("split/vae.safetensors", "vae")],
                        "optional": [{**f("split/lora.safetensors", "loras"), "label": "Speed LoRA", "recommended": True}]}}
    from agentic_core.model_fabric import downloads, model_files
    monkeypatch.setattr(model_files, "manifest", lambda: fake)
    downloads.JOBS.clear()
    yield blobs
    srv.shutdown()
    downloads.JOBS.clear()


def _wait_download(c, where, timeout=20):
    t = time.monotonic()
    while time.monotonic() - t < timeout:
        jobs = [j for j in c.get("/api/v1/downloads").json() if j["where"] == where]
        if jobs and jobs[0]["status"] not in ("queued", "running"):
            return jobs[0]
        time.sleep(0.1)
    raise AssertionError("download didn't finish")


@requires_db
def test_download_a_model_to_this_pc_and_to_a_gpu_worker(fabric_env, fake_hf, test_engine, tmp_path, monkeypatch):
    from src.main import app

    monkeypatch.setenv("AVOS_MODELS_DIR", str(tmp_path / "models"))
    monkeypatch.setenv("DOWNLOAD_ROOTS", str(tmp_path / "models"))
    with TestClient(app) as c:
        assert c.get("/api/v1/models").json()["models"][3]["download"] in (True, False)
        o = c.get("/api/v1/downloads/models/wan-2.2").json()
        assert o["recommended"] == "bf16"           # 24 GB worker: the full model fits easily here
        assert [v["key"] for v in o["variants"]] == ["bf16", "fp8"] and not any(v["complete"] for v in o["variants"])
        assert o["dest"] == str(tmp_path / "models")
        b = c.get("/api/v1/downloads/browse").json()
        assert b["path"] == str(tmp_path / "models") and b["writable"]
        assert c.get("/api/v1/downloads/browse", params={"path": str(tmp_path)}).status_code == 400   # outside the roots
        made = c.post("/api/v1/downloads/mkdir", json={"where": "local", "path": b["path"], "name": "comfy"}).json()["path"]

        job = c.post("/api/v1/downloads", json={"model": "wan-2.2", "variant": "fp8", "where": "local", "path": made,
                                               "extras": ["loras/lora.safetensors"]}).json()
        assert job["where"] == "local" and job["total"] == 300_000 + 2000 + 1000
        done = _wait_download(c, "local")
        assert done["status"] == "done", done
        assert (tmp_path / "models" / "comfy" / "diffusion_models" / "model_fp8.safetensors").stat().st_size == 300_000
        assert (tmp_path / "models" / "comfy" / "loras" / "lora.safetensors").exists()
        o = c.get("/api/v1/downloads/models/wan-2.2", params={"path": made}).json()
        assert next(v for v in o["variants"] if v["key"] == "fp8")["complete"]
        assert c.post("/api/v1/downloads", json={"model": "wan-2.2", "variant": "fp9"}).status_code == 400

        # straight onto the GPU worker, into its models folder (the worker runs in this test process: its own
        # DOWNLOAD_ROOTS would be the variable set above for "This PC")
        monkeypatch.delenv("DOWNLOAD_ROOTS")
        wb = c.get("/api/v1/downloads/browse", params={"where": "home-4090"}).json()
        assert wb["path"] == wb["default"]
        job = c.post("/api/v1/downloads", json={"model": "wan-2.2", "variant": "bf16", "where": "home-4090"}).json()
        assert job["where"] == "home-4090"
        done = _wait_download(c, "home-4090")
        assert done["status"] == "done", done
        ow = c.get("/api/v1/downloads/models/wan-2.2", params={"where": "home-4090"}).json()
        assert next(v for v in ow["variants"] if v["key"] == "bf16")["complete"] and ow["dest"] == wb["default"]
        assert c.delete(f"/api/v1/downloads/home-4090/{done['id']}").json() == {"ok": True}
