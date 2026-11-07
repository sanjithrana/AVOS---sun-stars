"""Model performance memory: what real runs measured, so routing improves with use.

Every generation the fabric runs is recorded (the API stores them in the gpu_jobs table). From those rows the API
builds a snapshot per (model, where it ran): runs, successes, GPU seconds per unit of output (per video second, or
per image megapixel) and the average QA score of the results. The router uses the measured speed instead of the
catalog's estimate once a model has MIN_RUNS runs somewhere, and lowers the score of models that fail or score badly.
"""
from __future__ import annotations

import time
from typing import Any, Awaitable, Callable

MIN_RUNS = 3
TTL = 60.0

Stats = dict[str, Any]          # {"runs", "ok", "unit_seconds", "avg_qa"}
_snapshot: dict[str, Stats] = {}
_loaded_at = 0.0
_loader: Callable[[], Awaitable[dict[str, Stats]]] | None = None


def key(model: str, where: str) -> str:
    return f"{model}|{(where or '').upper()}"


def set_loader(fn: Callable[[], Awaitable[dict[str, Stats]]] | None) -> None:
    """The API registers a function that aggregates the gpu_jobs table."""
    global _loader, _loaded_at
    _loader, _loaded_at = fn, 0.0


def update(snapshot: dict[str, Stats]) -> None:
    global _snapshot, _loaded_at
    _snapshot, _loaded_at = dict(snapshot), time.monotonic()


async def refresh(force: bool = False) -> dict[str, Stats]:
    if _loader and (force or time.monotonic() - _loaded_at > TTL):
        try:
            update(await _loader())
        except Exception:  # noqa: BLE001 - routing still works on catalog estimates
            pass
    return _snapshot


def lookup(model: str, where: str) -> Stats | None:
    s = _snapshot.get(key(model, where))
    return s if s and s.get("runs", 0) >= MIN_RUNS else None


def snapshot() -> dict[str, Stats]:
    return dict(_snapshot)
