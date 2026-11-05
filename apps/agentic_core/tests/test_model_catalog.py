"""The AVOS model catalog: routing, backends, and every catalog model against simulated fal.ai and ComfyUI servers
(no network or GPU in tests: these check the requests we send and how results come back)."""
import asyncio
import json

import httpx
import pytest

from agentic_core.models import catalog, fal_client
from agentic_core.models.image import catalog_image
from agentic_core.models.image.catalog_image import BestImageProvider, CatalogImageProvider, fal_image_input, fit_size
from agentic_core.models.image.factory import get_image_provider
from agentic_core.models.video import catalog_video, comfyui_provider
from agentic_core.models.video.catalog_video import (BestVideoProvider, CatalogVideoProvider, fal_video_input,
                                                      frames_for)
from agentic_core.models.video.factory import IMAGE_TO_VIDEO_PROVIDERS, get_video_provider

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 32
WAV = b"RIFF\x00\x00\x00\x00WAVEfmt " + b"0" * 32
MP4 = b"\x00\x00\x00\x18ftypmp42" + b"0" * 32


def _run(coro):
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def clean_env(monkeypatch, tmp_path):
    for k in ("FAL_KEY", "COMFYUI_URL", "MODEL_BACKEND", "CLOUDFLARE_ACCOUNT_ID", "CLOUDFLARE_API_TOKEN",
              "IMAGE_PROVIDER", "VIDEO_PROVIDER", "WAN_2_2_FAL_INPUT_JSON"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("COMFYUI_WORKFLOW_DIR", str(tmp_path / "workflows"))
    (tmp_path / "workflows").mkdir()
    yield


class FakeFal:
    """fal.ai queue API: submit -> status (IN_QUEUE, then COMPLETED) -> result."""

    def __init__(self, result_for):
        self.result_for = result_for
        self.jobs: list[tuple[str, dict]] = []
        self.polls = 0

    def handler(self, request: httpx.Request) -> httpx.Response:
        host, path = request.url.host, request.url.path
        if host == "files.fal.media":
            return httpx.Response(200, content=self.files[path])
        assert request.headers["authorization"] == "Key test-key"
        if request.method == "POST":
            endpoint = path.strip("/")
            self.jobs.append((endpoint, json.loads(request.content)))
            return httpx.Response(200, json={"request_id": "r1",
                                             "status_url": f"https://queue.fal.run/{endpoint}/requests/r1/status",
                                             "response_url": f"https://queue.fal.run/{endpoint}/requests/r1"})
        if path.endswith("/status"):
            self.polls += 1
            return httpx.Response(200, json={"status": "IN_QUEUE" if self.polls == 1 else "COMPLETED"})
        endpoint = path.rsplit("/requests/", 1)[0].strip("/")
        return httpx.Response(200, json=self.result_for(endpoint))

    files = {"/out.png": PNG, "/out.mp4": MP4}


@pytest.fixture
def fal(monkeypatch):
    monkeypatch.setenv("FAL_KEY", "test-key")

    def result_for(endpoint):
        if "image" in endpoint and "video" not in endpoint and "avatar" not in endpoint or endpoint.endswith("schnell"):
            return {"images": [{"url": "https://files.fal.media/out.png"}]}
        return {"video": {"url": "https://files.fal.media/out.mp4"}}

    fake = FakeFal(result_for)
    real = httpx.AsyncClient

    def factory(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(fake.handler)
        return real(*args, **kwargs)

    monkeypatch.setattr(fal_client.httpx, "AsyncClient", factory)
    async def no_sleep(_):
        return None
    monkeypatch.setattr(fal_client.asyncio, "sleep", no_sleep)
    return fake


# -- catalog -----------------------------------------------------------------


def test_catalog_lists_every_model_with_licence_and_a_place_to_run():
    ids = catalog.ids()
    assert set(ids) == {"z-image", "qwen-image", "flux-schnell", "wan-2.2", "ltx-2.3", "wan-vace",
                        "longcat-avatar", "infinitetalk", "wan-2.2-animate", "scail-2", "vista4d",
                        # Series: keyframes from references, voices, sound
                        "qwen-image-edit", "chatterbox", "indicf5", "indic-parler-tts", "hunyuan-foley", "ace-step"}
    for m in catalog.models():
        assert m["license"] and m["commercial"] in ("yes", "conditional") and m["license_url"].startswith("https://")
        assert m.get("fal") or m.get("comfyui") or m.get("selfhost")
    assert catalog.get("ltx-2.3")["commercial"] == "conditional"     # LTX-2 Community License: < $10M revenue
    assert [m["id"] for m in sorted(catalog.models("image"), key=lambda m: m["rank"])] == ["z-image", "qwen-image", "flux-schnell"]
    assert [m["id"] for m in sorted(catalog.models("speech"), key=lambda m: m["rank"])] == ["chatterbox", "indicf5", "indic-parler-tts"]
    assert "hi" in catalog.get("chatterbox")["languages"] and "ta" in catalog.get("indicf5")["languages"]
    assert catalog.get("hunyuan-foley")["commercial"] == "conditional"            # not in the EU / UK / South Korea
    assert set(catalog.catalog()["tasks"]) >= {"reference", "speech", "sound"}


def test_routing_picks_the_best_model_for_the_job():
    assert catalog.route_image("a fox in a misty forest at dawn") == "z-image"
    assert catalog.route_image("an empty street at night, no text, no people") == "z-image"
    assert catalog.route_image('a poster that says "SAVE WATER"') == "qwen-image"
    assert catalog.route_image("a labeled diagram of the heart") == "qwen-image"
    assert catalog.route_image("城市夜景海報，大標題") == "qwen-image"
    assert catalog.route_image("a fox", fast=True) == "flux-schnell"
    assert catalog.route_video(seconds=5) == "wan-2.2"
    assert catalog.route_video(seconds=14) == "ltx-2.3"
    assert catalog.route_video(has_audio=True) == "ltx-2.3"
    assert catalog.route_video(continuity=True) == "wan-vace"
    assert catalog.route_avatar(seconds=8) == "longcat-avatar"
    assert catalog.route_avatar(seconds=45) == "infinitetalk"
    assert catalog.route_avatar(seconds=8, speakers=2) == "infinitetalk"


def test_backends_free_first_and_clear_errors(monkeypatch, tmp_path):
    with pytest.raises(catalog.ModelUnavailable, match="FAL_KEY"):
        catalog.backend_for("z-image")
    with pytest.raises(catalog.ModelUnavailable, match="GPU server"):
        catalog.backend_for("scail-2")
    with pytest.raises(catalog.ModelUnavailable, match="no hosted API"):
        catalog.backend_for("vista4d")
    monkeypatch.setenv("FAL_KEY", "k")
    assert catalog.backend_for("z-image") == "fal"
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "a")
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "t")
    assert catalog.backend_for("flux-schnell") == "cloudflare"           # free tier before paid fal.ai
    monkeypatch.setenv("COMFYUI_URL", "http://gpu:8188")
    assert catalog.backend_for("z-image") == "fal"                        # no workflow exported yet
    (tmp_path / "workflows" / "z-image.json").write_text("{}")
    assert catalog.backend_for("z-image") == "comfyui"                    # your GPU server first
    monkeypatch.setenv("MODEL_BACKEND", "fal")
    assert catalog.backend_for("z-image") == "fal"
    with pytest.raises(catalog.ModelUnavailable, match="can't run on fal"):
        catalog.backend_for("scail-2")
    st = catalog.status()
    row = next(m for m in st["models"] if m["id"] == "scail-2")
    assert not row["ready"] and row["workflow"].endswith("scail-2.json")
    assert st["settings"]["fal"] and st["settings"]["modelBackend"] == "fal"


# -- image -------------------------------------------------------------------


def test_fal_image_inputs_per_model():
    assert fit_size(720, 1280) == (720, 1280)
    assert fit_size(512, 512) == (1280, 1280)
    z = fal_image_input("z-image", "a fox", 720, 1280, 7)
    assert z == {"prompt": "a fox", "image_size": {"width": 720, "height": 1280}, "num_images": 1,
                 "num_inference_steps": 8, "output_format": "png", "seed": 7}
    assert fal_image_input("qwen-image", "p", 1280, 720, None)["num_inference_steps"] == 30
    assert fal_image_input("flux-schnell", "p", 1280, 720, None)["num_inference_steps"] == 4


def test_image_models_run_on_fal(fal):
    data = _run(CatalogImageProvider("qwen-image").generate('a poster that says "HELLO"', width=720, height=1280, seed=1))
    assert data == PNG and fal.jobs[-1][0] == "fal-ai/qwen-image"
    best = BestImageProvider()
    _run(best.generate("a fox in the snow"))
    assert fal.jobs[-1][0] == "fal-ai/z-image/turbo" and best.last_model == "z-image"
    _run(best.generate("an infographic with the title 'Water cycle'"))
    assert fal.jobs[-1][0] == "fal-ai/qwen-image" and best.last_model == "qwen-image"


def test_best_image_falls_back_to_the_next_model_then_the_free_chain(monkeypatch, fal):
    calls = []

    async def flaky(self, prompt, *, width=512, height=512, seed=None):
        calls.append(self.model_id)
        if self.model_id == "z-image":
            raise RuntimeError("boom")
        return PNG

    monkeypatch.setattr(CatalogImageProvider, "generate", flaky)
    best = BestImageProvider()
    # the Model Router ranks the rest: with the default "balanced" preference the fast, cheap FLUX schnell is next
    assert _run(best.generate("a fox")) == PNG and calls == ["z-image", "flux-schnell"] and best.last_model == "flux-schnell"

    monkeypatch.delenv("FAL_KEY")

    class Free:
        name = "free"

        async def generate(self, *a, **k):
            return b"free"

    monkeypatch.setattr("agentic_core.models.image.factory.build_free_chain", lambda: Free())
    assert _run(BestImageProvider().generate("a fox")) == b"free"       # nothing set up: free chain


def test_image_factory_choices(monkeypatch):
    assert isinstance(get_image_provider("best"), BestImageProvider)
    with pytest.raises(ValueError, match="FAL_KEY"):
        get_image_provider("z-image")
    monkeypatch.setenv("FAL_KEY", "k")
    p = get_image_provider("qwen-image")
    assert isinstance(p, CatalogImageProvider) and p.name == "qwen-image"


def test_image_model_on_your_gpu_server(monkeypatch, tmp_path):
    wf = {"6": {"class_type": "CLIPTextEncode", "inputs": {"text": "{{PROMPT}}"}},
          "3": {"class_type": "KSampler", "inputs": {"seed": "{{SEED}}", "steps": "{{STEPS}}"}},
          "5": {"class_type": "EmptyLatentImage", "inputs": {"width": "{{WIDTH}}", "height": "{{HEIGHT}}"}}}
    (tmp_path / "workflows" / "z-image.json").write_text(json.dumps(wf))
    monkeypatch.setenv("COMFYUI_URL", "http://gpu:8188")
    queued = {}

    def handler(request):
        if request.url.path == "/prompt":
            queued.update(json.loads(request.content)["prompt"])
            return httpx.Response(200, json={"prompt_id": "p"})
        if request.url.path == "/history/p":
            return httpx.Response(200, json={"p": {"status": {"status_str": "success", "completed": True},
                                                   "outputs": {"9": {"images": [{"filename": "z_0001.png", "type": "output"}]}}}})
        if request.url.path == "/view":
            return httpx.Response(200, content=PNG)
        return httpx.Response(404)

    real = httpx.AsyncClient
    monkeypatch.setattr(comfyui_provider.httpx, "AsyncClient",
                        lambda *a, **k: real(*a, **{**k, "transport": httpx.MockTransport(handler)}))
    p = CatalogImageProvider("z-image")
    assert _run(p.generate("a fox", width=720, height=1280, seed=4)) == PNG and p.last_backend == "comfyui"
    assert queued["3"]["inputs"] == {"seed": 4, "steps": 8}
    assert queued["5"]["inputs"] == {"width": 704, "height": 1280}       # multiples of 32 for the latent


# -- video / avatar ----------------------------------------------------------


def test_fal_video_inputs_per_model():
    assert frames_for("wan-2.2", 5) == 81 and frames_for("wan-2.2", 30) == 161
    assert frames_for("infinitetalk", 8) == 201 and (frames_for("ltx-2.3", 4) - 1) % 8 == 0
    kw = dict(prompt="p", width=720, height=1280, seed=3, image="data:img", audio=None, video=None)
    ep, d = fal_video_input("wan-2.2", seconds=5, **kw)
    assert ep == "fal-ai/wan/v2.2-a14b/image-to-video"
    assert d["image_url"] == "data:img" and d["num_frames"] == 81 and d["frames_per_second"] == 16 and d["seed"] == 3
    ep, d = fal_video_input("ltx-2.3", seconds=7, **kw)
    assert ep == "fal-ai/ltx-2.3/image-to-video" and d["duration"] == 8 and d["generate_audio"] is False
    ep, d = fal_video_input("ltx-2.3", seconds=7, **{**kw, "audio": "data:wav"})
    assert ep == "fal-ai/ltx-2.3-22b/audio-to-video" and d["audio_url"] == "data:wav" and d["match_audio_length"]
    ep, d = fal_video_input("longcat-avatar", seconds=12, **{**kw, "audio": "data:wav"})
    assert ep == "fal-ai/longcat-single-avatar/image-audio-to-video" and d["num_segments"] == 3 and d["audio_url"]
    ep, d = fal_video_input("infinitetalk", seconds=8, **{**kw, "audio": "data:wav"})
    assert ep == "fal-ai/infinitalk" and d["num_frames"] == 201
    ep, d = fal_video_input("wan-vace", seconds=5, **{**kw, "video": "data:mp4"})
    assert d["task"] == "depth" and d["ref_image_urls"] == ["data:img"] and d["num_frames"] == 81
    ep, d = fal_video_input("wan-2.2-animate", seconds=5, **{**kw, "video": "data:mp4"})
    assert ep == "fal-ai/wan/v2.2-14b/animate/move" and set(d) == {"video_url", "image_url", "resolution", "seed"}
    with pytest.raises(catalog.ModelUnavailable):
        fal_video_input("scail-2", seconds=5, **kw)


def test_fal_input_override(monkeypatch):
    monkeypatch.setenv("WAN_2_2_FAL_INPUT_JSON", '{"resolution": "480p", "num_inference_steps": 20}')
    _, d = fal_video_input("wan-2.2", prompt="p", width=1, height=2, seed=None, seconds=5, image="i", audio=None, video=None)
    assert d["resolution"] == "480p" and d["num_inference_steps"] == 20


def test_video_and_avatar_models_run_on_fal(fal):
    clip = _run(CatalogVideoProvider("wan-2.2").generate("a fox runs", width=720, height=1280, seed=2,
                                                         duration_seconds=5, image=PNG))
    assert clip == MP4
    ep, data = fal.jobs[-1]
    assert ep == "fal-ai/wan/v2.2-a14b/image-to-video" and data["image_url"].startswith("data:image/png;base64,")
    talk = CatalogVideoProvider("longcat-avatar")
    assert talk.wants_audio == "required" and talk.needs_presenter
    _run(talk.generate("hello", duration_seconds=6, image=PNG, audio=WAV))
    ep, data = fal.jobs[-1]
    assert data["audio_url"].startswith("data:audio/wav;base64,") and talk.cost_per_clip_usd == pytest.approx(0.9)
    with pytest.raises(RuntimeError, match="narration audio"):
        _run(talk.generate("hello", image=PNG))


def test_best_video_routes_and_falls_back_to_free_motion(monkeypatch, fal):
    best = BestVideoProvider("video")
    _run(best.generate("p", duration_seconds=4, image=PNG))
    assert fal.jobs[-1][0] == "fal-ai/wan/v2.2-a14b/image-to-video" and best.name == "best:wan-2.2"
    _run(best.generate("p", duration_seconds=14, image=PNG))
    assert fal.jobs[-1][0] == "fal-ai/ltx-2.3/image-to-video" and best.name == "best:ltx-2.3"

    monkeypatch.delenv("FAL_KEY")
    seen = {}

    class Motion:
        async def generate(self, prompt, **kw):
            seen.update(kw)
            return b"motion"

    monkeypatch.setattr("agentic_core.models.video.motion_provider.MotionVideoProvider", lambda: Motion())
    best = BestVideoProvider("video")
    assert _run(best.generate("p", duration_seconds=4, image=PNG)) == b"motion" and best.name == "best:motion"
    assert seen["image"] == PNG


def test_avatar_routes_by_length(fal):
    av = BestVideoProvider("avatar")
    _run(av.generate("p", duration_seconds=8, image=PNG, audio=WAV))
    assert fal.jobs[-1][0] == "fal-ai/longcat-single-avatar/image-audio-to-video"
    _run(av.generate("p", duration_seconds=40, image=PNG, audio=WAV))
    assert fal.jobs[-1][0] == "fal-ai/infinitalk" and av.name == "avatar:infinitetalk"


def test_video_factory_choices(monkeypatch):
    assert {"best", "avatar", "wan-2.2", "ltx-2.3", "wan-vace", "longcat-avatar", "infinitetalk"} <= IMAGE_TO_VIDEO_PROVIDERS
    assert get_video_provider("best").name == "best"
    with pytest.raises(ValueError, match="LongCat Avatar or InfiniteTalk"):
        get_video_provider("avatar")
    with pytest.raises(ValueError, match="FAL_KEY"):
        get_video_provider("ltx-2.3")
    monkeypatch.setenv("FAL_KEY", "k")
    assert get_video_provider("avatar").needs_presenter
    assert get_video_provider("ltx-2.3").wants_audio == "optional"


def test_avatar_on_your_gpu_server_uploads_picture_and_audio(monkeypatch, tmp_path):
    wf = {"1": {"class_type": "LoadImage", "inputs": {"image": "{{IMAGE}}"}},
          "2": {"class_type": "LoadAudio", "inputs": {"audio": "{{AUDIO}}"}},
          "3": {"class_type": "Sampler", "inputs": {"frames": "{{FRAMES}}", "text": "{{PROMPT}}"}}}
    (tmp_path / "workflows" / "infinitetalk.json").write_text(json.dumps(wf))
    monkeypatch.setenv("COMFYUI_URL", "http://gpu:8188")
    uploads, queued = [], {}

    def handler(request):
        if request.url.path == "/upload/image":
            name = request.content.split(b'filename="')[1].split(b'"')[0].decode()
            uploads.append(name)
            return httpx.Response(200, json={"name": name, "subfolder": "", "type": "input"})
        if request.url.path == "/prompt":
            queued.update(json.loads(request.content)["prompt"])
            return httpx.Response(200, json={"prompt_id": "p"})
        if request.url.path == "/history/p":
            return httpx.Response(200, json={"p": {"status": {"completed": True},
                                                   "outputs": {"9": {"gifs": [{"filename": "t.mp4", "type": "output"}]}}}})
        if request.url.path == "/view":
            return httpx.Response(200, content=MP4)
        return httpx.Response(404)

    real = httpx.AsyncClient
    monkeypatch.setattr(comfyui_provider.httpx, "AsyncClient",
                        lambda *a, **k: real(*a, **{**k, "transport": httpx.MockTransport(handler)}))
    p = CatalogVideoProvider("infinitetalk")
    assert _run(p.generate("hi", duration_seconds=4, image=PNG, audio=WAV)) == MP4
    assert p.last_backend == "comfyui" and p.cost_per_clip_usd == 0.0
    assert uploads[0].endswith(".png") and uploads[1].endswith(".wav")
    assert queued["1"]["inputs"]["image"] == uploads[0] and queued["2"]["inputs"]["audio"] == uploads[1]
    assert queued["3"]["inputs"]["frames"] == 101                          # 25 fps, 4k+1


def test_fal_errors_are_explained(monkeypatch):
    monkeypatch.setenv("FAL_KEY", "bad")

    def handler(request):
        return httpx.Response(401, json={"detail": "Invalid key"})

    real = httpx.AsyncClient
    monkeypatch.setattr(fal_client.httpx, "AsyncClient",
                        lambda *a, **k: real(*a, **{**k, "transport": httpx.MockTransport(handler)}))
    with pytest.raises(fal_client.FalError, match="Check FAL_KEY"):
        _run(fal_client.run("fal-ai/z-image/turbo", {"prompt": "x"}))
    assert fal_client.data_uri(WAV).startswith("data:audio/wav")
    assert fal_client.first_url({"images": [{"url": "u"}]}, "images") == "u"
    assert fal_client.first_url({"video": "https://v"}, "video") == "https://v"
