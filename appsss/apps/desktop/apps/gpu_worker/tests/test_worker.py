"""The GPU worker without a GPU: a pretend RTX 4090, the mock backend, a fake Wan2GP and the ComfyUI templating."""
import asyncio
import base64
import json
import sys
import time

import pytest
from fastapi.testclient import TestClient

from worker import config, gpu
from worker.adapters.base import JobSpec
from worker.adapters.comfyui import fill as comfy_fill
from worker.adapters.mock import MockAdapter
from worker.adapters.wan2gp import Wan2GPAdapter
from worker.app import create_app
from worker.jobs import Queue
from worker.vram import Residency

RTX4090 = '{"name": "NVIDIA GeForce RTX 4090", "vram_gb": 24, "compute_capability": "8.9"}'


@pytest.fixture(autouse=True)
def setup(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "FAKE_GPU", RTX4090)
    monkeypatch.setattr(config, "MOCK_SECONDS", 0.3)
    monkeypatch.setattr(config, "RESULTS", tmp_path / "results")
    monkeypatch.setattr(config, "TOKEN", None)
    monkeypatch.setattr(config, "PINNED", set())
    monkeypatch.setattr(gpu, "_smi", lambda: None)
    gpu._cache.update(t=0.0, gpu=None)
    yield


def client(adapters=None):
    return TestClient(create_app(Queue(adapters or {"mock": MockAdapter()})))


def wait(c, jid, timeout=10):
    t = time.monotonic()
    while time.monotonic() - t < timeout:
        s = c.get(f"/jobs/{jid}").json()
        if s["status"] in ("done", "error", "cancelled"):
            return s
        time.sleep(0.05)
    raise AssertionError("job didn't finish")


def job(**kw):
    return {"model": "wan-2.2", "adapter": "mock", "precision": "fp8", "task": "video", "prompt": "a fox",
            "width": 320, "height": 192, "seconds": 1, "fps": 8, "seed": 1, "vram_gb": 22, **kw}


def test_status_reports_gpu_precisions_and_backends():
    with client() as c:
        s = c.get("/status").json()
    assert s["gpu"]["name"] == "NVIDIA GeForce RTX 4090" and s["gpu"]["vram_gb"] == 24
    assert s["supports"]["bf16"] and s["supports"]["fp8"] and not s["supports"]["fp4"]   # Ada: fp8 yes, fp4 no
    mock = s["adapters"]["mock"]
    assert mock["ready"] and "wan-2.2" in mock["models"] and "fp4" not in mock["precisions"]
    assert s["status"] == "ready" and s["queue_depth"] == 0


def test_blackwell_gets_fp4(monkeypatch):
    monkeypatch.setattr(config, "FAKE_GPU", '{"name": "NVIDIA GeForce RTX 5090", "vram_gb": 32, "compute_capability": "12.0"}')
    with client() as c:
        s = c.get("/status").json()
    assert s["supports"]["fp4"] and "fp4" in s["adapters"]["mock"]["precisions"]


def test_job_runs_keeps_model_warm_and_evicts_lru():
    with client() as c:
        first = wait(c, c.post("/jobs", json=job()).json()["id"])
        assert first["status"] == "done" and not first["warm"] and first["gpu_seconds"] > 0
        r = c.get(f"/jobs/{first['id']}/result")
        assert r.status_code == 200 and r.headers["content-type"] == "video/mp4" and len(r.content) > 100
        second = wait(c, c.post("/jobs", json=job(seed=2)).json()["id"])
        assert second["warm"] and second["load_seconds"] is None            # same model + precision: no reload
        third = wait(c, c.post("/jobs", json=job(model="qwen-image", task="image", want="image", vram_gb=14)).json()["id"])
        assert third["evicted"] == ["wan-2.2 (fp8)"]                        # 22 + 14 GB don't fit in 24 GB
        assert c.get(f"/jobs/{third['id']}/result").content[:4] == b"\x89PNG"
        loaded = c.get("/status").json()["loaded_models"]
        assert [m["model"] for m in loaded] == ["qwen-image"]
        assert c.delete(f"/jobs/{first['id']}").json()["forgotten"]
        assert c.get(f"/jobs/{first['id']}").status_code == 404


def test_precision_change_reloads_and_pinned_models_stay(monkeypatch):
    monkeypatch.setattr(config, "PINNED", {"ltx-2.3"})
    with client() as c:
        wait(c, c.post("/jobs", json=job(model="ltx-2.3", vram_gb=10)).json()["id"])
        wait(c, c.post("/jobs", json=job(model="wan-2.2", vram_gb=11)).json()["id"])
        s = wait(c, c.post("/jobs", json=job(model="wan-2.2", precision="int8", vram_gb=11)).json()["id"])
        assert s["evicted"] == ["wan-2.2 (fp8)"] and not s["warm"]
        big = wait(c, c.post("/jobs", json=job(model="infinitetalk", vram_gb=20)).json()["id"])
        assert "ltx-2.3 (fp8)" not in big["evicted"]                       # pinned: never evicted
        models = {m["model"] for m in c.get("/status").json()["loaded_models"]}
        assert "ltx-2.3" in models


def test_queue_order_and_cancel():
    with client() as c:
        a = c.post("/jobs", json=job()).json()
        b = c.post("/jobs", json=job(seed=5)).json()
        assert b["position"] in (0, 1)
        assert c.delete(f"/jobs/{b['id']}").json()["cancelled"]
        assert wait(c, a["id"])["status"] == "done"
        assert c.get(f"/jobs/{b['id']}").json()["status"] == "cancelled"


def test_unknown_backend_and_token(monkeypatch):
    with client() as c:
        assert c.post("/jobs", json=job(adapter="wan2gp")).status_code == 400
        monkeypatch.setattr(config, "TOKEN", "s3cret")
        assert c.get("/status").status_code == 401
        assert c.get("/status", headers={"Authorization": "Bearer s3cret"}).status_code == 200
        assert c.get("/health").status_code == 200


def test_residency_math():
    unloaded = []

    async def unload(r):
        unloaded.append(r.model)

    res = Residency(total_gb=lambda: 24, free_gb=lambda: None, unload=unload, reserve_gb=1.5)
    res.loaded("a", "x", "fp8", 10)
    res.loaded("b", "x", "fp8", 8)
    res.touch("a", "x")                                   # b is now least recently used
    asyncio.run(res.make_room("c", "x", "fp8", 10))
    assert unloaded == ["b"] and res.available_gb() == pytest.approx(12.5)


def test_comfyui_template_gets_weight_dtype():
    wf = {"1": {"inputs": {"weight_dtype": "{{WEIGHT_DTYPE}}", "text": "{{PROMPT}}, cinematic", "seed": "{{SEED}}"}}}
    out = comfy_fill(wf, {"{{WEIGHT_DTYPE}}": "fp8_e4m3fn_fast", "{{PROMPT}}": "a fox", "{{SEED}}": 7})
    assert out == {"1": {"inputs": {"weight_dtype": "fp8_e4m3fn_fast", "text": "a fox, cinematic", "seed": 7}}}


FAKE_WGP = r'''
import json, sys, os, time
args = sys.argv[1:]
settings = json.load(open(args[args.index("--process") + 1]))
out = args[args.index("--output-dir") + 1]
json.dump({"args": args, "settings": settings}, open(os.environ["WGP_LOG"], "w"))
for i in range(1, 5):
    print(f"{i*25}%|##| {i}/4 [00:01<00:01]", flush=True)
open(os.path.join(out, "result.mp4"), "wb").write(b"\x00\x00\x00\x18ftypmp42" + b"0" * 64)
'''


def test_wan2gp_runs_headless_with_the_routers_choices(monkeypatch, tmp_path):
    wdir, tdir = tmp_path / "Wan2GP", tmp_path / "templates"
    wdir.mkdir(), tdir.mkdir()
    (wdir / "wgp.py").write_text(FAKE_WGP)
    (tdir / "wan-2.2.json").write_text(json.dumps({
        "model_type": "i2v_2_2", "prompt": "{{PROMPT}}", "seed": "{{SEED}}", "resolution": "{{RESOLUTION}}",
        "video_length": "{{FRAMES}}", "image_start": "{{IMAGE}}", "num_inference_steps": 20}))
    monkeypatch.setattr(config, "WAN2GP_DIR", wdir)
    monkeypatch.setattr(config, "WAN2GP_TEMPLATES", tdir)
    monkeypatch.setattr(config, "WAN2GP_PYTHON", sys.executable)
    monkeypatch.setenv("WGP_LOG", str(tmp_path / "log.json"))
    a = Wan2GPAdapter()
    assert asyncio.run(a.ready()) == (True, None) and a.models() == ["wan-2.2"]
    steps = []

    async def progress(f, s):
        steps.append(f)

    spec = JobSpec.from_body(job(adapter="wan2gp", precision="bf16", attention="sage2", frames=81, width=1280, height=720),
                             {"image": b"\x89PNG fake"})
    data, ext = asyncio.run(a.run(spec, progress))
    log = json.load(open(tmp_path / "log.json"))
    assert ext == "mp4" and data.startswith(b"\x00\x00\x00\x18ftyp")
    assert log["settings"]["prompt"] == "a fox" and log["settings"]["resolution"] == "1280x720"
    assert log["settings"]["video_length"] == 81 and log["settings"]["seed"] == 1
    assert log["settings"]["image_start"].endswith("input_image.png") and log["settings"]["model_type"] == "i2v_2_2"
    args = log["args"]
    assert args[args.index("--attention") + 1] == "sage2" and args[args.index("--quantize-transformer") + 1] == "False"
    assert steps[-1] == 1.0


def test_inputs_must_be_base64():
    with client() as c:
        bad = c.post("/jobs", json=job(inputs={"image": "***"}))
        assert bad.status_code == 400
        ok = c.post("/jobs", json=job(inputs={"image": base64.b64encode(b"x").decode()}))
        assert ok.status_code == 200


def test_avos_can_push_a_workflow(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "COMFYUI_WORKFLOWS", tmp_path / "wf")
    wf = {"1": {"class_type": "CLIPTextEncode", "inputs": {"text": "{{PROMPT}}"}}}
    with client() as c:
        assert c.put("/workflows/wan-2.2", json={"nodes": [], "links": []}).status_code == 400
        assert c.put("/workflows/..%2Fx", json=wf).status_code in (400, 404)
        assert c.put("/workflows/wan-2.2", json=wf).json() == {"ok": True, "model": "wan-2.2"}
    assert json.loads((tmp_path / "wf" / "wan-2.2.json").read_text()) == wf


def test_urgent_jobs_jump_the_queue():
    async def go():
        q = Queue({"mock": MockAdapter()})
        jobs = [q.submit(JobSpec.from_body({**job(), "prompt": f"p{i}", "priority": p}, {})) for i, p in enumerate((5, 5, 9, 0))]
        assert [j.spec.prompt for j in q.waiting()] == ["p3", "p0", "p1", "p2"]
        assert q.position(jobs[3]) == 0 and q.position(jobs[2]) == 3
        assert JobSpec.from_body({**job(), "priority": 99}, {}).priority == 9
    asyncio.run(go())
