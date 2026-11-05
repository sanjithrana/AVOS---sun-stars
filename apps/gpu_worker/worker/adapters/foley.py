"""Sound effects for a clip: Tencent HunyuanVideo-Foley run headless (its own infer.py), like the Wan2GP adapter.

    hunyuan-foley    watches the clip and makes matching 48 kHz sound (footsteps, a door, a slap, rain, room tone)
                     guided by a short description. XXL ~20 GB VRAM (12 GB with offload); XL 16 GB (8 GB offload).

Setup on the GPU machine (Linux, CUDA):

    git clone https://github.com/Tencent-Hunyuan/HunyuanVideo-Foley /opt/HunyuanVideo-Foley
    cd /opt/HunyuanVideo-Foley && pip install -r requirements.txt
    AVOS Models page → HunyuanVideo-Foley → Download → this worker   (or: hf download tencent/HunyuanVideo-Foley)

FOLEY_DIR (default /opt/HunyuanVideo-Foley), FOLEY_MODELS (default <models dir>/hunyuanvideo_foley), FOLEY_SIZE
(xxl / xl, default xl), FOLEY_PYTHON. Offload is used when the router says the model doesn't fit.
Job: task "sound", want "audio", prompt = what should be heard, inputs["video"] = the clip. Returns a WAV.
Licence: Tencent Hunyuan Community (commercial use allowed; not for use in the EU, UK or South Korea).
"""
from __future__ import annotations

import asyncio
import os
import re
import shutil
import tempfile
from pathlib import Path

from worker import config
from worker.adapters.base import Adapter, JobSpec, Progress

AUDIO = (".wav", ".flac", ".mp3")
VIDEO = (".mp4", ".mov", ".mkv")


def foley_dir() -> Path:
    return Path(os.getenv("FOLEY_DIR") or "/opt/HunyuanVideo-Foley")


def foley_models() -> Path:
    return Path(os.getenv("FOLEY_MODELS") or Path(config.MODELS_DIR) / "hunyuanvideo_foley")


class FoleyAdapter(Adapter):
    name = "foley"
    precisions = ("bf16",)
    offload = True
    keeps_loaded = False

    def __init__(self) -> None:
        self._proc: asyncio.subprocess.Process | None = None

    async def ready(self) -> tuple[bool, str | None]:
        if not (foley_dir() / "infer.py").is_file():
            return False, f"HunyuanVideo-Foley not found at {foley_dir()} (git clone it there or set FOLEY_DIR)."
        size = (os.getenv("FOLEY_SIZE") or "xl").lower()
        weight = "hunyuanvideo_foley_xl.pth" if size == "xl" else "hunyuanvideo_foley.pth"
        if not (foley_models() / weight).is_file():
            return False, f"Its weights aren't in {foley_models()} (Models page → HunyuanVideo-Foley → Download)."
        return True, None

    def models(self) -> list[str]:
        return ["hunyuan-foley"]

    def command(self, video: Path, prompt: str, out: Path, offload: bool) -> list[str]:
        cmd = [os.getenv("FOLEY_PYTHON") or "python3", "infer.py", "--model_path", str(foley_models()),
               "--model_size", (os.getenv("FOLEY_SIZE") or "xl").lower(), "--single_video", str(video),
               "--single_prompt", prompt or "natural sound of the scene", "--output_dir", str(out)]
        return cmd + (["--enable_offload"] if offload else [])

    async def run(self, job: JobSpec, progress: Progress) -> tuple[bytes, str]:
        if not job.inputs.get("video"):
            raise RuntimeError("Foley needs the clip (inputs['video']).")
        with tempfile.TemporaryDirectory(prefix="avos_foley_") as t:
            tmp = Path(t)
            video, out = tmp / "clip.mp4", tmp / "out"
            video.write_bytes(job.inputs["video"])
            out.mkdir()
            await progress(0.05, "HunyuanVideo-Foley: listening to the clip")
            self._proc = await asyncio.create_subprocess_exec(
                *self.command(video, job.prompt, out, job.offload), cwd=str(foley_dir()),
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
            tail: list[str] = []
            assert self._proc.stdout is not None
            async for raw in self._proc.stdout:
                line = raw.decode("utf-8", "replace").strip()
                if line:
                    tail = (tail + [line])[-20:]
                    m = re.search(r"(\d+)/(\d+)\s*\[", line)
                    if m and int(m.group(2)):
                        await progress(int(m.group(1)) / int(m.group(2)), f"step {m.group(1)}/{m.group(2)}")
            code = await self._proc.wait()
            self._proc = None
            if code != 0:
                raise RuntimeError(f"HunyuanVideo-Foley exited with {code}: " + " | ".join(tail[-5:]))
            files = sorted(out.rglob("*"), key=lambda p: p.stat().st_mtime)
            audio = [p for p in files if p.suffix.lower() in AUDIO]
            if audio:
                return audio[-1].read_bytes(), audio[-1].suffix.lstrip(".").lower()
            vids = [p for p in files if p.suffix.lower() in VIDEO]
            if vids and shutil.which("ffmpeg"):     # it saved the clip with its sound: take the sound
                wav = tmp / "sound.wav"
                proc = await asyncio.create_subprocess_exec("ffmpeg", "-y", "-loglevel", "error", "-i", str(vids[-1]),
                                                            "-vn", "-ac", "2", "-ar", "48000", str(wav))
                await proc.wait()
                if wav.is_file():
                    return wav.read_bytes(), "wav"
            raise RuntimeError("HunyuanVideo-Foley finished but wrote no sound. " + " | ".join(tail[-3:]))

    async def cancel(self) -> None:
        if self._proc and self._proc.returncode is None:
            self._proc.terminate()
