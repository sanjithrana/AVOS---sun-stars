"""Wan2GP (github.com/deepbeepmeep/Wan2GP) run headless: `python wgp.py --process settings.json --output-dir ...`.

Wan2GP is a strong low-VRAM engine (Wan 2.1/2.2, VACE, LTX-2, InfiniteTalk, Qwen Image, Z-Image, Flux…) with its own
INT8 quantization, offload profiles and SageAttention / FlashAttention support. The worker drives its documented CLI
batch mode, one settings file per job:

  1. In Wan2GP's web UI pick the model and settings you like for an AVOS job (e.g. Wan 2.2 image-to-video, 720p).
  2. Save the settings (the JSON settings file) as wan2gp_templates/<AVOS model id>.json, e.g. wan-2.2.json.
  3. Replace the values AVOS should control with placeholders:
       {{PROMPT}} {{NEGATIVE_PROMPT}} {{SEED}} {{WIDTH}} {{HEIGHT}} {{RESOLUTION}} ("1280x720") {{FRAMES}} {{FPS}}
       {{STEPS}} and input files {{IMAGE}} {{AUDIO}} {{VIDEO}} (replaced by file paths).

Precision: bf16 → --quantize-transformer False; int8 → True (Wan2GP's default). Attention: --attention sage2 / sage /
flash / sdpa, as the router chose. Each job starts Wan2GP, so the model loads every time (keeps_loaded = False).
"""
from __future__ import annotations

import asyncio
import json
import re
import tempfile
import time
from pathlib import Path
from typing import Any

from worker import config
from worker.adapters.base import Adapter, JobSpec, Progress

NUMERIC = ("{{SEED}}", "{{WIDTH}}", "{{HEIGHT}}", "{{FRAMES}}", "{{FPS}}", "{{STEPS}}")
FILES = {"{{IMAGE}}": ("image", "png"), "{{AUDIO}}": ("audio", "wav"), "{{VIDEO}}": ("video", "mp4")}
STEP_RX = re.compile(r"(\d+)/(\d+)\s*\[")
OUT_EXTS = {".mp4", ".webm", ".mkv", ".png", ".jpg", ".jpeg", ".webp"}


def fill(node: Any, values: dict[str, Any]) -> Any:
    if isinstance(node, dict):
        return {k: fill(v, values) for k, v in node.items()}
    if isinstance(node, list):
        return [fill(v, values) for v in node]
    if isinstance(node, str):
        s = node.strip()
        if s in values and (s in NUMERIC or s in FILES):
            return values[s]
        out = node
        for k in ("{{PROMPT}}", "{{NEGATIVE_PROMPT}}", "{{RESOLUTION}}"):
            out = out.replace(k, str(values.get(k, "")))
        return out
    return node


class Wan2GPAdapter(Adapter):
    name = "wan2gp"
    precisions = ("bf16", "int8")
    attentions = ("sage2", "sage", "flash", "sdpa")
    offload = True
    keeps_loaded = False

    def __init__(self) -> None:
        self._proc: asyncio.subprocess.Process | None = None

    async def ready(self) -> tuple[bool, str | None]:
        if not (config.WAN2GP_DIR / "wgp.py").is_file():
            return False, f"Wan2GP not found at {config.WAN2GP_DIR} (git clone it there or set WAN2GP_DIR)."
        if not self.models():
            return False, f"No settings templates in {config.WAN2GP_TEMPLATES} (save one per model as <model id>.json)."
        return True, None

    def models(self) -> list[str]:
        d = config.WAN2GP_TEMPLATES
        return sorted(p.stem for p in d.glob("*.json")) if d.is_dir() else []

    def command(self, settings: Path, out_dir: Path, job: JobSpec) -> list[str]:
        cmd = [config.WAN2GP_PYTHON, "wgp.py", "--process", str(settings), "--output-dir", str(out_dir),
               "--attention", job.attention if job.attention in self.attentions else "sdpa",
               "--quantize-transformer", "False" if job.precision == "bf16" else "True"]
        if config.WAN2GP_PROFILE:
            cmd += ["--profile", str(config.WAN2GP_PROFILE)]
        return cmd

    def settings_for(self, job: JobSpec, tmp: Path) -> dict[str, Any]:
        template = json.loads((config.WAN2GP_TEMPLATES / f"{job.model}.json").read_text("utf-8"))
        text = json.dumps(template)
        values: dict[str, Any] = {
            "{{PROMPT}}": job.prompt, "{{NEGATIVE_PROMPT}}": job.negative_prompt,
            "{{SEED}}": int(job.seed if job.seed is not None else time.time()) % 2_147_483_647,
            "{{WIDTH}}": job.width, "{{HEIGHT}}": job.height, "{{RESOLUTION}}": f"{job.width}x{job.height}",
            "{{FRAMES}}": int(job.frames or max(1, round(job.seconds * (job.fps or 16)) + 1)),
            "{{FPS}}": int(job.fps or 16), "{{STEPS}}": int(job.steps or 30),
        }
        for ph, (key, ext) in FILES.items():
            if ph in text:
                data = job.inputs.get(key)
                if not data:
                    raise RuntimeError(f"The Wan2GP template for {job.model} needs {key} ({ph}) and the job has none.")
                path = tmp / f"input_{key}.{ext}"
                path.write_bytes(data)
                values[ph] = str(path)
        return fill(template, values)

    async def run(self, job: JobSpec, progress: Progress) -> tuple[bytes, str]:
        with tempfile.TemporaryDirectory(prefix="avos_wgp_") as t:
            tmp = Path(t)
            out_dir = tmp / "out"
            out_dir.mkdir()
            settings = tmp / "settings.json"
            settings.write_text(json.dumps(self.settings_for(job, tmp)), "utf-8")
            await progress(0.0, f"starting Wan2GP ({job.attention}, {job.precision})")
            self._proc = await asyncio.create_subprocess_exec(
                *self.command(settings, out_dir, job), cwd=str(config.WAN2GP_DIR),
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
            tail: list[str] = []
            assert self._proc.stdout is not None
            buf = b""
            while True:
                chunk = await self._proc.stdout.read(4096)
                if not chunk:
                    break
                buf += chunk
                parts = re.split(rb"[\r\n]", buf)
                buf = parts.pop()
                for raw in parts:
                    line = raw.decode("utf-8", "replace").strip()
                    if not line:
                        continue
                    tail = (tail + [line])[-20:]
                    m = STEP_RX.search(line)
                    if m and int(m.group(2)):
                        await progress(int(m.group(1)) / int(m.group(2)), f"step {m.group(1)}/{m.group(2)}")
            code = await self._proc.wait()
            self._proc = None
            if code != 0:
                raise RuntimeError(f"Wan2GP exited with {code}: " + " | ".join(tail[-5:]))
            outs = sorted((p for p in out_dir.rglob("*") if p.suffix.lower() in OUT_EXTS), key=lambda p: p.stat().st_mtime)
            want_video = job.want != "image"
            outs = [p for p in outs if (p.suffix.lower() in {".mp4", ".webm", ".mkv"}) == want_video] or outs
            if not outs:
                raise RuntimeError("Wan2GP finished but wrote no output file. " + " | ".join(tail[-3:]))
            return outs[-1].read_bytes(), outs[-1].suffix.lstrip(".").lower()

    async def cancel(self) -> None:
        if self._proc and self._proc.returncode is None:
            self._proc.terminate()
