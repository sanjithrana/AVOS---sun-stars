"""AVOS GPU worker API.

    GET    /health                 liveness (no token needed)
    GET    /status                 GPU, VRAM, temperature, precisions, kernels, backends + their models, loaded models, queue
    POST   /jobs                   queue a generation (the Model Router's choice: model, backend, precision, attention)
    GET    /jobs                   recent jobs
    GET    /jobs/{id}              status / progress / step / timing
    GET    /jobs/{id}/result       the output file
    DELETE /jobs/{id}              cancel (or forget a finished job)
    POST   /models/load            pre-load a model (warm it before a batch)
    POST   /models/unload          free a model's VRAM
    PUT    /workflows/{model}      save a ComfyUI API workflow sent by AVOS (Settings → Models uploads)
    POST   /downloads              download model files from Hugging Face into this machine's models folder
    GET    /downloads              downloads and their progress;  DELETE /downloads/{id} cancels
    GET    /browse?path=           folders on this machine (where to download);  POST /browse/mkdir
    POST   /files/check            which of these files are already here
"""
from __future__ import annotations

import base64
import binascii
import contextlib
import json
import re
import time
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse

from worker import config, downloads, gpu
from worker.adapters.base import JobSpec
from worker.jobs import Queue

MEDIA = {"mp4": "video/mp4", "webm": "video/webm", "mkv": "video/x-matroska", "gif": "image/gif", "png": "image/png",
         "jpg": "image/jpeg", "jpeg": "image/jpeg", "webp": "image/webp", "wav": "audio/wav", "flac": "audio/flac",
         "mp3": "audio/mpeg", "ogg": "audio/ogg", "m4a": "audio/mp4"}


def create_app(queue: Queue | None = None) -> FastAPI:
    state: dict[str, Any] = {"queue": queue}

    @contextlib.asynccontextmanager
    async def lifespan(_app: FastAPI):
        if state["queue"] is None:
            state["queue"] = Queue()
        state["queue"].start()
        yield
        await state["queue"].stop()

    app = FastAPI(title="AVOS GPU worker", version=config.VERSION, lifespan=lifespan)

    def q() -> Queue:
        return state["queue"]

    def auth(authorization: str | None = Header(default=None)) -> None:
        if config.TOKEN and authorization != f"Bearer {config.TOKEN}":
            raise HTTPException(401, "Missing or wrong token (GPU_WORKER_TOKEN).")

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {"ok": True, "name": config.NAME, "version": config.VERSION}

    @app.get("/status", dependencies=[Depends(auth)])
    async def status() -> dict[str, Any]:
        g = gpu.info()
        sup = gpu.supports(g)
        native = {"bf16" if sup.get("bf16") or not g else "fp16", "int8", "int4"} | \
            ({"fp8"} if sup.get("fp8") else set()) | ({"fp4"} if sup.get("fp4") else set())
        adapters: dict[str, Any] = {}
        for name, a in q().adapters.items():
            ok, why = await a.ready()
            precisions = [p for p in a.precisions if p in native]
            if len(a.attentions) == 1:          # fixed by the engine's own launch flags (ComfyUI)
                attention = a.attentions[0]
            else:                               # switchable per job: the fastest kernel installed here
                attention = gpu.best_attention(sup, tuple(a.attentions)) if g else "sdpa"
            adapters[name] = {"ready": ok, "why": why, "models": a.models() if ok else [], "precisions": precisions,
                              "attention": attention, **{k: v for k, v in a.describe().items() if k != "precisions"},
                              **({"device": "cpu", "offload": False} if gpu.is_cpu(g) else {})}
        running = q().running
        busy = running is not None
        loading = busy and running.status == "loading"
        return {
            "name": config.NAME, "worker_version": config.VERSION, "gpu": g, "supports": sup, "adapters": adapters,
            "loaded_models": [r.public() for r in q().residency.resident.values()],
            "queue_depth": q().queued(), "running": running.public() if running else None,
            "queue": [{"id": j.id, "model": j.spec.model, "task": j.spec.task, "priority": j.spec.priority,
                       "tag": j.spec.tag, "precision": j.spec.precision} for j in q().waiting()[:20]],
            "status": "loading" if loading else "generating" if busy else ("ready (CPU)" if gpu.is_cpu(g) else "ready" if g else "ready (no GPU)"),
            "avg_job_seconds": q().avg_job_seconds(), "cost_per_hour": config.COST_PER_HOUR,
            "reserve_gb": config.RESERVE_GB, "pinned": sorted(config.PINNED), "time": time.time(),
            "models_dir": config.MODELS_DIR,
            "downloads": [d for d in downloads.jobs() if d["status"] in ("queued", "running")],
        }

    @app.post("/jobs", dependencies=[Depends(auth)])
    def submit(body: dict[str, Any]) -> dict[str, Any]:
        for k in ("model", "adapter"):
            if not body.get(k):
                raise HTTPException(400, f"'{k}' is required.")
        try:
            inputs = {k: base64.b64decode(v, validate=True) for k, v in (body.get("inputs") or {}).items() if v}
        except (binascii.Error, ValueError) as e:
            raise HTTPException(400, f"inputs must be base64: {e}") from e
        try:
            job = q().submit(JobSpec.from_body(body, inputs))
        except (TypeError, ValueError) as e:
            raise HTTPException(400, str(e)) from e
        return job.public(q().position(job))

    @app.get("/jobs", dependencies=[Depends(auth)])
    def jobs() -> list[dict[str, Any]]:
        return [q().jobs[j].public(q().position(q().jobs[j])) for j in reversed(q().order[-50:]) if j in q().jobs]

    @app.get("/jobs/{job_id}", dependencies=[Depends(auth)])
    def job(job_id: str) -> dict[str, Any]:
        j = q().jobs.get(job_id)
        if j is None:
            raise HTTPException(404, "No such job.")
        return j.public(q().position(j))

    @app.get("/jobs/{job_id}/result", dependencies=[Depends(auth)])
    def result(job_id: str) -> FileResponse:
        j = q().jobs.get(job_id)
        if j is None or j.status != "done" or not j.result:
            raise HTTPException(404, "No result for this job (not finished, failed, or already fetched).")
        return FileResponse(j.result, media_type=MEDIA.get(j.ext or "", "application/octet-stream"),
                            filename=f"{j.spec.model}.{j.ext}")

    @app.delete("/jobs/{job_id}", dependencies=[Depends(auth)])
    async def delete(job_id: str) -> dict[str, Any]:
        j = q().jobs.get(job_id)
        if j is None:
            raise HTTPException(404, "No such job.")
        if j.status in ("queued", "loading", "running"):
            await q().cancel(job_id)
            return {"ok": True, "cancelled": True}
        q().forget(job_id)
        return {"ok": True, "forgotten": True}

    @app.post("/models/load", dependencies=[Depends(auth)])
    def load(body: dict[str, Any]) -> dict[str, Any]:
        """Warm a model: queued like a job that only loads (no output)."""
        body = {**body, "want": "none"}
        try:
            job = q().submit(JobSpec.from_body({**body, "prompt": "", "task": "load"}, {}))
        except (TypeError, ValueError) as e:
            raise HTTPException(400, str(e)) from e
        return job.public(q().position(job))

    @app.post("/models/unload", dependencies=[Depends(auth)])
    async def unload(body: dict[str, Any]) -> dict[str, Any]:
        r = q().residency.get(body.get("model", ""), body.get("adapter", ""))
        if r is None:
            raise HTTPException(404, "That model isn't loaded.")
        await q().residency._evict(r)
        return {"ok": True}

    # ---- model downloads (from the AVOS Models page) ----
    @app.post("/downloads", dependencies=[Depends(auth)])
    async def start_download(body: dict[str, Any]) -> dict[str, Any]:
        dest = body.get("dest") or config.MODELS_DIR
        try:
            Path(dest).mkdir(parents=True, exist_ok=True)
            if not downloads.allowed(dest):
                raise ValueError(f"Downloads can only go under {', '.join(downloads.roots())}.")
            job = downloads.start(files=body.get("files") or [], dest=dest, label=str(body.get("label") or ""),
                                  model=body.get("model"), variant=body.get("variant"))
        except (ValueError, OSError) as e:
            raise HTTPException(400, str(e)) from e
        return job.public()

    @app.get("/downloads", dependencies=[Depends(auth)])
    def list_downloads() -> list[dict[str, Any]]:
        return downloads.jobs()

    @app.delete("/downloads/{job_id}", dependencies=[Depends(auth)])
    def cancel_download(job_id: str) -> dict[str, Any]:
        j = downloads.get(job_id)
        if j is None:
            raise HTTPException(404, "No such download.")
        if j.status in ("queued", "running"):
            downloads.cancel(job_id)
        else:
            downloads.forget(job_id)
        return {"ok": True}

    @app.get("/browse", dependencies=[Depends(auth)])
    def browse(path: str | None = None) -> dict[str, Any]:
        try:
            if not path:
                Path(config.MODELS_DIR).mkdir(parents=True, exist_ok=True)
            return {**downloads.browse(path or config.MODELS_DIR), "default": config.MODELS_DIR}
        except ValueError as e:
            raise HTTPException(400, str(e)) from e

    @app.post("/browse/mkdir", dependencies=[Depends(auth)])
    def mkdir(body: dict[str, Any]) -> dict[str, Any]:
        try:
            return {"path": downloads.mkdir(str(body.get("path") or ""), str(body.get("name") or ""))}
        except (ValueError, OSError) as e:
            raise HTTPException(400, str(e)) from e

    @app.post("/files/check", dependencies=[Depends(auth)])
    def check_files(body: dict[str, Any]) -> dict[str, Any]:
        return {"dest": body.get("dest") or config.MODELS_DIR,
                "present": downloads.check(body.get("dest") or config.MODELS_DIR, body.get("files") or [])}

    @app.put("/workflows/{model}", dependencies=[Depends(auth)])
    def put_workflow(model: str, body: dict[str, Any]) -> dict[str, Any]:
        """AVOS pushes the workflows uploaded in its Settings, so they only have to be uploaded once."""
        if not re.fullmatch(r"[a-z0-9][a-z0-9._-]{1,63}", model):
            raise HTTPException(400, "Bad model id.")
        if not body or not all(isinstance(v, dict) and "class_type" in v for v in body.values()):
            raise HTTPException(400, "Not a ComfyUI API-format workflow (Export (API) in ComfyUI).")
        from worker import autowire
        wired: dict[str, list[str]] = {}
        if autowire.needs_wiring(body):
            body, wired = autowire.autowire(body)
        config.COMFYUI_WORKFLOWS.mkdir(parents=True, exist_ok=True)
        (config.COMFYUI_WORKFLOWS / f"{model}.json").write_text(json.dumps(body, indent=1), "utf-8")
        return {"ok": True, "model": model, "autowired": autowire.describe(wired) if wired else None}

    return app


app = create_app()
