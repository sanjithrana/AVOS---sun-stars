"""The AVOS model catalog (catalog.json): which open model does which job, where it runs, and the routing rules.

    get("z-image")                       → the catalog entry
    backend_for("wan-2.2")               → "fal" | "comfyui" (or raises ModelUnavailable with how to enable it)
    route_image(prompt)                  → "qwen-image" when the picture must show text, else "z-image"
    route_video(has_audio, seconds)      → "ltx-2.3" for audio-driven / long clips, else "wan-2.2"
    route_avatar(seconds, speakers)      → "infinitetalk" for long or multi-speaker, else "longcat-avatar"
    status()                             → every model with its readiness, for the Models page

Backends: your GPU workers (apps/gpu_worker, Settings → GPU workers; the Model Router in agentic_core.model_fabric
picks worker, backend and precision), fal.ai (FAL_KEY) or your own GPU server running ComfyUI (COMFYUI_URL + an exported workflow in
COMFYUI_WORKFLOW_DIR/<model id>.json). FLUX schnell can also run on Cloudflare Workers AI (free tier). MODEL_BACKEND=fal|comfyui forces one; the default prefers your GPU
server when the model's workflow is there (free per call), else fal.ai.
"""
from __future__ import annotations

import functools
import json
import os
import re
from pathlib import Path
from typing import Any

from agentic_core import settings_store

CATALOG_PATH = Path(os.getenv("AVOS_MODEL_CATALOG") or Path(__file__).with_name("catalog.json"))


class ModelUnavailable(ValueError):
    """The model can't run with the current settings; the message says how to enable it."""


@functools.lru_cache(maxsize=1)
def _load() -> dict[str, Any]:
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


def catalog() -> dict[str, Any]:
    return _load()


def builtin_ids() -> set[str]:
    return {m["id"] for m in _load()["models"]}


def _custom_entry(c: dict[str, Any]) -> dict[str, Any]:
    """A model added on the Settings page, in the catalog's shape."""
    kind = c["kind"]
    where = {"fal": f"fal.ai · {c.get('endpoint')}", "replicate": f"Replicate · {c.get('endpoint')}",
             "comfyui": "your GPU server (ComfyUI workflow)", "openai": f"{c.get('base_url')} · {c.get('model')}"}[kind]
    entry: dict[str, Any] = {
        "id": c["id"], "name": c["name"], "maker": "Added by you", "task": c["task"], "rank": 90, "role": "custom", "custom": True,
        "kind": kind, "best_for": c.get("notes") or "Your own model", "why": where,
        "license": c.get("license") or "Check the model's licence", "commercial": "unknown", "license_url": "",
        "inputs": ["prompt"], "size": "", "used_in": [], "definition": c,
    }
    if kind == "fal":
        entry["fal"] = {"endpoint": c["endpoint"], "price": "see fal.ai"}
    elif kind == "comfyui":
        entry["comfyui"] = {"workflow": c.get("workflow") or f"{c['id']}.json", "template": "your uploaded workflow"}
    return entry


def models(task: str | None = None, *, include_custom: bool = True) -> list[dict[str, Any]]:
    out = [m for m in _load()["models"] if task is None or m["task"] == task]
    if include_custom:
        out += [_custom_entry(c) for c in settings_store.custom_models(task)]
    return out


def get(model_id: str) -> dict[str, Any]:
    for m in _load()["models"]:
        if m["id"] == model_id:
            return m
    c = settings_store.custom_model(model_id)
    if c:
        return _custom_entry(c)
    raise KeyError(f"Unknown model '{model_id}'. Known: {', '.join(m['id'] for m in models())}")


def is_custom(model_id: str, task: str | tuple[str, ...] | None = None) -> bool:
    c = settings_store.custom_model(model_id or "")
    if not c:
        return False
    return task is None or c["task"] == task or (isinstance(task, tuple) and c["task"] in task)


def ids(task: str | None = None) -> tuple[str, ...]:
    return tuple(m["id"] for m in models(task))


# ---------- where a model can run ----------
def workflow_dir() -> Path:
    return Path(os.getenv("COMFYUI_WORKFLOW_DIR") or "/app/comfyui_workflows")


def workflow_path(model_id: str) -> Path | None:
    m = get(model_id)
    wf = (m.get("comfyui") or {}).get("workflow")
    return workflow_dir() / wf if wf else None


def available_backends(model_id: str) -> dict[str, str | None]:
    """{backend: None if usable, else why not} for the backends this model supports."""
    settings_store.apply()
    m = get(model_id)
    out: dict[str, str | None] = {}
    if m.get("custom"):
        c = m["definition"]
        kind, key = c["kind"], c.get("key_env")
        if kind == "comfyui":
            wf = workflow_path(model_id)
            out["comfyui"] = ("Set your GPU server address (Settings → GPU server)." if not os.getenv("COMFYUI_URL")
                              else None if wf and wf.is_file() else "Upload its ComfyUI workflow (Settings → Models).")
        else:
            out[kind] = None if (not key or os.getenv(key)) else f"Add the {key} key (Settings → API keys)."
        return out
    from agentic_core.models import provider_health as PH
    if m.get("fal"):
        out["fal"] = (PH.down("fal") if os.getenv("FAL_KEY") else "Set FAL_KEY (fal.ai/dashboard/keys).")
    if m.get("comfyui"):
        wf = workflow_path(model_id)
        if not os.getenv("COMFYUI_URL"):
            out["comfyui"] = "Set your GPU server address (Settings → GPU server)."
        elif not (wf and wf.is_file()):
            out["comfyui"] = f"Upload its '{m['comfyui']['template']}' workflow (Settings → Models), exported from ComfyUI in API format."
        else:
            out["comfyui"] = None
    if m.get("cloudflare"):
        out["cloudflare"] = PH.down("cloudflare") if (os.getenv("CLOUDFLARE_ACCOUNT_ID") and os.getenv("CLOUDFLARE_API_TOKEN")) else \
            "Set CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_API_TOKEN."
    gpu = gpu_backend_status(model_id)
    if gpu is not False:
        out = {"gpu": gpu, **out}
    return out


def gpu_backend_status(model_id: str) -> str | None | bool:
    """None if an online GPU worker can run the model, the reason if workers exist but none can, False with no
    workers configured. Uses the workers' last reported status (no network here; the Model Router refreshes it)."""
    from agentic_core.model_fabric import workers

    if not workers.configured():
        return False
    known = workers.cached(refresh_missing=True)
    if any(st.online and st.can_run(model_id) for st in known):
        return None
    if not any(st.online for st in known):
        return "No GPU worker is online."
    return "No online GPU worker can run it: install its weights / workflow on a worker (see apps/gpu_worker/README.md)."


def _downloadable(model_id: str) -> bool:
    from agentic_core.model_fabric import model_files

    return model_files.has(model_id)


def backend_for(model_id: str) -> str:
    """The backend to use for this model now, or ModelUnavailable explaining how to enable one."""
    m = get(model_id)
    avail = available_backends(model_id)
    if m.get("custom"):
        if avail.get("gpu", False) is None:
            return "gpu"
        kind, why = next((k, w) for k, w in avail.items() if k != "gpu") if any(k != "gpu" for k in avail) else ("gpu", avail["gpu"])
        if why:
            raise ModelUnavailable(f"{m['name']}: {why}")
        return kind
    forced = (os.getenv("MODEL_BACKEND") or "").strip().lower()
    if forced in ("fal", "comfyui", "cloudflare", "gpu"):
        if forced not in avail:
            raise ModelUnavailable(f"{m['name']} can't run on {forced} (MODEL_BACKEND). It runs on: {', '.join(avail) or 'nothing hosted yet'}.")
        if avail[forced]:
            raise ModelUnavailable(f"{m['name']} on {forced}: {avail[forced]}")
        return forced
    for b in ("gpu", "comfyui", "cloudflare", "fal"):   # your GPU workers, your ComfyUI server, Cloudflare free tier, then fal.ai (paid)
        if b in avail and avail[b] is None:
            return b
    reasons = "; ".join(f"{b}: {why}" for b, why in avail.items() if why)
    raise ModelUnavailable(f"{m['name']} isn't set up yet. {reasons or 'It has no hosted API: run it on your own GPU server.'}")


# ---------- routing: the best model for this job ----------
TEXT_RX = re.compile(
    r"\b(text|title|headline|caption|label(?:s|ed)?|signboard|poster|banner|infographic|diagram|chart|graph|"
    r"slide|menu|logo text|typography|lettering|written|words?|quote|equation|formula|timeline|whiteboard notes)\b"
    r"|[\"“][^\"”]{2,40}[\"”]|文字|標題|标题|海報|海报|圖表|图表|圖解|图解|招牌|字",
    re.I,
)


NEGATED_TEXT_RX = re.compile(r"\b(?:no|without|free of|avoid)\s+(?:any\s+)?(?:text|words?|letters|lettering|captions?|labels?|titles?|logos?|watermarks?)\b", re.I)


def needs_text(prompt: str) -> bool:
    """True when the picture must show readable text ("no text" in a prompt doesn't count)."""
    return bool(TEXT_RX.search(NEGATED_TEXT_RX.sub(" ", prompt or "")))


def route_image(prompt: str, *, fast: bool = False) -> str:
    if fast:
        return "flux-schnell"
    return "qwen-image" if needs_text(prompt) else "z-image"


def route_video(*, has_audio: bool = False, seconds: float = 5.0, continuity: bool = False) -> str:
    if continuity:
        return "wan-vace"
    if has_audio or seconds > 10.5:
        return "ltx-2.3"
    return "wan-2.2"


def route_avatar(*, seconds: float = 5.0, speakers: int = 1) -> str:
    return "infinitetalk" if speakers > 1 or seconds > 20 else "longcat-avatar"


def first_ready(candidates: list[str]) -> str | None:
    for c in candidates:
        try:
            backend_for(c)
            return c
        except ModelUnavailable:
            continue
    return None


# ---------- the Models page ----------
def _providers() -> dict[str, str]:
    from agentic_core.models import provider_health
    return provider_health.snapshot()


def local_models_dir() -> str:
    """Where Models page → Download → This PC saves (Docker: /models = apps/models on your PC)."""
    return os.getenv("AVOS_MODELS_DIR") or str(Path.home() / "AVOS-models")


def _downloaded(model_id: str) -> dict[str, Any] | None:
    """Which versions of the model are complete on this PC (and whether one is still a partial .part download)."""
    if not _downloadable(model_id):
        return None
    try:
        from agentic_core.model_fabric import model_files
        dest = local_models_dir()
        done = [v for v, ok in model_files.present(dest, model_id).items() if ok]
        e = model_files._entry(model_id)
        every = [f for fs in e["variants"].values() for f in fs] + list(e.get("shared") or []) + list(e.get("optional") or [])
        partial = any((Path(dest) / f["folder"] / (Path(f["path"]).name + ".part")).is_file() for f in every)
    except Exception:  # noqa: BLE001 - no manifest entry / unreadable folder
        return None
    return {"variants": done, "partial": partial, "dir": dest} if done or partial else None


def status() -> dict[str, Any]:
    settings_store.apply()
    cat = _load()
    rows = []
    for m in models():
        avail = available_backends(m["id"])
        try:
            current = backend_for(m["id"])
            ready, why = True, None
        except ModelUnavailable as e:
            current, ready, why = None, False, str(e)
        rows.append({**{k: v for k, v in m.items() if k != "definition"}, "backends": avail, "backend": current, "ready": ready, "missing": why,
                     "download": _downloadable(m["id"]), "downloaded": _downloaded(m["id"]),
                     "workflow": str(workflow_path(m["id"])) if m.get("comfyui") else None})
    from agentic_core.model_fabric import workers

    return {"tasks": cat["tasks"], "backends": cat["backends"], "models": rows,
            "settings": {"fal": bool(os.getenv("FAL_KEY")), "comfyui": os.getenv("COMFYUI_URL") or None,
                         "workflowDir": str(workflow_dir()), "modelBackend": os.getenv("MODEL_BACKEND") or "auto",
                         "gpuWorkers": len(workers.configured()),
                         "gpuWorkersOnline": sum(1 for st in workers.cached() if st.online),
                         "modelsDir": local_models_dir(), "providers": _providers()}}
