"""The API side of the Model Fabric (agentic_core.model_fabric).

- `shot_context(project, shot_id, version)`: while a shot is generated, the project's generation limits apply
  (policy.use) and every run is reported (telemetry.with_sink) → one gpu_jobs row per run + GPU_JOB_* live events.
- `load_performance()`: aggregates gpu_jobs into the router's measured speed / success / QA per (model, where).
- `record_qa(shot_id, version, score)`: the QA score of a shot's result is written onto its gpu_jobs rows, so the
  router learns which model / GPU produces results that pass.

Rows are written in their own short sessions (not the generation's transaction) so the GPU page sees a job the
moment it is queued and follows its progress live, even while the shot's own transaction is still open.
"""
from __future__ import annotations

import asyncio
import contextlib
import logging
from datetime import datetime, timezone
from typing import Any, Iterator

from sqlalchemy import case, func, select, update

from agentic_core.model_fabric import performance, policy, telemetry
from packages.contracts.event import EventType
from src.core.events.event_bus import get_event_bus
from src.core.events.factory import make_event
from src.database.models.gpu_job import GpuJob

logger = logging.getLogger(__name__)

KIND_EVENT = {
    "queued": EventType.GPU_JOB_QUEUED, "started": EventType.GPU_JOB_STARTED,
    "progress": EventType.GPU_JOB_PROGRESS, "completed": EventType.GPU_JOB_COMPLETED,
    "failed": EventType.GPU_JOB_FAILED,
}
PLACEMENT_FIELDS = ("model", "backend", "worker_id", "worker_name", "gpu", "adapter", "precision", "attention",
                    "offload", "warm", "where", "est_seconds", "est_cost", "score", "reasons")


def _session_factory():
    from src.database.async_session import AsyncSessionLocal

    return AsyncSessionLocal


def _now() -> datetime:
    return datetime.now(timezone.utc)


def job_public(row: GpuJob) -> dict[str, Any]:
    return {c: getattr(row, c) for c in (
        "id", "project_id", "shot_id", "version", "task", "model", "backend", "worker_id", "worker_name", "gpu",
        "adapter", "precision", "attention", "offload", "warm", "where", "units", "status", "progress", "step",
        "est_seconds", "est_cost", "score", "reasons", "gpu_seconds", "wall_seconds", "cost_usd", "qa_score",
        "error")} | {k: (getattr(row, k).isoformat() if getattr(row, k) else None)
                     for k in ("created_at", "started_at", "finished_at")}


class GpuJobSink:
    """Stores and broadcasts the telemetry of one shot's runs."""

    def __init__(self, project_id: str | None, shot_id: str | None, version: int | None, session_factory=None) -> None:
        self.project_id, self.shot_id, self.version = project_id, shot_id, version
        self.session_factory = session_factory

    async def __call__(self, ev: dict[str, Any]) -> None:
        kind = ev.get("kind")
        if kind not in KIND_EVENT:
            return
        factory = self.session_factory or _session_factory()
        async with factory() as s:
            row = await s.get(GpuJob, ev["job_id"])
            if row is None:
                row = GpuJob(id=ev["job_id"], project_id=self.project_id, shot_id=self.shot_id, version=self.version,
                             task=ev.get("task") or "video", units=float(ev.get("units") or 1.0), status="queued",
                             progress=0.0, step="queued",
                             **{k: ev.get(k) for k in PLACEMENT_FIELDS if k not in ("offload", "warm", "where")},
                             offload=bool(ev.get("offload")), warm=bool(ev.get("warm")),
                             where=str(ev.get("where") or ev.get("backend") or "?")[:120], created_at=_now())
                s.add(row)
            if kind == "started":
                row.status, row.step, row.started_at = "running", "running", _now()
                row.remote_id = ev.get("remote_id") or row.remote_id
            elif kind == "progress":
                if row.status == "queued" and (ev.get("step") not in (None, "queued")):
                    row.status = "running"
                row.progress = float(ev.get("progress") or 0.0)
                row.step = (ev.get("step") or row.step or "")[:200]
            elif kind == "completed":
                row.status, row.step, row.progress, row.finished_at = "done", "done", 1.0, _now()
                row.gpu_seconds, row.wall_seconds = ev.get("gpu_seconds"), ev.get("wall_seconds")
                row.cost_usd = ev.get("cost_usd")
                if "warm" in ev:   # the worker's own answer beats the router's guess
                    row.warm = bool(ev["warm"])
            elif kind == "failed":
                row.status, row.step, row.finished_at = "error", "failed", _now()
                row.error, row.wall_seconds = ev.get("error"), ev.get("wall_seconds")
            await s.commit()
            payload = job_public(row)
        try:
            await get_event_bus().publish(make_event(event_type=KIND_EVENT[kind], project_id=self.project_id,
                                                     payload=payload))
        except Exception:  # noqa: BLE001 - Redis down: the row is stored, the page will still show it
            logger.debug("GPU job event not published", exc_info=True)


@contextlib.contextmanager
def shot_context(project: Any, shot_id: str | None, version: int | None, *, session_factory=None,
                 label: str | None = None) -> Iterator[None]:
    """Limits + telemetry + the GPU queue tag for one shot's generation."""
    from agentic_core.model_fabric import dispatch

    pol = policy.resolve(getattr(project, "generation_policy", None) if project is not None else None)
    sink = GpuJobSink(str(project.id) if project is not None else None, shot_id, version, session_factory)
    tag = label or (f"{(getattr(project, 'name', '') or '')[:40]}" if project is not None else None)
    with policy.use(pol), telemetry.with_sink(sink), dispatch.use_tag(tag):
        yield


async def load_performance(session_factory=None) -> dict[str, performance.Stats]:
    """Per (model, where): runs, successes, GPU seconds per unit (successful runs) and average QA."""
    factory = session_factory or _session_factory()
    done = GpuJob.status == "done"
    async with factory() as s:
        rows = (await s.execute(
            select(GpuJob.model, GpuJob.where, func.count(),
                   func.sum(case((done, 1), else_=0)),
                   func.avg(case((done, GpuJob.gpu_seconds / func.nullif(GpuJob.units, 0)), else_=None)),
                   func.avg(GpuJob.qa_score))
            .where(GpuJob.status.in_(("done", "error")))
            .group_by(GpuJob.model, GpuJob.where)
        )).all()
    return {performance.key(m, w): {"runs": int(n), "ok": int(ok or 0),
                                    "unit_seconds": float(us) if us is not None else None,
                                    "avg_qa": float(qa) if qa is not None else None}
            for m, w, n, ok, us, qa in rows}


def install_performance_loader(session_factory=None) -> None:
    performance.set_loader(lambda: load_performance(session_factory))


async def record_qa(session, shot_id: str, version: int, score: float) -> None:
    """Write the QA score onto the shot version's completed runs (in the caller's transaction)."""
    await session.execute(
        update(GpuJob)
        .where(GpuJob.shot_id == str(shot_id), GpuJob.version == int(version), GpuJob.status == "done")
        .values(qa_score=float(score))
    )


async def recent_jobs(session, *, project_id: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    q = select(GpuJob).order_by(GpuJob.created_at.desc()).limit(max(1, min(limit, 500)))
    if project_id:
        q = q.where(GpuJob.project_id == project_id)
    return [job_public(r) for r in (await session.execute(q)).scalars()]


async def totals(session) -> dict[str, Any]:
    row = (await session.execute(
        select(func.count(), func.sum(case((GpuJob.status == "done", 1), else_=0)),
               func.sum(case((GpuJob.status == "error", 1), else_=0)),
               func.coalesce(func.sum(GpuJob.gpu_seconds), 0.0), func.coalesce(func.sum(GpuJob.cost_usd), 0.0))
    )).one()
    return {"runs": int(row[0] or 0), "done": int(row[1] or 0), "failed": int(row[2] or 0),
            "gpu_seconds": round(float(row[3] or 0), 1), "cost_usd": round(float(row[4] or 0), 4)}


def warmup_requests(project: Any, seconds: float = 5.0) -> list[Any]:
    """What the project's shots will ask the GPUs for: its picture model and its video / avatar model."""
    from agentic_core.model_fabric.router import RouteRequest
    from agentic_core.models import catalog
    from agentic_core.models.video.factory import resolve_video_choice

    sizes = {"9:16": (720, 1280), "16:9": (1280, 720), "1:1": (1024, 1024)}
    w, h = sizes.get(getattr(project, "aspect_ratio", "9:16"), (720, 1280))
    out: list[Any] = []
    image = (getattr(project, "image_provider", None) or "").strip().lower()
    ids = {m["id"]: m for m in catalog.models()}
    if image == "best" or (image in ids and ids[image]["task"] == "image"):
        out.append(RouteRequest(task="image", width=w, height=h, models=None if image == "best" else [image]))
    video = resolve_video_choice(getattr(project, "video_provider", None)) or ""
    if video == "best":
        out.append(RouteRequest(task="video", seconds=seconds, width=w, height=h))
    elif video == "avatar":
        out.append(RouteRequest(task="avatar", seconds=seconds, width=w, height=h, has_audio=True))
    elif video in ids and ids[video]["task"] in ("video", "avatar"):
        out.append(RouteRequest(task=ids[video]["task"], seconds=seconds, width=w, height=h, models=[video],
                                has_audio=ids[video]["task"] == "avatar"))
    return out


async def prewarm_project(project: Any, seconds: float = 5.0) -> list[dict[str, Any]]:
    """Load the project's models on the GPUs while the physics stage runs (best effort, a few HTTP calls)."""
    from agentic_core.model_fabric import scheduler, workers

    if not workers.configured():
        return []
    try:
        return await asyncio.wait_for(scheduler.prewarm(warmup_requests(project, seconds),
                                                        tag=f"{(getattr(project, 'name', '') or '')[:40]} · warm-up"), 20)
    except Exception:  # noqa: BLE001 - only a speed-up
        logger.debug("warm-up skipped", exc_info=True)
        return []

# The router learns from gpu_jobs in every process that imports this (the API and the Temporal worker).
install_performance_loader()
