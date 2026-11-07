"""The GPU Scheduler, AVOS side: what this process has already sent to each GPU, priorities, and warm-up.

Shots now generate in parallel, so many jobs are routed within a few seconds, faster than a worker's reported
status changes. The scheduler keeps a ledger of in-flight jobs per worker:

- the router adds their estimated time to that worker's wait, so the next job goes to a free GPU instead of
  queueing behind the busy one;
- a model already on its way to a worker counts as warm there (no second load estimate), so shots that use the same
  model stick to the GPU that has it;
- every job carries a priority: 0 for a Studio edit someone is waiting for, 5 for normal production, 9 for
  background warm-ups. Workers run the most urgent first.

    with dispatch.use_priority(0):   ...   # inside: every generation is urgent
    with dispatch.reserve(placement) as t:   ...   # done by scheduler.run_on_worker
"""
from __future__ import annotations

import contextlib
import contextvars
import itertools
import time
from dataclasses import dataclass, field
from typing import Any, Iterator

URGENT, NORMAL, BACKGROUND = 0, 5, 9

_priority: contextvars.ContextVar[int] = contextvars.ContextVar("avos_gpu_priority", default=NORMAL)
_tag: contextvars.ContextVar[str | None] = contextvars.ContextVar("avos_gpu_tag", default=None)
_ids = itertools.count(1)


@dataclass
class Ticket:
    worker_id: str
    model: str
    adapter: str | None
    precision: str | None
    est_seconds: float
    priority: int
    tag: str | None = None
    id: int = field(default_factory=lambda: next(_ids))
    t0: float = field(default_factory=time.monotonic)
    expires: float | None = None          # warm-ups: dropped from the ledger after this (monotonic) time

    def remaining(self) -> float:
        left = self.est_seconds - (time.monotonic() - self.t0)
        return max(0.0 if self.expires else 5.0, left)

    def public(self) -> dict[str, Any]:
        return {"id": self.id, "worker_id": self.worker_id, "model": self.model, "adapter": self.adapter,
                "precision": self.precision, "priority": self.priority, "tag": self.tag,
                "seconds": round(time.monotonic() - self.t0, 1), "est_seconds": round(self.est_seconds, 1)}


_inflight: dict[str, list[Ticket]] = {}


def current_priority() -> int:
    return _priority.get()


def current_tag() -> str | None:
    return _tag.get()


@contextlib.contextmanager
def use_priority(priority: int) -> Iterator[None]:
    token = _priority.set(max(0, min(9, int(priority))))
    try:
        yield
    finally:
        _priority.reset(token)


@contextlib.contextmanager
def use_tag(tag: str | None) -> Iterator[None]:
    token = _tag.set(tag)
    try:
        yield
    finally:
        _tag.reset(token)


@contextlib.contextmanager
def reserve(placement: Any) -> Iterator[Ticket | None]:
    """Hold a place in the ledger while a job runs on a GPU worker (no-op for hosted backends)."""
    wid = getattr(placement, "worker_id", None)
    if not wid:
        yield None
        return
    t = Ticket(worker_id=wid, model=placement.model, adapter=getattr(placement, "adapter", None),
               precision=getattr(placement, "precision", None), est_seconds=float(placement.est_seconds or 60),
               priority=current_priority(), tag=current_tag())
    _inflight.setdefault(wid, []).append(t)
    try:
        yield t
    finally:
        lst = _inflight.get(wid) or []
        if t in lst:
            lst.remove(t)


def inflight(worker_id: str) -> list[Ticket]:
    now = time.monotonic()
    lst = _inflight.get(worker_id) or []
    lst[:] = [t for t in lst if t.expires is None or t.expires > now]
    return list(lst)


def note(worker_id: str, model: str, adapter: str | None, precision: str | None, seconds: float,
         tag: str | None = "warm-up", ttl: float | None = None) -> Ticket:
    """A job sent without waiting for it (a warm-up taking ~`seconds`): kept in the ledger for `ttl` seconds
    (default 3 × seconds), then dropped by itself."""
    t = Ticket(worker_id=worker_id, model=model, adapter=adapter, precision=precision, est_seconds=seconds,
               priority=NORMAL, tag=tag, expires=time.monotonic() + (ttl or seconds * 3))
    _inflight.setdefault(worker_id, []).append(t)
    return t


def pending_seconds(worker_id: str, *, before_priority: int | None = None) -> float:
    """Estimated seconds of work this process has queued on the worker (jobs that would run before a job of
    `before_priority`)."""
    return sum(t.remaining() for t in inflight(worker_id)
               if before_priority is None or t.priority <= before_priority)


def on_the_way(worker_id: str) -> dict[tuple[str, str | None], str | None]:
    """(model, adapter) → precision for models this process has jobs for on the worker (they'll be loaded)."""
    return {(t.model, t.adapter): t.precision for t in inflight(worker_id)}


def snapshot() -> dict[str, list[dict[str, Any]]]:
    return {wid: [t.public() for t in inflight(wid)] for wid in list(_inflight) if inflight(wid)}


def clear() -> None:
    _inflight.clear()
