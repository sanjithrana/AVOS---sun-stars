"""The worker's job queue: one GPU job at a time, models kept loaded between jobs, results kept until fetched.

    queued → loading (make room in VRAM, load the model at the chosen precision) → running → done | error | cancelled
"""
from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from worker import config, gpu
from worker.adapters import build
from worker.adapters.base import Adapter, JobSpec
from worker.vram import Residency, Resident


@dataclass
class Job:
    spec: JobSpec
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    status: str = "queued"
    progress: float = 0.0
    step: str = "queued"
    error: str | None = None
    created_at: float = field(default_factory=time.time)
    started_at: float | None = None
    finished_at: float | None = None
    run_started: float | None = None
    gpu_seconds: float | None = None
    load_seconds: float | None = None
    warm: bool = False
    evicted: list[str] = field(default_factory=list)
    result: str | None = None
    ext: str | None = None

    def public(self, position: int | None = None) -> dict[str, Any]:
        s = self.spec
        return {"id": self.id, "status": self.status, "progress": round(self.progress, 3), "step": self.step,
                "error": self.error, "model": s.model, "adapter": s.adapter, "precision": s.precision,
                "attention": s.attention, "offload": s.offload, "task": s.task, "created_at": self.created_at,
                "started_at": self.started_at, "finished_at": self.finished_at, "gpu_seconds": self.gpu_seconds,
                "load_seconds": self.load_seconds, "warm": self.warm, "evicted": self.evicted, "ext": self.ext,
                "position": position, "priority": s.priority, "tag": s.tag}


class Queue:
    def __init__(self, adapters: dict[str, Adapter] | None = None) -> None:
        self.adapters = adapters if adapters is not None else build()
        self.jobs: dict[str, Job] = {}
        self.order: list[str] = []
        self.running: Job | None = None
        self.avg_seconds: dict[str, float] = {}
        self._wake = asyncio.Event()
        self._task: asyncio.Task | None = None
        self._run_task: asyncio.Task | None = None
        g = lambda: gpu.info(max_age=0) or {}  # noqa: E731
        self.residency = Residency(total_gb=lambda: float(g().get("vram_gb") or 0) or 1e9,
                                   free_gb=lambda: (None if g().get("fake") or "free_vram_gb" not in g() else float(g()["free_vram_gb"])),
                                   unload=self._unload)
        config.RESULTS.mkdir(parents=True, exist_ok=True)

    async def _unload(self, r: Resident) -> None:
        a = self.adapters.get(r.adapter)
        if a:
            await a.unload(r.model)

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()

    # ---- API ----
    def submit(self, spec: JobSpec) -> Job:
        if spec.adapter not in self.adapters:
            raise ValueError(f"This worker has no '{spec.adapter}' backend (it has: {', '.join(self.adapters) or 'none'}).")
        job = Job(spec)
        self.jobs[job.id] = job
        self.order.append(job.id)
        self._wake.set()
        return job

    def waiting(self) -> list[Job]:
        """Queued jobs in the order they will run: priority first (0 = most urgent), then arrival."""
        idx = {j: i for i, j in enumerate(self.order)}
        q = [self.jobs[j] for j in self.order if j in self.jobs and self.jobs[j].status == "queued"]
        return sorted(q, key=lambda j: (j.spec.priority, idx[j.id]))

    def position(self, job: Job) -> int | None:
        if job.status != "queued":
            return None
        ids = [j.id for j in self.waiting()]
        return ids.index(job.id) if job.id in ids else None

    def queued(self) -> int:
        return sum(1 for j in self.jobs.values() if j.status == "queued")

    async def cancel(self, job_id: str) -> Job | None:
        job = self.jobs.get(job_id)
        if job is None:
            return None
        if job.status == "queued":
            job.status, job.step, job.finished_at = "cancelled", "cancelled", time.time()
        elif job.status in ("loading", "running") and self.running is job:
            await self.adapters[job.spec.adapter].cancel()
            if self._run_task:
                self._run_task.cancel()
        return job

    def forget(self, job_id: str) -> None:
        job = self.jobs.pop(job_id, None)
        if job and job.result:
            try:
                from pathlib import Path

                Path(job.result).unlink(missing_ok=True)
            except OSError:
                pass
        if job_id in self.order:
            self.order.remove(job_id)

    def avg_job_seconds(self) -> float | None:
        vals = list(self.avg_seconds.values())
        return round(sum(vals) / len(vals), 1) if vals else None

    # ---- execution ----
    async def _loop(self) -> None:
        while True:
            waiting = self.waiting()
            nxt = waiting[0] if waiting else None
            if nxt is None:
                self._wake.clear()
                self._gc()
                try:
                    await asyncio.wait_for(self._wake.wait(), 30)
                except asyncio.TimeoutError:
                    pass
                continue
            self.running = nxt
            self._run_task = asyncio.create_task(self._run(nxt))
            try:
                await self._run_task
            except asyncio.CancelledError:
                if nxt.status not in ("done", "error"):
                    nxt.status, nxt.step, nxt.finished_at = "cancelled", "cancelled", time.time()
                if self._task and self._task.cancelling():
                    raise
            finally:
                self.running = None
                self._run_task = None

    async def _run(self, job: Job) -> None:
        spec = job.spec
        adapter = self.adapters[spec.adapter]
        job.started_at = time.time()

        async def progress(frac: float, step: str) -> None:
            if frac >= 0:
                job.progress = max(job.progress, min(1.0, frac)) if job.status == "running" else job.progress
            job.step = step

        try:
            ok, why = await adapter.ready()
            if not ok:
                raise RuntimeError(why or f"{spec.adapter} isn't ready")
            if spec.model not in adapter.models():
                raise RuntimeError(f"{spec.adapter} on this worker can't run {spec.model}.")
            job.status, job.step = "loading", "loading"
            resident = self.residency.get(spec.model, spec.adapter)
            job.warm = bool(adapter.keeps_loaded and resident and resident.precision == spec.precision)
            if not job.warm:
                t0 = time.monotonic()
                need = float(spec.vram_gb or 0)
                evicted = await self.residency.make_room(spec.model, spec.adapter, spec.precision, need)
                job.evicted = [f"{r.model} ({r.precision})" for r in evicted]
                await adapter.load(spec, progress)
                job.load_seconds = round(time.monotonic() - t0, 2)
                if adapter.keeps_loaded:
                    self.residency.loaded(spec.model, spec.adapter, spec.precision, need)
            self.residency.touch(spec.model, spec.adapter)
            if spec.task == "load":               # POST /models/load: warm only
                job.status, job.step, job.progress = "done", "loaded", 1.0
                return
            job.status, job.step, job.progress = "running", "running", 0.0
            job.run_started = time.monotonic()
            data, ext = await asyncio.wait_for(adapter.run(spec, progress), timeout=spec.timeout)
            job.gpu_seconds = round(time.monotonic() - job.run_started + (job.load_seconds or 0), 2)
            path = config.RESULTS / f"{job.id}.{ext}"
            path.write_bytes(data)
            job.result, job.ext = str(path), ext
            job.status, job.step, job.progress = "done", "done", 1.0
            key = f"{spec.model}|{spec.adapter}"
            prev = self.avg_seconds.get(key)
            total = time.time() - job.started_at
            self.avg_seconds[key] = total if prev is None else 0.7 * prev + 0.3 * total
        except asyncio.CancelledError:
            job.status, job.step = "cancelled", "cancelled"
            raise
        except asyncio.TimeoutError:
            job.status, job.error = "error", f"Took longer than the {spec.timeout:.0f} s limit."
            await adapter.cancel()
        except Exception as exc:  # noqa: BLE001 - reported to AVOS
            job.status, job.error = "error", str(exc)[:1000] or type(exc).__name__
            if not adapter.keeps_loaded:
                self.residency.forget(spec.model, spec.adapter)
        finally:
            job.finished_at = time.time()

    def _gc(self) -> None:
        now = time.time()
        for jid, job in list(self.jobs.items()):
            if job.finished_at and now - job.finished_at > config.RESULT_TTL:
                self.forget(jid)
