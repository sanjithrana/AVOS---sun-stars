"""AVOS GPU workers for the Animations tab: AI backdrops and the AI finish on your own GPUs.

The same workers as the Facts tab (Settings → GPU workers, apps/gpu_worker). The Facts tab's full Model Router lives
in agentic_core, which this service doesn't ship with; this module makes the same kind of choice for the one model
the studio already picked: which online worker, which backend on it and which precision, using the catalog's VRAM
table (the model's "fabric" block) and each worker's own report.

    pl = pick("wan-vace")                    # None when no worker can run it (the reason is in why_not())
    data = run(pl, prompt=..., width=..., height=..., inputs={"image": png, "video": mp4}, want="video")
"""
from __future__ import annotations

import base64
import os
import threading
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

from . import avos_settings

PRECISIONS = ("bf16", "fp8", "int8", "fp4", "int4")
RESERVE_GB = 1.5
STATUS_TTL = 5.0
_cache: dict[str, tuple[float, dict[str, Any]]] = {}
_busy: dict[str, int] = {}            # jobs this process is running on each worker right now (AI finish runs shots in parallel)
_busy_lock = threading.Lock()


@dataclass
class Placement:
    worker: dict[str, Any]
    adapter: str
    precision: str
    attention: str
    offload: bool = False
    vram_gb: float | None = None
    warm: bool = False
    reasons: list[str] = field(default_factory=list)

    @property
    def label(self) -> str:
        return f"{self.worker.get('name')} · {self.adapter} · {self.precision}"


def _headers() -> dict[str, str]:
    avos_settings.apply()
    tok = os.environ.get("GPU_WORKER_TOKEN")
    return {"Authorization": f"Bearer {tok}"} if tok else {}


def workers() -> list[dict[str, Any]]:
    return avos_settings.workers(enabled_only=True)


def status(w: dict[str, Any], force: bool = False) -> dict[str, Any]:
    """The worker's GET /status, or {"online": False, "error": ...}; cached for a few seconds."""
    hit = _cache.get(w["id"])
    if hit and not force and time.monotonic() - hit[0] < STATUS_TTL:
        return hit[1]
    try:
        r = httpx.get(f"{w['url']}/status", headers=_headers(), timeout=3.0)
        st = {**r.json(), "online": True} if r.status_code < 400 else \
            {"online": False, "error": "wrong GPU_WORKER_TOKEN" if r.status_code == 401 else f"HTTP {r.status_code}"}
    except (httpx.HTTPError, ValueError) as e:
        st = {"online": False, "error": f"can't reach {w['url']} ({type(e).__name__})"}
    _cache[w["id"]] = (time.monotonic(), st)
    return st


def _native(supports: dict[str, Any]) -> set[str]:
    out = {"int8", "int4", "bf16" if supports.get("bf16", True) else "fp16"}
    if supports.get("fp8"):
        out.add("fp8")
    if supports.get("fp4"):
        out.add("fp4")
    return out


def _need(fabric: dict[str, Any], precision: str) -> float | None:
    v = (fabric.get("vram_gb") or {}).get(precision)
    return float(v) if v else None


def placements(model_id: str, fabric: dict[str, Any] | None = None) -> tuple[list[Placement], list[str]]:
    """Every (worker, backend) that can run the model now, best first, and why the others can't."""
    fabric = fabric or {}
    out: list[Placement] = []
    why: list[str] = []
    for w in workers():
        st = status(w)
        if not st.get("online"):
            why.append(f"{w.get('name')}: {st.get('error')}")
            continue
        total = float((st.get("gpu") or {}).get("vram_gb") or 0) or 1e9
        native = _native(st.get("supports") or {})
        loaded = {(x.get("model"), x.get("adapter")): x for x in st.get("loaded_models") or []}
        queue = max(int(st.get("queue_depth") or 0) + (1 if st.get("running") else 0), _busy.get(w["id"], 0))
        for name, a in (st.get("adapters") or {}).items():
            if not a.get("ready") or model_id not in (a.get("models") or []):
                continue
            precs = [p for p in PRECISIONS if p in (a.get("precisions") or ["bf16"]) and p in native]
            if (st.get("gpu") or {}).get("device") == "cpu":    # CPU: the smallest weights page least from the SSD
                precs.sort(key=lambda p: _need(fabric, p) or 1e9)
            if not precs:
                why.append(f"{w.get('name')} ({name}): no precision it supports runs natively on this GPU")
                continue
            warm = loaded.get((model_id, name))
            chosen, offload = (warm.get("precision") if warm and warm.get("precision") in precs else None), False
            if chosen is None:
                chosen = next((p for p in precs if (_need(fabric, p) or 0) <= total - RESERVE_GB), None)
            if chosen is None:
                if float(fabric.get("min_vram_gb") or 1e9) <= total and a.get("offload", True):
                    chosen, offload = min(precs, key=lambda p: _need(fabric, p) or 1e9), True
                else:
                    why.append(f"{w.get('name')}: not enough " + ("memory (RAM + page file) " if (st.get("gpu") or {}).get("device") == "cpu"
                                                                   else "VRAM ") + f"({total:.0f} GB)")
                    continue
            cost = float(w["cost_per_hour"] if w.get("cost_per_hour") is not None else st.get("cost_per_hour") or 0)
            p = Placement(worker={**w, "cost_per_hour": cost}, adapter=name, precision=chosen,
                          attention=a.get("attention") or "sdpa", offload=offload, vram_gb=_need(fabric, chosen),
                          warm=bool(warm), reasons=[f"{(st.get('gpu') or {}).get('name') or 'GPU'}", chosen,
                                                    "already loaded" if warm else "loads first", f"{queue} queued"])
            p._rank = (0 if warm else 1, queue, offload, cost, PRECISIONS.index(chosen))  # type: ignore[attr-defined]
            out.append(p)
    out.sort(key=lambda p: p._rank)  # type: ignore[attr-defined]
    return out, why


def pick(model_id: str, fabric: dict[str, Any] | None = None) -> Placement | None:
    found, _ = placements(model_id, fabric)
    return found[0] if found else None


def why_not(model_id: str, fabric: dict[str, Any] | None = None) -> str:
    found, why = placements(model_id, fabric)
    if found:
        return ""
    if not workers():
        return "No GPU workers (Settings → GPU workers)."
    return "; ".join(why) or "No online GPU worker can run it: install its weights / workflow on a worker."


def run(pl: Placement, *, model_id: str, prompt: str, width: int, height: int, task: str = "video", want: str = "video",
        negative_prompt: str = "", seconds: float = 5.0, frames: int | None = None, fps: int | None = None,
        seed: int | None = None, steps: int | None = None, inputs: dict[str, bytes | None] | None = None,
        timeout: float = 1800.0, poll: float = 2.0, options: dict[str, Any] | None = None, priority: int = 5,
        tag: str | None = None) -> bytes:
    """Run one job on the worker and return the output bytes (blocking: the studio runs this in a thread)."""
    w = pl.worker
    body = {"model": model_id, "adapter": pl.adapter, "precision": pl.precision, "attention": pl.attention,
            "offload": pl.offload, "vram_gb": pl.vram_gb, "task": task, "want": want, "prompt": prompt,
            "negative_prompt": negative_prompt, "width": int(width), "height": int(height), "seconds": float(seconds),
            "frames": frames, "fps": fps, "seed": None if seed is None else int(seed) % 2_147_483_647, "steps": steps,
            "inputs": {k: base64.b64encode(v).decode() for k, v in (inputs or {}).items() if v}, "timeout": timeout,
            "options": options or {}, "priority": int(priority), "tag": tag}
    deadline = time.monotonic() + timeout
    with _busy_lock:
        _busy[w["id"]] = _busy.get(w["id"], 0) + 1
    try:
        return _run(w, body, model_id, deadline, timeout, poll)
    finally:
        with _busy_lock:
            _busy[w["id"]] = max(0, _busy.get(w["id"], 1) - 1)


def _run(w: dict[str, Any], body: dict[str, Any], model_id: str, deadline: float, timeout: float, poll: float) -> bytes:
    with httpx.Client(timeout=60.0, headers=_headers()) as c:
        r = c.post(f"{w['url']}/jobs", json=body)
        if r.status_code >= 400:
            raise RuntimeError(f"GPU worker {w.get('name')} refused the job ({r.status_code}): {r.text[:300]}")
        jid = r.json()["id"]
        try:
            while True:
                if time.monotonic() > deadline:
                    raise RuntimeError(f"The GPU job took longer than {timeout:.0f} s and was cancelled.")
                s = c.get(f"{w['url']}/jobs/{jid}").json()
                if s.get("status") == "done":
                    res = c.get(f"{w['url']}/jobs/{jid}/result")
                    if res.status_code >= 400:
                        raise RuntimeError(f"Could not download the result from {w.get('name')}: {res.text[:200]}")
                    _cache.pop(w["id"], None)
                    return res.content
                if s.get("status") in ("error", "cancelled"):
                    raise RuntimeError(f"{model_id} on {w.get('name')} failed: {s.get('error') or s.get('status')}")
                time.sleep(poll)
        finally:
            try:
                c.delete(f"{w['url']}/jobs/{jid}")
            except httpx.HTTPError:
                pass
