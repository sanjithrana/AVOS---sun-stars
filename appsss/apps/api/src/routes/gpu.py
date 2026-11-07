"""GPU compute: your GPU workers, the Model Router's choices, generation limits and every run (the GPU page).

    GET    /gpu                         workers (live status), limits, totals, recent runs
    GET    /gpu/workers                 live status of every worker (?force=1 skips the few-second cache)
    POST   /gpu/workers                 add / update a worker {id?, name, url, cost_per_hour?, enabled?}
    DELETE /gpu/workers/{id}            remove a worker
    POST   /gpu/workers/{id}/test       reach it now, report what it can run
    POST   /gpu/workers/{id}/load       warm a model {model, adapter, precision?}
    POST   /gpu/workers/{id}/unload     free a model's VRAM {model, adapter}
    POST   /gpu/workers/{id}/workflows  send the ComfyUI workflows uploaded in Settings to the worker
    GET    /gpu/jobs                    runs (?project_id=, ?limit=)
    GET    /gpu/performance             what routing has learned per model and GPU
    PUT    /gpu/limits                  default generation limits (preference, max cost / time per shot, attempts…)
    POST   /gpu/route                   preview the router: ranked placements + why others were rejected
    PUT    /gpu/projects/{id}/limits    one project's limits (null = the defaults)
"""
from __future__ import annotations

from typing import Any

import httpx
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from agentic_core import settings_store
from agentic_core.model_fabric import performance, policy, requirements, router as fabric_router, workers
from agentic_core.models import catalog
from src.database.async_session import get_async_db
from src.errors import APIException
from src.services import fabric_service
from src.services.project_service import ProjectService

router = APIRouter(prefix="/api/v1/gpu", tags=["gpu"])


def _bad(e: Exception | str) -> APIException:
    return APIException(code="validation_error", message=str(e), status_code=400)


def _worker(wid: str) -> dict[str, Any]:
    w = next((w for w in settings_store.workers() if w["id"] == wid), None)
    if w is None:
        raise APIException(code="not_found", message=f"No GPU worker '{wid}'.", status_code=404)
    return w


async def _statuses(force: bool = False) -> list[dict[str, Any]]:
    live = {s.id: s for s in await workers.statuses(force=force)}
    out = []
    for w in settings_store.workers():
        st = live.get(w["id"])
        out.append({**(st.public() if st else {"id": w["id"], "name": w.get("name"), "url": w["url"], "online": False,
                                                 "error": "Turned off."}), "enabled": w.get("enabled", True),
                    "cost_per_hour_setting": w.get("cost_per_hour")})
    return out


@router.get("")
async def overview(db: AsyncSession = Depends(get_async_db)) -> dict[str, Any]:
    return {"workers": await _statuses(), "limits": settings_store.fabric(), "preferences": settings_store.PREFERENCES,
            "totals": await fabric_service.totals(db), "jobs": await fabric_service.recent_jobs(db, limit=30),
            "modelBackend": (settings_store.load()["gpu"].get("model_backend") or "auto"),
            "tokenSet": bool(workers.token())}


@router.get("/workers")
async def list_workers(force: bool = False) -> list[dict[str, Any]]:
    return await _statuses(force)


@router.post("/workers")
async def put_worker(request: Request) -> list[dict[str, Any]]:
    body = await request.json()
    if not isinstance(body, dict):
        raise _bad("Send {name, url, cost_per_hour}.")
    try:
        settings_store.upsert_worker(body)
    except ValueError as e:
        raise _bad(e) from e
    workers.forget()
    return await _statuses(force=True)


@router.delete("/workers/{wid}")
async def delete_worker(wid: str) -> list[dict[str, Any]]:
    _worker(wid)
    settings_store.delete_worker(wid)
    workers.forget(wid)
    return await _statuses()


@router.post("/workers/{wid}/test")
async def test_worker(wid: str) -> dict[str, Any]:
    st = await workers.fetch(_worker(wid), force=True, timeout=6.0)
    out = st.public()
    if st.online:
        runs = sorted({m for a in st.adapters.values() for m in (a.get("models") or [])})
        out["summary"] = (f"{st.gpu.get('name') or 'No GPU found'}"
                          + (f", {st.gpu.get('vram_gb')} GB" if st.gpu.get("vram_gb") else "")
                          + f" · backends: {', '.join(st.adapters) or 'none ready'}"
                          + f" · can run: {', '.join(runs) or 'nothing yet (install models / workflows)'}")
    return out


async def _proxy(wid: str, path: str, body: dict[str, Any]) -> dict[str, Any]:
    w = _worker(wid)
    try:
        async with httpx.AsyncClient(timeout=20.0, headers=workers.headers()) as client:
            r = await client.post(f"{w['url']}{path}", json=body)
    except httpx.HTTPError as e:
        raise APIException(code="worker_unreachable", message=f"Can't reach {w.get('name')}: {e}", status_code=502) from e
    if r.status_code >= 400:
        raise APIException(code="worker_error", message=f"{w.get('name')}: {r.text[:300]}", status_code=502)
    workers.forget(wid)
    return r.json()


@router.post("/workers/{wid}/load")
async def load_model(wid: str, request: Request) -> dict[str, Any]:
    body = await request.json()
    try:
        m = catalog.get(str(body.get("model") or ""))
    except KeyError as e:
        raise _bad("Unknown model.") from e
    fabric = requirements.fabric_of(m)
    precision = body.get("precision") or "bf16"
    return await _proxy(wid, "/models/load", {"model": m["id"], "adapter": body.get("adapter") or "comfyui",
                                              "precision": precision,
                                              "vram_gb": requirements.vram_need(fabric, precision)})


@router.post("/workers/{wid}/unload")
async def unload_model(wid: str, request: Request) -> dict[str, Any]:
    body = await request.json()
    return await _proxy(wid, "/models/unload", {"model": body.get("model"), "adapter": body.get("adapter")})


@router.post("/workers/{wid}/workflows")
async def push_workflows(wid: str) -> dict[str, Any]:
    """Copy every workflow in COMFYUI_WORKFLOW_DIR to the worker's ComfyUI backend (upload once, use everywhere)."""
    import json as _json

    w = _worker(wid)
    d = catalog.workflow_dir()
    files = sorted(d.glob("*.json")) if d.is_dir() else []
    sent, failed = [], []
    async with httpx.AsyncClient(timeout=20.0, headers=workers.headers()) as client:
        for f in files:
            try:
                body = _json.loads(f.read_text("utf-8"))
                r = await client.put(f"{w['url']}/workflows/{f.stem}", json=body)
                (sent if r.status_code < 400 else failed).append(f.stem if r.status_code < 400 else f"{f.stem}: {r.text[:120]}")
            except (ValueError, httpx.HTTPError) as e:
                failed.append(f"{f.stem}: {e}")
    workers.forget(wid)
    return {"sent": sent, "failed": failed, "dir": str(d)}


@router.get("/jobs")
async def jobs(project_id: str | None = None, limit: int = 50, db: AsyncSession = Depends(get_async_db)) -> list[dict[str, Any]]:
    return await fabric_service.recent_jobs(db, project_id=project_id, limit=limit)


@router.get("/performance")
async def learned() -> dict[str, Any]:
    snap = await performance.refresh(force=True)
    rows = []
    for k, v in sorted(snap.items()):
        model, where = k.split("|", 1)
        rows.append({"model": model, "where": where, **v, "used_for_routing": v.get("runs", 0) >= performance.MIN_RUNS})
    return {"min_runs": performance.MIN_RUNS, "rows": rows}


@router.put("/limits")
async def put_limits(request: Request) -> dict[str, Any]:
    body = await request.json()
    try:
        settings_store.set_fabric(body if isinstance(body, dict) else {})
    except ValueError as e:
        raise _bad(e) from e
    return settings_store.fabric()


@router.post("/route")
async def preview_route(request: Request) -> dict[str, Any]:
    """What the router would do for a shot like this, right now (no generation happens)."""
    body = await request.json() or {}
    task = body.get("task") or "video"
    if task not in ("image", "video", "avatar"):
        raise _bad("task must be image, video or avatar.")
    models = body.get("models") or ([body["model"]] if body.get("model") else None)
    req = fabric_router.RouteRequest(
        task=task, seconds=float(body.get("seconds") or 5), width=int(body.get("width") or (1024 if task == "image" else 1280)),
        height=int(body.get("height") or (1024 if task == "image" else 720)), prompt=str(body.get("prompt") or ""),
        has_audio=bool(body.get("has_audio")), continuity=bool(body.get("continuity")),
        speakers=int(body.get("speakers") or 1), models=models)
    try:
        limits = settings_store.clean_policy(body.get("limits") or {})
    except ValueError as e:
        raise _bad(e) from e
    pol = policy.resolve(limits)
    return (await fabric_router.plan(req, pol)).as_dict()


@router.put("/projects/{project_id}/limits")
async def put_project_limits(project_id: str, request: Request, db: AsyncSession = Depends(get_async_db)) -> dict[str, Any]:
    body = await request.json()
    project = await ProjectService(db).set_generation_policy(project_id, body if isinstance(body, dict) else None)
    await db.commit()
    return {"project_id": str(project.id), "generation_policy": project.generation_policy,
            "effective": policy.resolve(project.generation_policy).as_dict()}
