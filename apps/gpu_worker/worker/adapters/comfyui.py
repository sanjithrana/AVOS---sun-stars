"""ComfyUI running next to the worker (same GPU machine): one exported API-format workflow per model.

Workflows live in COMFYUI_WORKFLOW_DIR/<model id>.json (the same files as AVOS's apps/comfyui_workflows). The
placeholders are the same as AVOS's, plus two the router fills:

    {{PROMPT}} {{NEGATIVE_PROMPT}} {{SEED}} {{WIDTH}} {{HEIGHT}} {{FRAMES}} {{FPS}} {{DURATION}} {{STEPS}}
    {{IMAGE}} {{AUDIO}} {{VIDEO}}           input files (uploaded to ComfyUI first)
    {{IMAGE2}} {{IMAGE3}} {{IMAGE4}}        extra reference pictures (Qwen-Image-Edit: character sheets, the location)
    {{WEIGHT_DTYPE}}                        the precision, as a ComfyUI weight_dtype: default (bf16) / fp8_e4m3fn(_fast)
    {{LYRICS}} {{LANGUAGE}}                 music / speech workflows (job options; "[instrumental]" when none)

Jobs that want "audio" return the first saved audio file (Save Audio: flac / mp3 / wav / ogg).

Progress comes from ComfyUI's websocket (per sampler step). ComfyUI keeps the last workflow's models loaded by
itself; unloading calls its /free endpoint. Attention is a ComfyUI launch flag (--use-sage-attention): tell the
worker with COMFYUI_ATTENTION=sage so the router knows.
"""
from __future__ import annotations

import asyncio
import copy
import json
import time
import uuid
from pathlib import Path
from typing import Any

import httpx

from worker import config, gpu
from worker.adapters.base import Adapter, JobSpec, Progress

NUMERIC = ("{{SEED}}", "{{WIDTH}}", "{{HEIGHT}}", "{{FRAMES}}", "{{FPS}}", "{{DURATION}}", "{{STEPS}}")
FILES = {"{{IMAGE}}": ("image", "png"), "{{AUDIO}}": ("audio", "wav"), "{{VIDEO}}": ("video", "mp4"),
         "{{IMAGE2}}": ("image2", "png"), "{{IMAGE3}}": ("image3", "png"), "{{IMAGE4}}": ("image4", "png")}
TEXTS = ("{{PROMPT}}", "{{NEGATIVE_PROMPT}}", "{{LYRICS}}", "{{LANGUAGE}}")
VIDEO_EXTS = (".mp4", ".webm", ".mov", ".mkv", ".gif")
IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".webp")
AUDIO_EXTS = (".flac", ".wav", ".mp3", ".ogg", ".m4a")


def wanted_exts(want: str) -> tuple[str, ...]:
    return IMAGE_EXTS if want == "image" else AUDIO_EXTS if want == "audio" else VIDEO_EXTS


def fill(node: Any, values: dict[str, Any]) -> Any:
    if isinstance(node, dict):
        return {k: fill(v, values) for k, v in node.items()}
    if isinstance(node, list):
        return [fill(v, values) for v in node]
    if isinstance(node, str):
        s = node.strip()
        if s in values and (s in NUMERIC or s in FILES or s == "{{WEIGHT_DTYPE}}"):
            return values[s]
        out = node
        for key in TEXTS:
            out = out.replace(key, str(values.get(key, "")))
        return out
    return node


def weight_dtype(precision: str) -> str:
    if precision == "fp8":
        try:
            cc = float((gpu.info() or {}).get("compute_capability") or 0)
        except ValueError:
            cc = 0
        return "fp8_e4m3fn_fast" if cc >= 8.9 else "fp8_e4m3fn"
    return "default"


def cpu_size(job: JobSpec) -> None:
    """On a CPU: draw small (AVOS scales the result up to the film's size) and keep clips short (it holds the last
    frame). Diffusion time grows with pixels × frames, so this is what makes a CPU usable at all."""
    side = max(job.width, job.height)
    if side > config.CPU_MAX_SIDE:
        k = config.CPU_MAX_SIDE / side
        job.width, job.height = max(256, int(job.width * k) // 32 * 32), max(256, int(job.height * k) // 32 * 32)
    if job.task in ("video", "avatar", "control") and job.seconds > config.CPU_MAX_SECONDS:
        fps = job.fps or (round((job.frames - 1) / job.seconds) if job.frames and job.seconds else 16)
        job.seconds = config.CPU_MAX_SECONDS
        if job.frames:
            mult = 8 if (job.frames - 1) % 8 == 0 else 4
            job.frames = max(9, (round(job.seconds * fps) // mult) * mult + 1)


class ComfyUIAdapter(Adapter):
    name = "comfyui"
    precisions = ("bf16", "fp8")
    offload = True

    def __init__(self) -> None:
        self._ready: tuple[float, bool, str | None] = (0.0, False, None)
        self._prompt_id: str | None = None
        self.attentions = (config.COMFYUI_ATTENTION,)

    async def ready(self) -> tuple[bool, str | None]:
        t, ok, why = self._ready
        if time.monotonic() - t < 10:
            return ok, why
        try:
            async with httpx.AsyncClient(timeout=3) as c:
                r = await c.get(f"{config.COMFYUI_URL}/system_stats")
            ok, why = (r.status_code == 200), (None if r.status_code == 200 else f"ComfyUI answered {r.status_code}")
        except httpx.HTTPError:
            ok, why = False, f"ComfyUI isn't running at {config.COMFYUI_URL} (start it with --listen, or set COMFYUI_URL)."
        if ok and not self.models():
            ok, why = False, f"No workflows in {config.COMFYUI_WORKFLOWS} (export each model's workflow as <model id>.json)."
        self._ready = (time.monotonic(), ok, why)
        return ok, why

    def models(self) -> list[str]:
        d = config.COMFYUI_WORKFLOWS
        return sorted(p.stem for p in d.glob("*.json")) if d.is_dir() else []

    def _workflow(self, model: str) -> dict[str, Any]:
        p = config.COMFYUI_WORKFLOWS / f"{model}.json"
        data = json.loads(p.read_text("utf-8"))
        if "nodes" in data and "links" in data:
            raise RuntimeError(f"{p.name} is a regular ComfyUI save, not the API format (Workflow → Export (API)).")
        from worker import autowire
        if autowire.needs_wiring(data):      # a plain export dropped into the folder: wire the prompt, image, seed … here
            data, _ = autowire.autowire(data)
        return data

    async def unload(self, model: str) -> None:
        try:
            async with httpx.AsyncClient(timeout=30) as c:
                await c.post(f"{config.COMFYUI_URL}/free", json={"unload_models": True, "free_memory": True})
        except httpx.HTTPError:
            pass

    async def _upload(self, c: httpx.AsyncClient, data: bytes, ext: str) -> str:
        if ext == "png" and data[:3] == b"\xff\xd8\xff":
            ext = "jpg"
        if ext == "wav" and (data[:3] == b"ID3" or data[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2")):
            ext = "mp3"
        name = f"avos_{uuid.uuid4().hex[:12]}.{ext}"
        r = await c.post(f"{config.COMFYUI_URL}/upload/image", files={"image": (name, data, "application/octet-stream")},
                         data={"overwrite": "true"})
        if r.status_code >= 400:
            raise RuntimeError(f"ComfyUI upload failed: {r.text[:300]}")
        info = r.json()
        return f"{info['subfolder']}/{info['name']}" if info.get("subfolder") else info["name"]

    async def _ws_progress(self, client_id: str, prompt_id: str, progress: Progress, done: asyncio.Event) -> None:
        try:
            import websockets
        except ImportError:
            return
        url = config.COMFYUI_URL.replace("http", "ws", 1) + f"/ws?clientId={client_id}"
        try:
            async with websockets.connect(url, max_size=None, open_timeout=5) as ws:
                while not done.is_set():
                    try:
                        msg = await asyncio.wait_for(ws.recv(), 1.0)
                    except asyncio.TimeoutError:
                        continue
                    if isinstance(msg, bytes):
                        continue          # preview images
                    m = json.loads(msg)
                    d = m.get("data") or {}
                    if m.get("type") == "progress" and d.get("max"):
                        await progress(float(d["value"]) / float(d["max"]), f"step {d['value']}/{d['max']}")
                    elif m.get("type") == "executing" and d.get("node"):
                        await progress(-1, f"node {d['node']}")
        except Exception:  # noqa: BLE001 - progress is best effort
            return

    async def run(self, job: JobSpec, progress: Progress) -> tuple[bytes, str]:
        if gpu.is_cpu():
            cpu_size(job)
        wf = self._workflow(job.model)
        text = json.dumps(wf)
        for ph, (key, _) in FILES.items():
            if ph in text and not job.inputs.get(key):
                raise RuntimeError(f"The {job.model} workflow needs {key} ({ph}) and the job has none.")
        client_id = str(uuid.uuid4())
        async with httpx.AsyncClient(timeout=120) as c:
            names = {ph: await self._upload(c, job.inputs[key], ext) for ph, (key, ext) in FILES.items()
                     if ph in text and job.inputs.get(key)}
            values = {"{{PROMPT}}": job.prompt, "{{NEGATIVE_PROMPT}}": job.negative_prompt,
                      "{{SEED}}": int(job.seed if job.seed is not None else time.time()) % 2_147_483_647,
                      "{{WIDTH}}": job.width - job.width % 32, "{{HEIGHT}}": job.height - job.height % 32,
                      "{{FRAMES}}": int(job.frames or max(1, round(job.seconds * (job.fps or 16)) + 1)),
                      "{{FPS}}": int(job.fps or 16), "{{DURATION}}": round(job.seconds, 2), "{{STEPS}}": int(job.steps or 20),
                      "{{WEIGHT_DTYPE}}": weight_dtype(job.precision),
                      "{{LYRICS}}": str(job.options.get("lyrics") or "[instrumental]"),
                      "{{LANGUAGE}}": str(job.options.get("language") or "en"), **names}
            graph = fill(copy.deepcopy(wf), values)
            done = asyncio.Event()
            watcher = asyncio.create_task(self._ws_progress(client_id, "", progress, done))
            try:
                r = await c.post(f"{config.COMFYUI_URL}/prompt", json={"prompt": graph, "client_id": client_id})
                if r.status_code >= 400:
                    raise RuntimeError(f"ComfyUI rejected the workflow: {r.text[:800]}")
                self._prompt_id = r.json()["prompt_id"]
                outputs = await self._wait(c, self._prompt_id, job.timeout)
            finally:
                done.set()
                watcher.cancel()
                self._prompt_id = None
            files = [i for out in outputs.values() for items in out.values() if isinstance(items, list)
                     for i in items if isinstance(i, dict) and "filename" in i and i.get("type", "output") == "output"]
            files = [f for f in files if f["filename"].lower().endswith(wanted_exts(job.want))]
            if not files:
                raise RuntimeError("ComfyUI finished but saved no " + {
                    "image": "image ('Save Image').", "audio": "audio ('Save Audio')."}.get(
                    job.want, "video ('Save Video' MP4 or 'Video Combine')."))
            f = sorted(files, key=lambda f: 0 if f["filename"].lower().endswith((".mp4", ".png", ".flac", ".wav")) else 1)[0]
            v = await c.get(f"{config.COMFYUI_URL}/view", params={"filename": f["filename"], "subfolder": f.get("subfolder", ""),
                                                                  "type": f.get("type", "output")})
            if v.status_code >= 400:
                raise RuntimeError(f"Could not download {f['filename']} from ComfyUI.")
            return v.content, Path(f["filename"]).suffix.lstrip(".").lower()

    async def _wait(self, c: httpx.AsyncClient, prompt_id: str, timeout: float) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        while True:
            r = await c.get(f"{config.COMFYUI_URL}/history/{prompt_id}")
            if r.status_code == 200 and (entry := r.json().get(prompt_id)):
                st = entry.get("status") or {}
                if st.get("status_str") == "error":
                    msgs = [m for m in st.get("messages", []) if m and m[0] == "execution_error"]
                    raise RuntimeError("ComfyUI workflow failed: " + (msgs[-1][1].get("exception_message") if msgs else "unknown error"))
                if st.get("completed", True):
                    return entry.get("outputs") or {}
            if time.monotonic() > deadline:
                raise RuntimeError(f"ComfyUI did not finish within {timeout:.0f} s.")
            await asyncio.sleep(1.5)

    async def cancel(self) -> None:
        try:
            async with httpx.AsyncClient(timeout=10) as c:
                await c.post(f"{config.COMFYUI_URL}/interrupt")
        except httpx.HTTPError:
            pass
