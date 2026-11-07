"""Series jobs on the worker: voices (speech backend), sound effects (HunyuanVideo-Foley headless), ComfyUI reference
pictures + audio results, and the mock backend's stand-ins. No GPU, no model weights: the engines are faked."""
import asyncio
import base64
import io
import sys
import time
import types
import wave
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from worker import config, gpu
from worker.adapters import comfyui
from worker.adapters.base import JobSpec
from worker.adapters.foley import FoleyAdapter
from worker.adapters.mock import MockAdapter, wav, wav_seconds
from worker.adapters.speech import SpeechAdapter
from worker.app import create_app
from worker.jobs import Queue

RTX4090 = '{"name": "NVIDIA GeForce RTX 4090", "vram_gb": 24, "compute_capability": "8.9"}'


@pytest.fixture(autouse=True)
def setup(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "FAKE_GPU", RTX4090)
    monkeypatch.setattr(config, "MOCK_SECONDS", 0.2)
    monkeypatch.setattr(config, "RESULTS", tmp_path / "results")
    monkeypatch.setattr(config, "TOKEN", None)
    monkeypatch.setattr(gpu, "_smi", lambda: None)
    gpu._cache.update(t=0.0, gpu=None)
    yield


def run(adapter, spec: JobSpec):
    async def go():
        async def progress(f, s):
            pass
        await adapter.load(spec, progress)
        return await adapter.run(spec, progress)
    return asyncio.run(go())


def test_job_options_reach_the_backend_and_audio_comes_back():
    with TestClient(create_app(Queue({"mock": MockAdapter()}))) as c:
        r = c.post("/jobs", json={"model": "chatterbox", "adapter": "mock", "task": "speech", "want": "audio",
                                  "prompt": "नमस्ते, आज बहुत गर्मी है!", "options": {"language": "hi", "exaggeration": 0.8}})
        assert r.status_code == 200, r.text
        jid = r.json()["id"]
        t = time.monotonic()
        while c.get(f"/jobs/{jid}").json()["status"] != "done":
            assert time.monotonic() - t < 10
            time.sleep(0.05)
        res = c.get(f"/jobs/{jid}/result")
    assert res.headers["content-type"] == "audio/wav"
    assert 0.8 <= wav_seconds(res.content) < 3


def test_mock_lip_sync_lasts_as_long_as_the_line():
    spec = JobSpec(model="infinitetalk", adapter="mock", task="avatar", want="video", prompt="talks", width=320, height=180,
                   seconds=1.0, fps=8, inputs={"image": b"x", "audio": wav(2.5, 200)})
    data, ext = run(MockAdapter(), spec)
    assert ext == "mp4" and spec.seconds == pytest.approx(2.5, abs=0.01)


class FakeTensor:
    def __init__(self, n):
        self.n = n

    def detach(self):
        return self

    def cpu(self):
        return self

    def float(self):
        return self

    def numpy(self):
        import numpy as np
        return np.zeros(self.n, dtype=np.float32)


def test_speech_backend_clones_the_approved_voice(monkeypatch):
    pytest.importorskip("numpy")
    pytest.importorskip("soundfile")
    calls = []

    class FakeTTS:
        sr = 24000

        @classmethod
        def from_pretrained(cls, device, t3_model=None):
            calls.append(("load", device, t3_model))
            return cls()

        def generate(self, text, **kw):
            calls.append(("gen", text, kw["language_id"], Path(kw["audio_prompt_path"]).read_bytes(), kw["exaggeration"]))
            return FakeTensor(24000)

    mtl = types.ModuleType("chatterbox.mtl_tts")
    mtl.ChatterboxMultilingualTTS = FakeTTS
    monkeypatch.setitem(sys.modules, "chatterbox", types.ModuleType("chatterbox"))
    monkeypatch.setitem(sys.modules, "chatterbox.mtl_tts", mtl)
    torch = types.ModuleType("torch")
    torch.cuda = types.SimpleNamespace(is_available=lambda: False)
    monkeypatch.setitem(sys.modules, "torch", torch)

    a = SpeechAdapter()
    monkeypatch.setattr("worker.adapters.speech._has", lambda pkg: pkg in ("torch", "chatterbox"))
    assert a.models() == ["chatterbox"] and asyncio.run(a.ready()) == (True, None)
    spec = JobSpec(model="chatterbox", adapter="speech", task="speech", want="audio", prompt="Arre, chai kahan hai?",
                   inputs={"audio": b"VOICE"}, options={"language": "hi-IN", "exaggeration": 1.1})
    data, ext = run(a, spec)
    assert ext == "wav" and data[:4] == b"RIFF"
    assert calls[0] == ("load", "cpu", "v3") and calls[1] == ("gen", "Arre, chai kahan hai?", "hi", b"VOICE", 1.1)
    with wave.open(io.BytesIO(data)) as w:
        assert w.getframerate() == 24000 and w.getnframes() == 24000

    bad = JobSpec(model="chatterbox", adapter="speech", task="speech", want="audio", prompt="வணக்கம்", options={"language": "ta"})
    with pytest.raises(RuntimeError, match="doesn't speak 'ta'"):
        run(a, bad)


def test_foley_runs_headless_and_returns_the_sound(monkeypatch, tmp_path):
    repo, weights = tmp_path / "foley", tmp_path / "models" / "hunyuanvideo_foley"
    repo.mkdir()
    weights.mkdir(parents=True)
    (weights / "hunyuanvideo_foley_xl.pth").write_bytes(b"w")
    # a stand-in infer.py that checks the flags and writes a wav, like the real one
    (repo / "infer.py").write_text(
        "import sys, wave, pathlib\n"
        "a = sys.argv\n"
        "assert a[a.index('--model_size') + 1] == 'xl' and pathlib.Path(a[a.index('--single_video') + 1]).is_file()\n"
        "out = pathlib.Path(a[a.index('--output_dir') + 1]); prompt = a[a.index('--single_prompt') + 1]\n"
        "print('50/50 [00:01]', flush=True)\n"
        "w = wave.open(str(out / 'clip.wav'), 'wb'); w.setnchannels(1); w.setsampwidth(2); w.setframerate(48000)\n"
        "w.writeframes(b'\\x00\\x00' * 48000); w.close()\n"
        "open(out / 'prompt.txt', 'w').write(prompt)\n")
    monkeypatch.setenv("FOLEY_DIR", str(repo))
    monkeypatch.setenv("FOLEY_MODELS", str(weights))
    monkeypatch.setenv("FOLEY_PYTHON", sys.executable)
    a = FoleyAdapter()
    assert asyncio.run(a.ready()) == (True, None) and a.models() == ["hunyuan-foley"]
    data, ext = run(a, JobSpec(model="hunyuan-foley", adapter="foley", task="sound", want="audio",
                                prompt="a pressure cooker whistles, steel plates clatter", inputs={"video": b"MP4"}))
    assert ext == "wav" and wav_seconds(data) == pytest.approx(1.0)
    (weights / "hunyuanvideo_foley_xl.pth").unlink()
    ok, why = asyncio.run(FoleyAdapter().ready())
    assert not ok and "Download" in why


def test_comfyui_gets_reference_pictures_and_returns_audio(monkeypatch, tmp_path):
    wf = {"1": {"class_type": "LoadImage", "inputs": {"image": "{{IMAGE}}"}},
          "2": {"class_type": "LoadImage", "inputs": {"image": "{{IMAGE2}}"}},
          "3": {"class_type": "TextEncodeAceStepAudio", "inputs": {"tags": "{{PROMPT}}", "lyrics": "{{LYRICS}}"}}}
    vals = {"{{IMAGE}}": "a.png", "{{IMAGE2}}": "b.png", "{{PROMPT}}": "sitcom theme, tabla, upbeat", "{{LYRICS}}": "[instrumental]"}
    out = comfyui.fill(wf, vals)
    assert out["2"]["inputs"]["image"] == "b.png" and out["3"]["inputs"]["lyrics"] == "[instrumental]"
    assert comfyui.wanted_exts("audio") == comfyui.AUDIO_EXTS and ".flac" in comfyui.AUDIO_EXTS
    assert comfyui.FILES["{{IMAGE3}}"][0] == "image3"


def test_inputs_and_options_are_validated():
    with TestClient(create_app(Queue({"mock": MockAdapter()}))) as c:
        r = c.post("/jobs", json={"model": "qwen-image-edit", "adapter": "mock", "task": "edit", "want": "image",
                                  "prompt": "the two of them in the kitchen", "options": "nope",
                                  "inputs": {"image": base64.b64encode(b"a").decode(), "image2": base64.b64encode(b"b").decode()}})
    assert r.status_code == 200
