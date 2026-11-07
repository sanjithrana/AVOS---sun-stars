"""GPU workers: where they are (Settings → GPU workers) and what they report right now.

Each worker is an AVOS GPU worker (apps/gpu_worker) on a GPU machine: your own PC, a RunPod / Vast.ai / Lambda pod,
or a cloud VM. AVOS never cares where the GPU is; it only needs the worker's address. Every worker is asked for
GET /status (GPU, free VRAM, loaded models, queue, which models and precisions it can run) and the answers are
cached for a few seconds so routing many shots doesn't hammer them.

The token in GPU_WORKER_TOKEN (Settings → API keys) is sent as a bearer token; set the same value on the worker.
"""
from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

from agentic_core import settings_store

STATUS_TTL = 4.0
_cache: dict[str, tuple[float, "WorkerStatus"]] = {}


@dataclass
class WorkerStatus:
    id: str
    name: str
    url: str
    online: bool
    error: str | None = None
    report: dict[str, Any] = field(default_factory=dict)
    cost_per_hour: float = 0.0
    checked_at: float = 0.0

    # --- views over the worker's report ---
    @property
    def gpu(self) -> dict[str, Any]:
        return self.report.get("gpu") or {}

    @property
    def supports(self) -> dict[str, Any]:
        return self.report.get("supports") or {}

    @property
    def adapters(self) -> dict[str, Any]:
        return {k: v for k, v in (self.report.get("adapters") or {}).items() if (v or {}).get("ready")}

    @property
    def loaded(self) -> list[dict[str, Any]]:
        return list(self.report.get("loaded_models") or [])

    @property
    def queue_depth(self) -> int:
        return int(self.report.get("queue_depth") or 0) + (1 if self.report.get("running") else 0)

    def can_run(self, model_id: str) -> list[str]:
        """Ready adapters on this worker that can run the model, in the worker's preferred order."""
        return [a for a, info in self.adapters.items() if model_id in (info.get("models") or [])]

    def public(self) -> dict[str, Any]:
        report = {k: v for k, v in self.report.items() if k != "name"}
        return {**report, "worker_name": self.report.get("name"), "id": self.id, "name": self.name, "url": self.url,
                "online": self.online, "error": self.error, "cost_per_hour": self.cost_per_hour,
                "checked_at": self.checked_at}


def token() -> str | None:
    settings_store.apply()
    return os.getenv("GPU_WORKER_TOKEN") or None


def headers() -> dict[str, str]:
    t = token()
    return {"Authorization": f"Bearer {t}"} if t else {}


def configured() -> list[dict[str, Any]]:
    return settings_store.workers(enabled_only=True)


def _fresh(worker: dict[str, Any]) -> "WorkerStatus | None":
    hit = _cache.get(worker["id"])
    if hit and time.monotonic() - hit[0] < STATUS_TTL and hit[1].url == worker["url"]:
        return hit[1]
    return None


async def fetch(worker: dict[str, Any], *, timeout: float = 3.0, force: bool = False) -> WorkerStatus:
    if not force and (hit := _fresh(worker)):
        return hit
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.get(f"{worker['url']}/status", headers=headers())
    except httpx.HTTPError as exc:
        r = exc
    return _store(worker, r)


def fetch_blocking(worker: dict[str, Any], *, timeout: float = 2.0) -> WorkerStatus:
    """Synchronous status check, for synchronous callers that find no status cached yet."""
    if hit := _fresh(worker):
        return hit
    try:
        with httpx.Client(timeout=timeout) as client:
            r = client.get(f"{worker['url']}/status", headers=headers())
    except httpx.HTTPError as exc:
        r = exc
    return _store(worker, r)


def _store(worker: dict[str, Any], r: "httpx.Response | httpx.HTTPError") -> WorkerStatus:
    wid = worker["id"]
    st = WorkerStatus(id=wid, name=worker.get("name") or wid, url=worker["url"], online=False, checked_at=time.time())
    if isinstance(r, httpx.HTTPError):
        st.error = f"Can't reach the worker at {worker['url']} ({type(r).__name__}). Is it running and reachable from here?"
    elif r.status_code == 401:
        st.error = "The worker refused the token: set the same GPU_WORKER_TOKEN here (Settings → API keys) and on the worker."
    elif r.status_code >= 400:
        st.error = f"The worker answered {r.status_code}: {r.text[:200]}"
    else:
        try:
            st.report, st.online = r.json(), True
        except ValueError:
            st.error = "The worker's answer wasn't JSON: is this the AVOS GPU worker's address?"
    reported = st.report.get("cost_per_hour")
    st.cost_per_hour = float(worker["cost_per_hour"] if worker.get("cost_per_hour") is not None else (reported or 0.0))
    _cache[wid] = (time.monotonic(), st)
    return st


async def statuses(*, force: bool = False) -> list[WorkerStatus]:
    ws = configured()
    if not ws:
        return []
    return list(await asyncio.gather(*(fetch(w, force=force) for w in ws)))


def cached(*, refresh_missing: bool = False) -> list[WorkerStatus]:
    """Last known statuses of the configured workers (no network): for synchronous callers such as the catalog.
    With refresh_missing, a worker never checked (or checked too long ago) is asked now, briefly."""
    out = []
    for w in configured():
        hit = _cache.get(w["id"])
        if refresh_missing and (hit is None or time.monotonic() - hit[0] > 60):
            out.append(fetch_blocking(w))
        elif hit:
            out.append(hit[1])
    return out


def forget(worker_id: str | None = None) -> None:
    if worker_id:
        _cache.pop(worker_id, None)
    else:
        _cache.clear()
