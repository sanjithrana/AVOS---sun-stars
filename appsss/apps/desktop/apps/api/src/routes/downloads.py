"""Model downloads (Models page → Download): a model's ComfyUI files from Hugging Face, into a folder you pick,
on this PC (where AVOS runs) or straight onto one of your GPU workers.

    GET    /downloads/models/{id}?where=           variants (fp8 / bf16 …) with sizes, extras, the recommended one,
                                                    and which are already complete in that place's models folder
    GET    /downloads/browse?where=&path=          folders, for the folder picker   ·   POST /downloads/mkdir
    POST   /downloads                               {model, variant, extras[], where: "local" | <worker id>, path}
    GET    /downloads                               every download (this PC + each worker) with progress
    DELETE /downloads/{where}/{id}                  cancel (or clear a finished one)

"local" downloads go to AVOS_MODELS_DIR (Docker: /models, mounted from AVOS_MODELS_HOST_DIR in apps/.env) unless
you pick another folder; DOWNLOAD_ROOTS limits where they may go.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import httpx
from fastapi import APIRouter, Request

from agentic_core import settings_store
from agentic_core.model_fabric import downloads, model_files, workers
from agentic_core.models import catalog
from src.errors import APIException

router = APIRouter(prefix="/api/v1/downloads", tags=["downloads"])


def local_dir() -> str:
    return os.getenv("AVOS_MODELS_DIR") or str(Path.home() / "AVOS-models")


def _bad(e: Exception | str, code: int = 400) -> APIException:
    return APIException(code="validation_error" if code == 400 else "not_found", message=str(e), status_code=code)


def _worker(wid: str) -> dict[str, Any]:
    w = next((w for w in settings_store.workers() if w["id"] == wid), None)
    if w is None:
        raise _bad(f"No GPU worker '{wid}'.", 404)
    return w


async def _call(w: dict[str, Any], method: str, path: str, **kw) -> Any:
    try:
        async with httpx.AsyncClient(timeout=15.0, headers=workers.headers()) as c:
            r = await c.request(method, f"{w['url']}{path}", **kw)
    except httpx.HTTPError as e:
        raise APIException(code="worker_unreachable", message=f"Can't reach {w.get('name')}: {e}", status_code=502) from e
    if r.status_code == 404 and path.startswith(("/downloads", "/browse", "/files")) and "No such" not in r.text:
        raise APIException(code="worker_outdated", status_code=502,
                           message=f"{w.get('name')} runs an older GPU worker without downloads: update apps/gpu_worker there.")
    if r.status_code >= 400:
        detail = r.json().get("detail") if r.headers.get("content-type", "").startswith("application/json") else r.text
        raise APIException(code="worker_error", message=f"{w.get('name')}: {detail}"[:400], status_code=400 if r.status_code < 500 else 502)
    return r.json()


async def _vram(where: str) -> float | None:
    if where == "local":
        sts = [s for s in await workers.statuses() if s.online]
        return max((float(s.gpu.get("vram_gb") or 0) for s in sts), default=0) or None
    st = await workers.fetch(_worker(where))
    return (float(st.gpu.get("vram_gb") or 0) or None) if st.online else None


@router.get("/models/{model_id}")
async def model_options(model_id: str, where: str = "local", path: str | None = None) -> dict[str, Any]:
    if not model_files.has(model_id):
        raise _bad(f"{model_id} has no download list (only the open models on the Models page).", 404)
    out = model_files.options(model_id, await _vram(where))
    try:
        out["name"] = catalog.get(model_id)["name"]
    except KeyError:
        out["name"] = model_id
    dest = path or (local_dir() if where == "local" else None)
    every = [{"folder": f["folder"], "name": f["name"], "size": f["size"]}
             for v in out["variants"] for f in v["files"]] + \
            [{"folder": f["folder"], "name": f["name"], "size": f["size"]} for f in out["shared"] + out["optional"]]
    try:
        if where == "local":
            present = downloads.check(dest, every)
        else:
            r = await _call(_worker(where), "POST", "/files/check", json={"dest": dest, "files": every})
            present, dest = r["present"], r["dest"]
    except APIException:
        present = [False] * len(every)
    have = {f"{f['folder']}/{f['name']}" for f, ok in zip(every, present) if ok}
    shared_ok = all(f["id"] in have for f in out["shared"])
    for v in out["variants"]:
        v["complete"] = shared_ok and all(f["id"] in have for f in v["files"])
        for f in v["files"]:
            f["present"] = f["id"] in have
    for f in out["shared"] + out["optional"]:
        f["present"] = f["id"] in have
    out.update(where=where, dest=dest)
    return out


@router.get("/browse")
async def browse(where: str = "local", path: str | None = None) -> dict[str, Any]:
    if where != "local":
        return await _call(_worker(where), "GET", "/browse", params={"path": path} if path else None)
    try:
        if not path:
            Path(local_dir()).mkdir(parents=True, exist_ok=True)
        return {**downloads.browse(path or local_dir()), "default": local_dir()}
    except (ValueError, OSError) as e:
        raise _bad(e) from e


@router.post("/mkdir")
async def mkdir(request: Request) -> dict[str, Any]:
    body = await request.json()
    where = body.get("where") or "local"
    if where != "local":
        return await _call(_worker(where), "POST", "/browse/mkdir", json={"path": body.get("path"), "name": body.get("name")})
    try:
        return {"path": downloads.mkdir(str(body.get("path") or ""), str(body.get("name") or ""))}
    except (ValueError, OSError) as e:
        raise _bad(e) from e


@router.post("")
async def start(request: Request) -> dict[str, Any]:
    body = await request.json()
    model_id, variant = str(body.get("model") or ""), body.get("variant")
    where = body.get("where") or "local"
    try:
        files = model_files.files(model_id, variant, body.get("extras") or [])
    except (KeyError, ValueError) as e:
        raise _bad(e) from e
    try:
        name = catalog.get(model_id)["name"]
    except KeyError:
        name = model_id
    label = f"{name} ({variant or 'default'})"
    if where != "local":
        job = await _call(_worker(where), "POST", "/downloads",
                          json={"files": files, "dest": body.get("path") or None, "label": label, "model": model_id,
                                "variant": variant})
        return {**job, "where": where}
    dest = body.get("path") or local_dir()
    try:
        Path(dest).mkdir(parents=True, exist_ok=True)
        if not downloads.allowed(dest):
            raise ValueError(f"Downloads can only go under {', '.join(downloads.roots())} (DOWNLOAD_ROOTS).")
        job = downloads.start(files=files, dest=dest, label=label, model=model_id, variant=variant)
    except (ValueError, OSError) as e:
        raise _bad(e) from e
    return {**job.public(), "where": "local"}


@router.get("")
async def list_all() -> list[dict[str, Any]]:
    out = [{**j, "where": "local", "where_name": "This PC"} for j in downloads.jobs()]
    for w in settings_store.workers(enabled_only=True):
        try:
            async with httpx.AsyncClient(timeout=4.0, headers=workers.headers()) as c:
                r = await c.get(f"{w['url']}/downloads")
            if r.status_code < 400:
                out += [{**j, "where": w["id"], "where_name": w.get("name") or w["id"]} for j in r.json()]
        except httpx.HTTPError:
            continue
    return sorted(out, key=lambda j: -(j.get("created_at") or 0))


@router.delete("/{where}/{job_id}")
async def cancel(where: str, job_id: str) -> dict[str, Any]:
    if where != "local":
        return await _call(_worker(where), "DELETE", f"/downloads/{job_id}")
    j = downloads.get(job_id)
    if j is None:
        raise _bad("No such download.", 404)
    if j.status in ("queued", "running"):
        downloads.cancel(job_id)
    else:
        downloads.forget(job_id)
    return {"ok": True}
