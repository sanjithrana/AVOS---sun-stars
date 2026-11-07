"""Open models in the Animations tab (shared AVOS catalog): AI backdrops with a chosen model, AI settings, and the
AI finish over a whole film, against a simulated fal.ai (no network in tests)."""
from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from studio import config, finish, models
from studio.render import images
from studio.server import app

from .conftest import needs_ffmpeg

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 64


def _mp4(path: Path, seconds: float, color: str = "red", size: str = "320x568", audio: bool = False) -> bytes:
    args = ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"color=c={color}:s={size}:r=24:d={seconds}"]
    if audio:
        args += ["-f", "lavfi", "-i", f"sine=f=330:d={seconds}", "-c:a", "aac", "-shortest"]
    subprocess.run(args + ["-c:v", "libx264", "-pix_fmt", "yuv420p", str(path)], check=True)
    return path.read_bytes()


class FakeFal:
    def __init__(self, video: bytes | None = None, fail_on: int | None = None):
        self.jobs: list[tuple[str, dict]] = []
        self.video, self.fail_on, self.polls = video, fail_on, 0

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if request.url.host == "files.fal.media":
            return httpx.Response(200, content=PNG if path.endswith(".png") else self.video, request=request)
        assert request.headers["authorization"] == "Key test-key"
        if request.method == "POST":
            self.jobs.append((path.strip("/"), json.loads(request.content)))
            if self.fail_on is not None and len(self.jobs) == self.fail_on:
                return httpx.Response(422, json={"detail": "bad input"})
            return httpx.Response(200, json={"request_id": "r"})
        if path.endswith("/status"):
            return httpx.Response(200, json={"status": "COMPLETED"})
        ep = self.jobs[-1][0]
        if ep.endswith(("turbo", "qwen-image", "schnell", "flux-pro/v1.1")):
            return httpx.Response(200, json={"images": [{"url": "https://files.fal.media/o.png"}]})
        return httpx.Response(200, json={"video": {"url": "https://files.fal.media/o.mp4"}})


@pytest.fixture
def fal(monkeypatch):
    def install(fake: FakeFal) -> FakeFal:
        monkeypatch.setenv("FAL_KEY", "test-key")
        real = httpx.Client
        monkeypatch.setattr(models.httpx, "Client", lambda *a, **k: real(*a, **{**k, "transport": httpx.MockTransport(fake.handler)}))
        monkeypatch.setattr(models.httpx, "get", lambda url, **k: fake.handler(httpx.Request("GET", url)))
        return fake
    return install


def test_catalog_is_shared_with_the_facts_tab():
    assert models.catalog_path() and models.catalog_path().name == "catalog.json"
    assert {m["id"] for m in models.catalog()["models"]} >= {"z-image", "wan-vace", "scail-2"}
    st = models.status()
    assert [m["id"] for m in st["images"]] == ["z-image", "qwen-image", "flux-schnell"]
    assert [m["id"] for m in st["finish"]] == ["wan-vace", "wan-2.2-animate", "scail-2", "ltx-2.3"]
    assert not any(m["ready"] for m in st["finish"]) and "fal.ai key" in st["finish"][0]["why"]
    assert models.route_image('a shop sign that says "OPEN"')[0] == "qwen-image"
    assert models.frames("wan-vace", 3) == 81 and models.frames("ltx-2.3", 3) == 81


def test_ai_backdrop_uses_the_chosen_model_then_falls_back(fal, monkeypatch, tmp_path):
    fake = fal(FakeFal())
    monkeypatch.setenv("STUDIO_IMAGE_MODEL", "best")
    out = images.generate_plate("empty city street at night, no text", tmp_path / "a.jpg", 1280, 720)
    assert out and out.read_bytes() == PNG, images.LAST_ERROR
    ep, payload = fake.jobs[-1]
    assert ep == "fal-ai/z-image/turbo" and payload["image_size"] == {"width": 1280, "height": 720}
    ok, detail = images.images_status()
    assert ok and "Z-Image" in detail
    # a picture with a sign goes to Qwen-Image
    images.generate_plate('a bakery with a sign that says "BREAD"', tmp_path / "b.jpg", 1280, 720)
    assert fake.jobs[-1][0] == "fal-ai/qwen-image"
    # the chosen model fails -> the free chain still gives a picture (here: Pollinations, faked)
    monkeypatch.setenv("STUDIO_IMAGE_MODEL", "flux-schnell")
    fake.fail_on = len(fake.jobs) + 1
    monkeypatch.setattr(images.httpx, "get", lambda url, **k: httpx.Response(200, content=PNG, headers={"content-type": "image/jpeg"}))
    assert images.generate_plate("a park", tmp_path / "c.jpg", 640, 360)
    assert "flux-schnell" in images.LAST_ERROR[str(tmp_path / "c.jpg")]


def test_ai_settings_save_model_choices():
    with TestClient(app) as c:
        info = c.post("/api/agents/settings", json={"render": {"imageModel": "qwen-image"},
                                                    "models": {"falKey": "fal-test", "comfyuiUrl": "http://gpu:8188"}}).json()
        assert info["render"]["imageModel"] == "qwen-image"
        assert info["models"]["fal"] and info["models"]["comfyui"] == "http://gpu:8188"
        assert next(m for m in info["models"]["finish"] if m["id"] == "wan-vace")["ready"]        # fal.ai key set
        scail = next(m for m in info["models"]["finish"] if m["id"] == "scail-2")
        assert not scail["ready"] and "Upload its" in scail["why"]                              # GPU server only
        assert c.post("/api/agents/settings", json={"render": {"imageModel": "dall-e"}}).status_code == 400
        assert c.post("/api/agents/settings", json={"models": {"comfyuiUrl": "gpu:8188"}}).status_code == 400
        c.post("/api/agents/settings", json={"render": {"imageModel": "free"}, "models": {"falKey": "", "comfyuiUrl": ""}})
    assert json.loads(config.SECRETS_PATH.read_text()).get("FAL_KEY") is None


def _film(tmp_path: Path) -> Path:
    """A finished two-shot project: shots in build/shots, the film with its soundtrack in out/video.mp4."""
    d = config.PROJECTS / f"finish-{int(time.time() * 1000)}"
    (d / "build" / "shots").mkdir(parents=True)
    (d / "out").mkdir()
    plan = {"engine": "anime-cel", "format": {"width": 320, "height": 568, "fps": 24, "duration_s": 3.0},
            "shots": [{"id": "S1", "start_s": 0, "end_s": 1.5, "summary": "a girl looks at the moon", "action": "she reaches up"},
                      {"id": "S2", "start_s": 1.5, "end_s": 3.0, "summary": "the moon smiles", "action": "it winks"}]}
    (d / "plan.json").write_text(json.dumps(plan))
    (d / "job.json").write_text(json.dumps({"id": d.name, "title": "t", "agent": "builtin", "lang": "en", "stage": "done",
                                            "chat": [], "log": [], "needs": [], "waived": [], "pipeline": {}, "settings": {}}))
    _mp4(d / "build" / "shots" / "S1.mp4", 1.85, "red")
    _mp4(d / "build" / "shots" / "S2.mp4", 1.85, "blue")
    _mp4(d / "out" / "video.mp4", 3.0, "red", audio=True)
    return d


def _wait(c: TestClient, jid: str) -> dict:
    for _ in range(300):
        st = c.get(f"/api/projects/{jid}").json()["finish"]
        if st and st["state"] != "running":
            return st
        time.sleep(0.1)
    raise AssertionError("AI finish didn't end")


def _probe(f: Path) -> dict:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type,width,height",
                        "-of", "json", str(f)], capture_output=True, text=True)
    return json.loads(r.stdout)


@needs_ffmpeg
def test_ai_finish_restyles_every_shot_and_keeps_timing_and_sound(fal, tmp_path):
    fake = fal(FakeFal(video=_mp4(tmp_path / "ai.mp4", 5.0, "green", "480x832")))   # the model returns 5 s at its own size
    d = _film(tmp_path)
    with TestClient(app) as c:
        assert c.post(f"/api/projects/{d.name}/finish", json={"model": "nope"}).status_code == 400
        assert "GPU server" in c.post(f"/api/projects/{d.name}/finish", json={"model": "scail-2"}).json()["error"]
        r = c.post(f"/api/projects/{d.name}/finish", json={"model": "wan-vace"})
        assert r.status_code == 200 and r.json()["finish"]["total"] == 2
        st = _wait(c, d.name)
    assert st["state"] == "done" and st["video"] == "out/video_ai.mp4" and all(v["ok"] for v in st["shots"].values())
    # shots run in parallel now: find shot S1's request
    ep, payload = next(j for j in fake.jobs if "a girl looks at the moon" in j[1].get("prompt", ""))
    assert len(fake.jobs) == 2
    assert ep == "fal-ai/wan-vace-14b" and payload["task"] == "depth"
    assert payload["video_url"].startswith("data:video/mp4;base64,") and payload["ref_image_urls"][0].startswith("data:image/png")
    assert "a girl looks at the moon" in payload["prompt"] and "anime" in payload["prompt"]
    info = _probe(d / "out" / "video_ai.mp4")
    assert abs(float(info["format"]["duration"]) - 3.0) < 0.15                                   # same length as the film
    assert {s["codec_type"] for s in info["streams"]} == {"video", "audio"}                      # soundtrack kept
    v = next(s for s in info["streams"] if s["codec_type"] == "video")
    assert (v["width"], v["height"]) == (320, 568)                                              # same frame size
    assert (d / "out" / "video.mp4").exists()                                                   # engine film untouched


@needs_ffmpeg
def test_ai_finish_keeps_the_engine_shot_when_one_fails(fal, tmp_path, monkeypatch):
    monkeypatch.setenv("FINISH_CONCURRENCY", "1")        # one at a time, so "the second request" is shot S2
    fal(FakeFal(video=_mp4(tmp_path / "ai.mp4", 2.0, "green"), fail_on=2))
    d = _film(tmp_path)
    with TestClient(app) as c:
        c.post(f"/api/projects/{d.name}/finish", json={"model": "wan-2.2-animate"})
        st = _wait(c, d.name)
    assert st["state"] == "done" and st["shots"]["S1"]["ok"] and not st["shots"]["S2"]["ok"]
    assert "422" in st["shots"]["S2"]["error"]
    assert abs(float(_probe(d / "out" / "video_ai.mp4")["format"]["duration"]) - 3.0) < 0.15


def test_ai_finish_needs_a_finished_film(fal, tmp_path):
    fal(FakeFal())
    d = config.PROJECTS / "finish-empty"
    d.mkdir(parents=True, exist_ok=True)
    assert "Finish the film first" in finish.check(d, "wan-vace")


# ---------- models and keys from the AVOS Settings page (shared with Facts) ----------
from studio import avos_settings  # noqa: E402
from studio import llm as llm_mod  # noqa: E402


@pytest.fixture
def shared(monkeypatch, tmp_path):
    monkeypatch.setenv("AVOS_SETTINGS_FILE", str(tmp_path / "avos.json"))
    avos_settings._ORIG.clear(); avos_settings._SET.clear()
    yield
    avos_settings.save(avos_settings._empty())
    avos_settings._ORIG.clear(); avos_settings._SET.clear()


def test_settings_page_models_and_keys_show_up_in_animations(fal, shared, tmp_path):
    fake = fal(FakeFal())
    os.environ.pop("FAL_KEY", None)
    avos_settings.set_env({"FAL_KEY": "test-key", "DS_KEY": "sk-1"})          # saved on the Settings page
    avos_settings.upsert_model({"id": "my-flux", "name": "My FLUX", "task": "image", "kind": "fal", "endpoint": "fal-ai/flux-pro/v1.1",
                                "inputs": {"prompt": "{{prompt}}", "image_size": "landscape_16_9"}})
    avos_settings.upsert_model({"id": "my-video", "name": "My video", "task": "video", "kind": "replicate", "endpoint": "me/vid"})
    avos_settings.upsert_model({"id": "deepseek", "name": "DeepSeek", "task": "llm", "kind": "openai",
                                "base_url": "http://ds.local/v1", "model": "deepseek-chat", "key_env": "DS_KEY"})
    with TestClient(app) as c:
        info = c.get("/api/agents/info").json()
        crew = next(a for a in info["agents"] if a["id"] == "deepseek")
        assert crew["ready"] and crew["tier"] == "custom" and crew["model"] == "deepseek-chat"
        assert "my-flux" in [m["id"] for m in info["models"]["images"]]
        vid = next(m for m in info["models"]["finish"] if m["id"] == "my-video")
        assert not vid["ready"] and "REPLICATE_API_TOKEN" in vid["why"]
        # picking it for backdrops, then a key saved here goes to the shared Settings file
        info = c.post("/api/agents/settings", json={"render": {"imageModel": "my-flux"}, "models": {"comfyuiUrl": "http://gpu:8188"}}).json()
        assert info["render"]["imageModel"] == "my-flux"
        c.post("/api/agents/settings", json={"agent": "groq", "key": "gsk_shared"})
    assert os.environ["GROQ_API_KEY"] == "gsk_shared" and os.environ["COMFYUI_URL"] == "http://gpu:8188"
    saved = json.loads((tmp_path / "avos.json").read_text())
    assert saved["env"]["GROQ_API_KEY"] == "gsk_shared" and saved["gpu"]["comfyui_url"] == "http://gpu:8188"
    out = images.generate_plate("a park, no text", tmp_path / "p.jpg", 1280, 720)
    assert out, images.LAST_ERROR
    assert fake.jobs[-1] == ("fal-ai/flux-pro/v1.1", {"prompt": "a park, no text", "image_size": "landscape_16_9"})


def test_a_text_model_from_settings_runs_as_a_crew(shared, monkeypatch, tmp_path):
    import asyncio

    avos_settings.set_env({"DS_KEY": "sk-1"})
    avos_settings.upsert_model({"id": "deepseek", "name": "DeepSeek", "task": "llm", "kind": "openai",
                                "base_url": "http://ds.local/v1", "model": "deepseek-chat", "key_env": "DS_KEY"})
    seen = {}

    def handler(req):
        seen.update(url=str(req.url), body=json.loads(req.content), auth=req.headers["authorization"])
        chunk = 'data: {"choices":[{"delta":{"content":"{\\"ok\\": true}"}}]}\n\ndata: [DONE]\n\n'
        return httpx.Response(200, content=chunk.encode(), headers={"content-type": "text/event-stream"})

    real = httpx.AsyncClient
    monkeypatch.setattr(llm_mod.httpx, "AsyncClient", lambda *a, **k: real(*a, **{**k, "transport": httpx.MockTransport(handler)}))

    class Abort:
        aborted = False

    crew = llm_mod.Crew("deepseek", "j", "fresh", "director", lambda ev: None, Abort(), tmp_path)
    assert asyncio.run(crew.ask_json("You plan videos.", "Plan it")) == {"ok": True}
    assert seen["url"] == "http://ds.local/v1/chat/completions" and seen["body"]["model"] == "deepseek-chat" and seen["auth"] == "Bearer sk-1"


def test_colibri_runs_as_a_local_crew(monkeypatch, tmp_path):
    """Colibrì (a huge MoE model streamed from SSD on the CPU) is an OpenAI-compatible server on port 8000: the crew asks
    it which model is loaded and uses it; the AI settings show it ready when it answers."""
    import asyncio

    monkeypatch.setenv("COLIBRI_URL", "http://colibri.local:8000/")
    seen = {}

    def handler(req):
        if req.url.path == "/v1/models":
            return httpx.Response(200, json={"data": [{"id": "glm-5.2"}]})
        seen.update(url=str(req.url), body=json.loads(req.content))
        chunk = 'data: {"choices":[{"delta":{"content":"{\\"ok\\": 1}"}}]}\n\ndata: [DONE]\n\n'
        return httpx.Response(200, content=chunk.encode(), headers={"content-type": "text/event-stream"})

    real = httpx.AsyncClient
    monkeypatch.setattr(llm_mod.httpx, "AsyncClient", lambda *a, **k: real(*a, **{**k, "transport": httpx.MockTransport(handler)}))

    class Abort:
        aborted = False

    assert "colibri" in llm_mod.agent_kinds() and llm_mod.local_url("colibri") == "http://colibri.local:8000"
    crew = llm_mod.Crew("colibri", "j", "fresh", "writer", lambda ev: None, Abort(), tmp_path)
    assert asyncio.run(crew.ask_json("You write.", "Go")) == {"ok": 1}
    assert seen["url"] == "http://colibri.local:8000/v1/chat/completions" and seen["body"]["model"] == "glm-5.2"
    info = next(a for a in asyncio.run(llm_mod.agents_info())["agents"] if a["id"] == "colibri")
    assert info["ready"] and info["model"] == "glm-5.2" and "colibri" in info["fix"].lower()


# ---------- AVOS GPU workers (Settings → GPU workers, shared with Facts) ----------
@pytest.fixture(scope="module")
def gpu_worker_url(tmp_path_factory):
    """A real AVOS GPU worker in a thread: the mock backend on a pretend RTX 4090 (no GPU needed)."""
    import socket
    import sys
    import threading

    import uvicorn

    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "gpu_worker"))
    from worker import config as wconfig, gpu as wgpu
    from worker.adapters.mock import MockAdapter
    from worker.app import create_app
    from worker.jobs import Queue

    wconfig.FAKE_GPU = '{"name": "NVIDIA GeForce RTX 4090", "vram_gb": 24, "compute_capability": "8.9"}'
    wconfig.MOCK_SECONDS, wconfig.TOKEN = 0.2, "tok"
    wconfig.RESULTS = tmp_path_factory.mktemp("gw") / "results"
    wgpu._smi = lambda: None
    wgpu._cache.update(t=0.0, gpu=None)
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(create_app(Queue({"mock": MockAdapter()})), host="127.0.0.1", port=port, log_level="warning"))
    t = threading.Thread(target=server.run, daemon=True)
    t.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True


@needs_ffmpeg
def test_ai_finish_and_backdrops_run_on_a_gpu_worker(shared, gpu_worker_url, monkeypatch, tmp_path):
    from studio import gpu

    for k in ("FAL_KEY", "COMFYUI_URL", "MODEL_BACKEND"):
        monkeypatch.delenv(k, raising=False)
    gpu._cache.clear()
    avos_settings.set_env({"GPU_WORKER_TOKEN": "tok"})
    avos_settings.upsert_worker({"id": "home", "name": "Home 4090", "url": gpu_worker_url})
    st = models.status()
    vace = next(m for m in st["finish"] if m["id"] == "wan-vace")
    assert vace["ready"] and vace["backend"] == "gpu"
    pl = gpu.pick("wan-vace", models.get("wan-vace").get("fabric"))
    assert pl and pl.adapter == "mock" and pl.precision == "fp8"          # 32 GB at bf16 doesn't fit 24 GB
    assert models.backend_for("z-image") == "gpu"

    png = models.image("z-image", "a quiet park", 1280, 720, seed=3)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"

    d = _film(tmp_path)
    with TestClient(app) as c:
        r = c.post(f"/api/projects/{d.name}/finish", json={"model": "wan-vace"})
        assert r.status_code == 200, r.text
        fin = _wait(c, d.name)
    assert fin["state"] == "done" and all(v["ok"] for v in fin["shots"].values()), fin
    assert abs(float(_probe(d / "out" / "video_ai.mp4")["format"]["duration"]) - 3.0) < 0.15

    avos_settings.set_env({"GPU_WORKER_TOKEN": "wrong"})
    gpu._cache.clear()
    assert "wrong GPU_WORKER_TOKEN" in models.available("wan-vace")["gpu"]


def test_a_retired_groq_model_is_replaced_automatically(shared, monkeypatch, tmp_path):
    """Groq shut Llama 3.3 down (model_not_found): an old saved choice is upgraded, and any other model the provider
    drops is swapped at call time for one it still lists, then remembered."""
    import asyncio

    from studio import config as sconfig

    monkeypatch.setenv("GROQ_API_KEY", "gsk-test")
    monkeypatch.setenv("STUDIO_GROQ_MODEL", "llama-3.3-70b-versatile")
    assert llm_mod.model_of("groq") == "openai/gpt-oss-120b"            # known retirement: upgraded silently
    monkeypatch.setenv("STUDIO_GROQ_MODEL", "some-vanished-model")
    saved = {}
    monkeypatch.setattr(sconfig, "save_secrets", lambda upd: saved.update(upd) or upd)
    calls = []

    def handler(req):
        if req.url.path.endswith("/models"):
            return httpx.Response(200, json={"data": [{"id": "whisper-large-v3"}, {"id": "qwen/qwen3.8-27b"},
                                                      {"id": "openai/gpt-oss-120b"}]})
        model = json.loads(req.content)["model"]
        calls.append(model)
        if model == "some-vanished-model":
            return httpx.Response(404, json={"error": {"message": f"The model `{model}` does not exist", "code": "model_not_found"}})
        chunk = 'data: {"choices":[{"delta":{"content":"{\\"ok\\": 1}"}}]}\n\ndata: [DONE]\n\n'
        return httpx.Response(200, content=chunk.encode(), headers={"content-type": "text/event-stream"})

    real = httpx.AsyncClient
    monkeypatch.setattr(llm_mod.httpx, "AsyncClient", lambda *a, **k: real(*a, **{**k, "transport": httpx.MockTransport(handler)}))
    logs = []

    class Abort:
        aborted = False

    crew = llm_mod.Crew("groq", "j", "fresh", "director", logs.append, Abort(), tmp_path)
    assert asyncio.run(crew.ask_json("You plan videos.", "Plan it")) == {"ok": 1}
    assert calls == ["some-vanished-model", "openai/gpt-oss-120b"]
    assert saved == {"STUDIO_GROQ_MODEL": "openai/gpt-oss-120b"}
    assert any("switched to openai/gpt-oss-120b" in (e.get("text") or "") for e in logs)


def test_a_broke_fal_account_is_skipped_and_the_next_option_draws(fal, shared, monkeypatch):
    """fal.ai answering 'Exhausted balance' marks fal.ai as skipped (shared with the Models page), every model says why,
    and a Series picture falls through to the next option instead of failing."""
    from studio import provider_health as PH
    from studio.series import media

    class Broke(FakeFal):
        def handler(self, request):
            if request.method == "POST":
                self.jobs.append((request.url.path.strip("/"), json.loads(request.content)))
                return httpx.Response(403, json={"detail": "User is locked. Reason: Exhausted balance. Top up your balance at fal.ai/dashboard/billing."})
            return super().handler(request)
    fake = fal(Broke())
    PH.clear()
    assert models.ready("z-image")[0]
    with pytest.raises(models.ModelUnavailable) as e:
        models.image("z-image", "a park", 512, 512, 1)
    assert "no credit left" in str(e.value) and "Exhausted balance" in str(e.value)
    assert "no credit left" in models.available("qwen-image")["fal"] and not models.ready("wan-2.2")[0]
    assert "fal" in PH.snapshot() and len(fake.jobs) == 1
    drawn = {}

    def free_chain(prompt, out, w, h):
        out.write_bytes(PNG)
        drawn["free"] = True
        return out
    monkeypatch.setattr("studio.render.images.generate_plate", free_chain)
    data, mid = media._t2i("a park", 512, 512, 1)
    assert data == PNG and mid == "free picture chain" and drawn["free"] and len(fake.jobs) == 1     # fal.ai not asked again
    monkeypatch.setenv("FAL_KEY", "a-new-key")                                                       # a new key: tried again
    assert PH.down("fal") is None
    PH.clear()


def test_clips_run_on_fal_when_there_is_no_gpu(fal, tmp_path):
    fake = fal(FakeFal(video=b"MP4"))
    out = models.run_model("wan-2.2", task="video", want="video", prompt="she waves", w=1280, h=720, seconds=4.0, seed=3,
                           inputs={"image": PNG})
    assert out == b"MP4"
    ep, body = fake.jobs[-1]
    assert ep == "fal-ai/wan/v2.2-a14b/image-to-video" and body["num_frames"] == 65 and body["image_url"].startswith("data:image/png")
    models.run_model("infinitetalk", task="avatar", want="video", prompt="talks", seconds=2.0, inputs={"image": PNG, "audio": b"RIFF0000WAVE"})
    ep, body = fake.jobs[-1]
    assert ep == "fal-ai/infinitalk" and body["audio_url"].startswith("data:audio/wav") and body["num_frames"] == 53


def test_your_model_choices_per_step(shared, monkeypatch, tmp_path):
    """Per film / series: the model and the place for each step; Auto keeps the usual order."""
    from studio.series import media
    monkeypatch.setenv("FAL_KEY", "k")
    with TestClient(app) as c:
        sid = c.post("/api/series", data={"title": "Picks", "crew": "builtin", "partPlan": "0.25", "cast": "Raju - a boy"}).json()["id"]
        steps = {x["step"]: x for x in c.get(f"/api/series/{sid}/models").json()["steps"]}
        assert set(steps) == {"pictures", "motion", "lipsync", "lines", "sfx", "music"} and steps["motion"]["model"] == "auto"
        wan = next(o for o in steps["motion"]["options"] if o["id"] == "wan-2.2")
        assert wan["ready"] and wan["backends"]["fal"]["why"] is None and "comfyui" in wan["backends"]
        assert any(o["id"] == "off" for o in steps["music"]["options"]) and any(o["id"] == "edge" for o in steps["lines"]["options"])
        r = c.patch(f"/api/series/{sid}", json={"models": {"motion": {"model": "ltx-2.3", "backend": "fal"}, "music": {"model": "off"},
                                                           "bogus": {"model": "x"}}})
        s = r.json()["series"]
        assert s["settings"]["models"] == {"motion": {"model": "ltx-2.3", "backend": "fal"}, "music": {"model": "off", "backend": "auto"}}
        assert media.ordered(s, "motion", ["wan-2.2", "ltx-2.3"]) == ["ltx-2.3", "wan-2.2"] and media.where(s, "motion", "ltx-2.3") == "fal"
        assert media.where(s, "motion", "wan-2.2") is None and media.music(s, "x", 10, "t")[1]["note"] == "music off (your choice)"
        c.post(f"/api/series/{sid}/cancel")
