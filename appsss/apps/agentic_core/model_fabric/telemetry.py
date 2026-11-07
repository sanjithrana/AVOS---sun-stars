"""Generation job telemetry: every run the fabric makes, wherever it runs, reported to whoever is listening.

The API installs a sink for the shot being generated (`with_sink`); the sink stores a gpu_jobs row and publishes
GPU_JOB_QUEUED / STARTED / PROGRESS / COMPLETED / FAILED live events. Without a sink (tests, the Animation Studio)
events are simply dropped.

    async with track(placement, task="video", units=5.0) as job:
        job.started(); job.progress(0.4, "sampling")
        ...                                   # completed / failed are recorded automatically
"""
from __future__ import annotations

import contextlib
import contextvars
import logging
import time
import uuid
from typing import Any, AsyncIterator, Awaitable, Callable

logger = logging.getLogger(__name__)

Sink = Callable[[dict[str, Any]], Awaitable[None]]
_sink: contextvars.ContextVar[Sink | None] = contextvars.ContextVar("avos_fabric_sink", default=None)
PROGRESS_EVERY = 3.0


@contextlib.contextmanager
def with_sink(sink: Sink | None):
    token = _sink.set(sink)
    try:
        yield
    finally:
        _sink.reset(token)


async def emit(event: dict[str, Any]) -> None:
    sink = _sink.get()
    if sink is None:
        return
    try:
        await sink(event)
    except Exception:  # noqa: BLE001 - telemetry must never break a generation
        logger.warning("fabric telemetry sink failed", exc_info=True)


class Job:
    def __init__(self, placement: Any, task: str, units: float) -> None:
        self.id = str(uuid.uuid4())
        self.placement = placement
        self.task = task
        self.units = units
        self.t0 = time.monotonic()
        self.started_at: float | None = None
        self.gpu_seconds: float | None = None   # the worker's own measurement, when it has one
        self.cost_usd: float | None = None
        self.remote_id: str | None = None
        self.actual: dict[str, Any] = {}       # what really happened on the worker (warm, load_seconds, evicted)
        self._last_progress = 0.0

    def base(self) -> dict[str, Any]:
        p = self.placement
        return {"job_id": self.id, "task": self.task, "units": self.units, **(p.as_dict() if hasattr(p, "as_dict") else {})}

    async def started(self, remote_id: str | None = None) -> None:
        self.started_at = time.monotonic()
        self.remote_id = remote_id or self.remote_id
        await emit({"kind": "started", **self.base(), "remote_id": self.remote_id})

    async def progress(self, fraction: float, step: str | None = None, force: bool = False) -> None:
        now = time.monotonic()
        if not force and now - self._last_progress < PROGRESS_EVERY:
            return
        self._last_progress = now
        await emit({"kind": "progress", **self.base(), "progress": max(0.0, min(1.0, float(fraction))), "step": step})


@contextlib.asynccontextmanager
async def track(placement: Any, *, task: str, units: float) -> AsyncIterator[Job]:
    job = Job(placement, task, units)
    await emit({"kind": "queued", **job.base()})
    try:
        yield job
    except BaseException as exc:
        await emit({"kind": "failed", **job.base(), "error": str(exc)[:500] or type(exc).__name__,
                    "wall_seconds": round(time.monotonic() - job.t0, 2)})
        raise
    else:
        wall = time.monotonic() - job.t0
        run = job.gpu_seconds if job.gpu_seconds is not None else (time.monotonic() - (job.started_at or job.t0))
        await emit({"kind": "completed", **job.base(), **job.actual, "wall_seconds": round(wall, 2), "gpu_seconds": round(run, 2),
                    "cost_usd": job.cost_usd if job.cost_usd is not None else getattr(placement, "est_cost", 0.0)})
