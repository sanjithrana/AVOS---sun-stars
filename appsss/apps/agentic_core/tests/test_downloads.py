"""Model downloads (Models page → Download): the verified file lists, and the downloader against a fake Hugging Face
(resume, skip, progress, errors, free space, folder picker)."""
import asyncio
from pathlib import Path

import httpx
import pytest

from agentic_core.model_fabric import downloads, model_files

ROOT = Path(__file__).resolve().parents[2]


class FakeHF:
    def __init__(self, files: dict[str, bytes], deny: set[str] = frozenset(), short: set[str] = frozenset()):
        self.files, self.deny, self.short, self.ranges = files, deny, short, []

    def handler(self, req: httpx.Request) -> httpx.Response:
        path = req.url.path.split("/resolve/main/", 1)[1]
        if path in self.deny:
            return httpx.Response(401)
        data = self.files.get(path)
        if data is None:
            return httpx.Response(404)
        rng = req.headers.get("range")
        if rng:
            start = int(rng.split("=")[1].split("-")[0])
            self.ranges.append((path, start))
            if start >= len(data):
                return httpx.Response(416)
            data = data[start:]
            return httpx.Response(206, content=data, headers={"content-length": str(len(data))})
        if path in self.short:
            data = data[: len(data) // 2]
        return httpx.Response(200, content=data, headers={"content-length": str(len(data))})


@pytest.fixture
def hf(monkeypatch):
    def install(fake):
        real = httpx.AsyncClient
        monkeypatch.setattr(downloads.httpx, "AsyncClient", lambda *a, **k: real(*a, **{**k, "transport": httpx.MockTransport(fake.handler)}))
        monkeypatch.setenv("HF_ENDPOINT", "https://hf.test")
        return fake
    downloads.JOBS.clear()
    yield install
    downloads.JOBS.clear()


def files_for(blobs):
    return [{"repo": "org/repo", "path": f"split/{n}", "folder": folder, "size": len(b)} for (folder, n), b in blobs.items()]


async def run(**kw):
    job = downloads.start(**kw)
    await job._task
    return job


def test_manifest_is_complete_and_consistent():
    m = model_files.manifest()
    assert {"z-image", "qwen-image", "flux-schnell", "wan-2.2", "ltx-2.3", "wan-vace", "infinitetalk",
            "wan-2.2-animate", "scail-2", "longcat-avatar"} <= set(m)
    for mid, e in m.items():
        assert e["default"] in e["variants"], mid
        for f in [x for v in e["variants"].values() for x in v] + e.get("shared", []) + e.get("optional", []):
            assert f["repo"] and f["path"].endswith((".safetensors", ".pth")) and f["size"] > 1e6 and f["folder"] in downloads.FOLDERS, (mid, f)
    assert {"qwen-image-edit", "ace-step", "hunyuan-foley"} <= set(m)
    edit = model_files.files("qwen-image-edit", "fp8")
    assert [f["folder"] for f in edit] == ["diffusion_models", "text_encoders", "vae"]          # same encoder + VAE as Qwen-Image
    assert model_files.options("hunyuan-foley", vram_gb=12)["recommended"] == "xl"
    assert model_files.options("hunyuan-foley", vram_gb=24)["recommended"] == "xxl"
    o = model_files.options("wan-2.2", vram_gb=24)
    assert o["recommended"] == "fp8" and [v["key"] for v in o["variants"]] == ["bf16", "fp8"]
    fp8 = next(v for v in o["variants"] if v["key"] == "fp8")
    assert fp8["total"] > fp8["size"] > 28e9 and len(fp8["files"]) == 2
    assert model_files.options("wan-2.2", vram_gb=80)["recommended"] == "bf16"
    fl = model_files.files("qwen-image", "fp8", extras=["loras/Qwen-Image-Lightning-8steps-V1.0.safetensors"])
    assert [f["folder"] for f in fl] == ["diffusion_models", "text_encoders", "vae", "loras"]
    assert fl[0]["url"].startswith("https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/")
    with pytest.raises(ValueError):
        model_files.files("wan-vace", "fp8")


def test_worker_has_an_identical_downloader():
    assert (ROOT / "gpu_worker/worker/downloads.py").read_text() == (ROOT / "agentic_core/model_fabric/downloads.py").read_text()


def test_download_resume_skip_and_progress(hf, tmp_path):
    blobs = {("diffusion_models", "a.safetensors"): b"A" * 3_000_000, ("vae", "v.safetensors"): b"V" * 1000}
    fake = hf(FakeHF({f"split/{n}": b for (_, n), b in blobs.items()}))
    fl = files_for(blobs) + files_for({("vae", "v.safetensors"): b"V" * 1000})       # duplicate shared file
    # a half-finished earlier download
    (tmp_path / "diffusion_models").mkdir()
    (tmp_path / "diffusion_models" / "a.safetensors.part").write_bytes(b"A" * 1_000_000)
    job = asyncio.run(run(files=fl, dest=str(tmp_path), label="Test"))
    assert job.status == "done", job.public()
    assert (tmp_path / "diffusion_models" / "a.safetensors").read_bytes() == blobs[("diffusion_models", "a.safetensors")]
    assert (tmp_path / "vae" / "v.safetensors").stat().st_size == 1000
    assert ("split/a.safetensors", 1_000_000) in fake.ranges and len(job.files) == 2
    pub = job.public()
    assert pub["progress"] == 1.0 and pub["done"] == pub["total"] == 3_001_000
    # again: everything is already there
    again = asyncio.run(run(files=fl, dest=str(tmp_path)))
    assert again.status == "done" and {f.status for f in again.files} == {"skipped"}
    assert downloads.check(str(tmp_path), [{"folder": "vae", "name": "v.safetensors", "size": 1000},
                                           {"folder": "vae", "name": "v.safetensors", "size": 5}]) == [True, False]


def test_errors_are_explained(hf, tmp_path):
    blobs = {("loras", "gated.safetensors"): b"x" * 10, ("loras", "short.safetensors"): b"y" * 100}
    hf(FakeHF({f"split/{n}": b for (_, n), b in blobs.items()}, deny={"split/gated.safetensors"}, short={"split/short.safetensors"}))
    job = asyncio.run(run(files=files_for(blobs) + [{"repo": "org/repo", "path": "split/gone.safetensors", "folder": "loras", "size": 5}],
                          dest=str(tmp_path)))
    assert job.status == "error"
    by = {f.name: f for f in job.files}
    assert "HF_TOKEN" in by["gated.safetensors"].error
    assert "incomplete" in by["short.safetensors"].error and (tmp_path / "loras" / "short.safetensors.part").exists()
    assert "not found" in by["gone.safetensors"].error
    with pytest.raises(ValueError, match="Not enough free space"):
        downloads.start(files=[{"repo": "o/r", "path": "x.safetensors", "folder": "vae", "size": 10**16}], dest=str(tmp_path))
    with pytest.raises(ValueError, match="Unknown model folder"):
        downloads.plan_files([{"repo": "o/r", "path": "x.safetensors", "folder": "../etc", "size": 1}], str(tmp_path))
    with pytest.raises(ValueError):
        downloads.plan_files([{"url": "https://x/..", "name": "..", "folder": "vae"}], str(tmp_path))


def test_cancel(hf, tmp_path, monkeypatch):
    monkeypatch.setattr(downloads, "CHUNK", 1000)
    class Slow(FakeHF):
        def handler(self, req):
            async def body():
                for _ in range(200):
                    await asyncio.sleep(0.01)
                    yield b"z" * 1000
            return httpx.Response(200, content=body(), headers={"content-length": "200000"})

    hf(Slow({}))

    async def go():
        job = downloads.start(files=[{"repo": "o/r", "path": "big.safetensors", "folder": "vae", "size": 200000}], dest=str(tmp_path))
        await asyncio.sleep(0.2)
        assert job.public()["status"] == "running" and 0 < job.done < 200000
        downloads.cancel(job.id)
        try:
            await job._task
        except asyncio.CancelledError:
            pass
        return job
    job = asyncio.run(go())
    assert job.status == "cancelled" and (tmp_path / "vae" / "big.safetensors.part").exists()


def test_folder_picker_respects_roots(monkeypatch, tmp_path):
    (tmp_path / "models" / "diffusion_models").mkdir(parents=True)
    monkeypatch.setenv("DOWNLOAD_ROOTS", str(tmp_path / "models"))
    top = downloads.browse(None)
    assert top["dirs"][0]["path"] == str(tmp_path / "models")
    inside = downloads.browse(str(tmp_path / "models"))
    assert inside["looks_like_models"] and inside["writable"] and inside["free"] > 0 and inside["parent"] is None
    with pytest.raises(ValueError, match="DOWNLOAD_ROOTS"):
        downloads.browse(str(tmp_path))
    made = downloads.mkdir(str(tmp_path / "models"), "wan")
    assert Path(made).is_dir()
    with pytest.raises(ValueError):
        downloads.mkdir(str(tmp_path / "models"), "../x")
    assert not downloads.allowed(str(tmp_path / "models" / ".." / "x"))
