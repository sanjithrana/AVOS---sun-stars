"""Run one generation on a GPU worker: submit → follow progress → download the result.

    data = await run_on_worker(placement, job, inputs={"image": png}, params={...}, timeout=900)

The worker queues jobs (one GPU job at a time), loads the model at the chosen precision (keeping it loaded for the
next shot), runs it through the chosen backend (ComfyUI / Wan2GP / Diffusers) and keeps the output until we fetch it.
"""
from __future__ import annotations

import asyncio
import base64
import time
from typing import Any

import httpx

from agentic_core.model_fabric import dispatch, workers
from agentic_core.model_fabric.telemetry import Job


class WorkerJobError(RuntimeError):
    pass


def _worker(worker_id: str) -> dict[str, Any]:
    w = next((w for w in workers.configured() if w["id"] == worker_id), None)
    if w is None:
        raise WorkerJobError(f"GPU worker '{worker_id}' is no longer configured (Settings → GPU workers).")
    return w


async def run_on_worker(placement: Any, job: Job, *, prompt: str, negative_prompt: str = "", width: int, height: int,
                        seconds: float = 0.0, seed: int | None = None, steps: int | None = None,
                        frames: int | None = None, fps: int | None = None,
                        inputs: dict[str, bytes | None] | None = None, want: str = "video",
                        timeout: float = 1800.0, poll: float = 2.0) -> bytes:
    w = _worker(placement.worker_id)
    body = {
        "model": placement.model, "adapter": placement.adapter, "precision": placement.precision,
        "attention": placement.attention, "offload": placement.offload, "task": job.task, "want": want,
        "prompt": prompt, "negative_prompt": negative_prompt, "width": int(width), "height": int(height),
        "seconds": float(seconds), "frames": frames, "fps": fps, "vram_gb": placement.vram_gb,
        "seed": None if seed is None else int(seed) % 2_147_483_647, "steps": steps,
        "inputs": {k: base64.b64encode(v).decode() for k, v in (inputs or {}).items() if v},
        "timeout": timeout, "priority": dispatch.current_priority(), "tag": dispatch.current_tag(),
    }
    deadline = time.monotonic() + timeout
    with dispatch.reserve(placement):
        return await _submit_and_follow(w, placement, job, body, deadline, timeout, poll)


async def _submit_and_follow(w: dict[str, Any], placement: Any, job: Job, body: dict[str, Any], deadline: float,
                             timeout: float, poll: float) -> bytes:
    async with httpx.AsyncClient(timeout=60.0, headers=workers.headers()) as client:
        try:
            r = await client.post(f"{w['url']}/jobs", json=body)
        except httpx.HTTPError as exc:
            workers.forget(w["id"])
            raise WorkerJobError(f"Can't reach GPU worker {w.get('name')} at {w['url']}: {exc}") from exc
        if r.status_code >= 400:
            raise WorkerJobError(f"GPU worker {w.get('name')} refused the job ({r.status_code}): {r.text[:400]}")
        remote = r.json()["id"]
        await job.progress(0.0, "queued", force=True)
        started = False
        try:
            while True:
                if time.monotonic() > deadline:
                    await client.delete(f"{w['url']}/jobs/{remote}")
                    raise WorkerJobError(f"The GPU job took longer than the {timeout:.0f} s limit and was cancelled.")
                s = (await client.get(f"{w['url']}/jobs/{remote}")).json()
                state = s.get("status")
                if state in ("loading", "running") and not started:
                    started = True
                    await job.started(remote)
                if state in ("queued", "loading", "running"):
                    await job.progress(float(s.get("progress") or 0.0), s.get("step") or state)
                elif state == "done":
                    if not started:
                        await job.started(remote)
                    job.gpu_seconds = s.get("gpu_seconds")
                    job.actual = {"warm": bool(s.get("warm")), "load_seconds": s.get("load_seconds"),
                                  "evicted": s.get("evicted") or []}
                    workers.forget(w["id"])     # its loaded models / queue changed: re-read before the next route
                    res = await client.get(f"{w['url']}/jobs/{remote}/result")
                    if res.status_code >= 400:
                        raise WorkerJobError(f"Could not download the result from {w.get('name')}: {res.text[:200]}")
                    await client.delete(f"{w['url']}/jobs/{remote}")
                    if job.gpu_seconds is not None:
                        job.cost_usd = round(float(workers_cost(w, placement)) * float(job.gpu_seconds) / 3600.0, 4)
                    return res.content
                else:   # error / cancelled
                    raise WorkerJobError(f"{placement.model_name} on {w.get('name')} failed: {s.get('error') or state}")
                # pictures finish in seconds: look more often; deep in a queue: less often
                pos = s.get("position")
                await asyncio.sleep(min(poll, 0.5) if job.task == "image" and not pos else poll * (2 if pos and pos > 2 else 1))
        except asyncio.CancelledError:
            try:
                await client.delete(f"{w['url']}/jobs/{remote}")
            finally:
                raise


def workers_cost(w: dict[str, Any], placement: Any) -> float:
    if w.get("cost_per_hour") is not None:
        return float(w["cost_per_hour"])
    hit = next((s for s in workers.cached() if s.id == w["id"]), None)
    return hit.cost_per_hour if hit else 0.0


async def prewarm(requests: list[Any], *, tag: str = "warm-up") -> list[dict[str, Any]]:
    """Load the models these jobs will need on the GPUs the router would pick, before the jobs arrive (e.g. while
    the physics stage runs). Different jobs go to different workers when one is nearly as good, so with two GPUs the
    picture model and the video model are each loaded once and stay put. Nothing happens on hosted backends or
    when the model is already loaded."""
    from agentic_core.model_fabric import router

    done: list[dict[str, Any]] = []
    used: set[str] = set()
    for req in requests:
        try:
            plan = await router.plan(req)
        except Exception:  # noqa: BLE001 - warm-up is best effort
            continue
        gpu = [p for p in plan.placements if p.backend == "gpu"]
        if not gpu or plan.placements[0].backend != "gpu":
            continue
        best = next((p for p in gpu[:4] if p.worker_id not in used and p.score >= gpu[0].score * 0.9), gpu[0])
        used.add(best.worker_id)
        if best.warm:
            done.append({"model": best.model, "worker": best.worker_name, "already": True})
            continue
        w = next((x for x in workers.configured() if x["id"] == best.worker_id), None)
        if w is None:
            continue
        try:
            async with httpx.AsyncClient(timeout=10.0, headers=workers.headers()) as client:
                r = await client.post(f"{w['url']}/models/load", json={
                    "model": best.model, "adapter": best.adapter, "precision": best.precision,
                    "vram_gb": best.vram_gb, "attention": best.attention, "offload": best.offload, "tag": tag})
            if r.status_code < 400:
                from agentic_core.model_fabric import requirements as R
                from agentic_core.models import catalog

                load_s = float(R.fabric_of(catalog.get(best.model)).get("load_seconds") or 60)
                dispatch.note(best.worker_id, best.model, best.adapter, best.precision, load_s, tag=tag)
                workers.forget(best.worker_id)
                done.append({"model": best.model, "worker": best.worker_name, "precision": best.precision})
        except httpx.HTTPError:
            continue
    return done
