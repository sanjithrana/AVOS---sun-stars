"""Settings shared by Facts and Animations: API keys, the GPU server, models you add, ComfyUI workflows.

Stored in one file (agentic_core/settings_store.py) that the API, the worker and the Animation Studio all read.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
from fastapi import APIRouter, Request
from pydantic import BaseModel

from agentic_core import settings_store
from agentic_core.models import catalog, comfy_autowire
from src.errors import APIException

router = APIRouter(prefix="/api/v1/settings", tags=["settings"])

PLACEHOLDERS = {
    "prompt": "the shot's description", "negative_prompt": "things to avoid", "width": "pixels", "height": "pixels",
    "aspect_ratio": "9:16 / 16:9 / 1:1", "seed": "a number", "duration": "seconds (decimal)", "duration_int": "seconds (whole)",
    "num_frames": "frames for the shot", "fps": "frames per second", "image_url": "the shot's picture (or the presenter)",
    "audio_url": "the shot's narration", "video_url": "a driving / source video",
}


def _bad(e: Exception) -> APIException:
    return APIException(code="validation_error", message=str(e), status_code=400)


def _view() -> dict[str, Any]:
    pub = settings_store.public()
    return {**pub, "tasks": settings_store.TASKS, "kinds": settings_store.KINDS, "placeholders": PLACEHOLDERS,
            "defaultInputs": {f"{k}:{t}": v for (k, t), v in settings_store.DEFAULT_INPUTS.items()},
            "workflowDir": str(catalog.workflow_dir()),
            "workflows": sorted(p.name for p in catalog.workflow_dir().glob("*.json")) if catalog.workflow_dir().is_dir() else []}


@router.get("")
def get_settings() -> dict[str, Any]:
    return _view()


@router.put("/keys")
async def put_keys(request: Request) -> dict[str, Any]:
    body = await request.json()
    if not isinstance(body, dict):
        raise _bad(ValueError("Send {\"NAME\": \"value\"}; an empty value removes it."))
    try:
        settings_store.set_env({str(k).strip().upper(): (None if v is None else str(v)) for k, v in body.items()})
    except ValueError as e:
        raise _bad(e) from e
    return _view()


class GpuBody(BaseModel):
    comfyui_url: str | None = None
    model_backend: str | None = None


@router.put("/gpu")
def put_gpu(body: GpuBody) -> dict[str, Any]:
    try:
        settings_store.set_gpu(body.comfyui_url, body.model_backend)
    except ValueError as e:
        raise _bad(e) from e
    return _view()


@router.post("/gpu/test")
async def test_gpu() -> dict[str, Any]:
    url = settings_store.apply()["gpu"].get("comfyui_url")
    import os
    url = url or os.getenv("COMFYUI_URL")
    if not url:
        return {"ok": False, "detail": "No GPU server address yet."}
    try:
        async with httpx.AsyncClient(timeout=8) as c:
            r = await c.get(f"{url.rstrip('/')}/system_stats")
        if r.status_code != 200:
            return {"ok": False, "detail": f"{url} answered {r.status_code}; is it ComfyUI?"}
        devices = (r.json().get("devices") or [])
        gpu = ", ".join(f"{d.get('name', 'GPU')} ({round((d.get('vram_total') or 0) / 2**30)} GB)" for d in devices) or "connected"
        return {"ok": True, "detail": f"ComfyUI is reachable: {gpu}"}
    except httpx.HTTPError as e:
        return {"ok": False, "detail": f"Can't reach {url} ({type(e).__name__}). Is the pod running and port 8188 open?"}


@router.post("/providers/{provider}/retry")
def retry_provider(provider: str) -> dict[str, Any]:
    """Try a provider that was skipped (no credit / refused key) again now, e.g. after topping up."""
    from agentic_core.models import provider_health

    provider_health.clear(provider)
    return {"ok": True, "providers": provider_health.snapshot()}


@router.post("/models")
async def add_model(request: Request) -> dict[str, Any]:
    try:
        settings_store.upsert_model(await request.json(), catalog.builtin_ids())
    except ValueError as e:
        raise _bad(e) from e
    return _view()


@router.delete("/models/{model_id}")
def remove_model(model_id: str) -> dict[str, Any]:
    if not settings_store.custom_model(model_id):
        raise APIException(code="not_found", message="No such model.", status_code=404)
    settings_store.delete_model(model_id)
    wf = catalog.workflow_dir() / f"{model_id}.json"
    if wf.is_file():
        wf.unlink()
    return _view()


@router.put("/models/{model_id}/workflow")
async def upload_workflow(model_id: str, request: Request) -> dict[str, Any]:
    """A ComfyUI workflow exported with Workflow → Export (API), for a catalog model or one you added."""
    try:
        m = catalog.get(model_id)
    except KeyError as e:
        raise APIException(code="not_found", message=str(e), status_code=404) from e
    if not m.get("comfyui"):
        raise _bad(ValueError(f"{m['name']} doesn't run on ComfyUI."))
    raw = await request.body()
    try:
        wf = json.loads(raw)
    except ValueError as e:
        raise _bad(ValueError(f"That file isn't JSON: {e}")) from e
    if not isinstance(wf, dict) or ("nodes" in wf and "links" in wf):
        raise _bad(ValueError("This is a regular ComfyUI save. In ComfyUI use Workflow → Export (API) and upload that file."))
    if not any(isinstance(n, dict) and "class_type" in n for n in wf.values()):
        raise _bad(ValueError("This doesn't look like a ComfyUI API workflow (no nodes with class_type)."))
    wired: dict[str, list[str]] = {}
    if comfy_autowire.needs_wiring(wf):           # a plain export: AVOS finds the prompt, image, seed, size, frames itself
        wf, wired = comfy_autowire.autowire(wf)
    text = json.dumps(wf)
    if "{{PROMPT}}" not in text and m["task"] != "avatar":
        raise _bad(ValueError("Couldn't find the prompt box in this workflow (no text-encode node feeding a sampler). Type {{PROMPT}} "
                              "into the positive prompt in ComfyUI, export again with Workflow → Export (API) and upload it."))
    d = catalog.workflow_dir()
    d.mkdir(parents=True, exist_ok=True)
    (d / m["comfyui"]["workflow"]).write_text(json.dumps(wf, indent=1), "utf-8")
    found = [p for p in ("{{PROMPT}}", "{{NEGATIVE_PROMPT}}", "{{IMAGE}}", "{{AUDIO}}", "{{VIDEO}}", "{{SEED}}", "{{FRAMES}}", "{{WIDTH}}",
                         "{{HEIGHT}}", "{{FPS}}", "{{WEIGHT_DTYPE}}") if p in text]
    pushed = await _push_to_workers(Path(m["comfyui"]["workflow"]).stem, wf)
    return {**_view(), "uploaded": {"model": model_id, "file": m["comfyui"]["workflow"], "placeholders": found,
                                    "autowired": comfy_autowire.describe(wired) if wired else None, "workers": pushed}}


async def _push_to_workers(name: str, wf: dict[str, Any]) -> list[str]:
    """Send the workflow to every GPU worker now, so it's usable there without the GPU page's 'push' button."""
    from agentic_core.model_fabric import workers

    out = []
    async with httpx.AsyncClient(timeout=10.0, headers=workers.headers()) as client:
        for w in settings_store.workers(enabled_only=True):
            try:
                r = await client.put(f"{w['url']}/workflows/{name}", json=wf)
                out.append(f"{w.get('name') or w['id']}: {'ok' if r.status_code < 400 else r.status_code}")
                workers.forget(w["id"])
            except httpx.HTTPError as e:
                out.append(f"{w.get('name') or w['id']}: unreachable ({type(e).__name__})")
    return out


@router.delete("/models/{model_id}/workflow")
def delete_workflow(model_id: str) -> dict[str, Any]:
    try:
        m = catalog.get(model_id)
    except KeyError as e:
        raise APIException(code="not_found", message=str(e), status_code=404) from e
    f = catalog.workflow_dir() / ((m.get("comfyui") or {}).get("workflow") or f"{model_id}.json")
    if f.is_file():
        f.unlink()
    return _view()


@router.post("/models/{model_id}/test")
async def test_model(model_id: str) -> dict[str, Any]:
    """Text models: one short request. Others: say whether they're ready to run."""
    c = settings_store.custom_model(model_id)
    try:
        backend = catalog.backend_for(model_id)
    except (catalog.ModelUnavailable, KeyError) as e:
        return {"ok": False, "detail": str(e)}
    if c and c["task"] == "llm":
        from agentic_core.models.llm.factory import get_llm_provider

        try:
            text = await get_llm_provider(model_id).complete("Reply with the single word: ready", max_tokens=10, temperature=0)
            return {"ok": True, "detail": f"Answered: {text.strip()[:60]}"}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "detail": f"{type(e).__name__}: {str(e)[:300]}"}
    return {"ok": True, "detail": f"Ready on {backend}. It runs when a project uses it."}
