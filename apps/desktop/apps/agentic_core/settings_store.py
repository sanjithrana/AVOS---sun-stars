"""AVOS settings shared by Facts and Animations: API keys, the GPU server, and models you add yourself.

One JSON file (AVOS_SETTINGS_FILE; Docker: /data/settings/avos.json on the shared `avos_settings` volume) is written by
the Settings page and read by the API, the worker and the Animation Studio. A value saved here wins over the same name
in apps/.env; clearing it falls back to .env again.

    {"env": {"FAL_KEY": "...", "OPENAI_API_KEY": "...", "MY_DEEPSEEK_KEY": "..."},
     "gpu": {"comfyui_url": "http://1.2.3.4:8188", "model_backend": "auto"},
     "models": [{"id": "my-flux-pro", "name": "FLUX Pro", "task": "image", "kind": "fal", "endpoint": "fal-ai/flux-pro", ...}],
     "workers": [{"id": "gpu-4090", "name": "RTX 4090 at home", "url": "http://1.2.3.4:8700", "cost_per_hour": 0, "enabled": true}],
     "fabric": {"preference": "balanced", "max_cost_per_shot": null, "max_seconds_per_shot": null, "max_attempts": 3,
                "quality_threshold": 0.6, "allow_hosted": true}}

Standard library only: the Animation Studio carries an identical copy (animation_studio/studio/avos_settings.py).
"""
from __future__ import annotations

import json
import os
import re
import threading
from pathlib import Path
from typing import Any

# Keys the Settings page lists by name (any other NAME=value can be added too). "uses": which tab reads it.
KNOWN_KEYS: list[dict[str, str]] = [
    {"name": "OPENAI_API_KEY", "label": "OpenAI", "group": "Text AI", "uses": "Facts, Animations", "url": "https://platform.openai.com/api-keys"},
    {"name": "GROQ_API_KEY", "label": "Groq (free tier)", "group": "Text AI", "uses": "Facts, Animations", "url": "https://console.groq.com/keys"},
    {"name": "GEMINI_API_KEY", "label": "Google Gemini (free tier)", "group": "Text AI", "uses": "Animations", "url": "https://aistudio.google.com/apikey"},
    {"name": "OPENROUTER_API_KEY", "label": "OpenRouter", "group": "Text AI", "uses": "Animations", "url": "https://openrouter.ai/keys"},
    {"name": "ANTHROPIC_API_KEY", "label": "Anthropic", "group": "Text AI", "uses": "Animations", "url": "https://console.anthropic.com/"},
    {"name": "FAL_KEY", "label": "fal.ai (open image/video models)", "group": "Images & video", "uses": "Facts, Animations", "url": "https://fal.ai/dashboard/keys"},
    {"name": "REPLICATE_API_TOKEN", "label": "Replicate", "group": "Images & video", "uses": "Facts", "url": "https://replicate.com/account/api-tokens"},
    {"name": "STABILITY_API_KEY", "label": "Stability AI", "group": "Images & video", "uses": "Facts", "url": "https://platform.stability.ai/account/keys"},
    {"name": "CLOUDFLARE_ACCOUNT_ID", "label": "Cloudflare account ID (free images)", "group": "Images & video", "uses": "Facts, Animations", "url": "https://dash.cloudflare.com/"},
    {"name": "CLOUDFLARE_API_TOKEN", "label": "Cloudflare API token (Workers AI)", "group": "Images & video", "uses": "Facts, Animations", "url": "https://dash.cloudflare.com/profile/api-tokens"},
    {"name": "POLLINATIONS_TOKEN", "label": "Pollinations token (optional)", "group": "Images & video", "uses": "Facts", "url": "https://auth.pollinations.ai/"},
    {"name": "OLLAMA_BASE_URL", "label": "Ollama address (local text AI)", "group": "Local", "uses": "Facts, Animations", "url": "https://ollama.com"},
    {"name": "OLLAMA_MODEL", "label": "Ollama model for Facts", "group": "Local", "uses": "Facts", "url": ""},
    {"name": "LLAMACPP_URL", "label": "llama.cpp server address (local GGUF text model)", "group": "Local", "uses": "Facts, Animations", "url": "https://github.com/ggml-org/llama.cpp"},
    {"name": "IMAGE_SERVICE_URL", "label": "Your own image server (Automatic1111)", "group": "Local", "uses": "Facts, Animations", "url": ""},
    {"name": "HF_TOKEN", "label": "Hugging Face token (only for gated model downloads)", "group": "GPU", "uses": "Model downloads", "url": "https://huggingface.co/settings/tokens"},
    {"name": "GPU_WORKER_TOKEN", "label": "GPU worker token (shared secret)", "group": "GPU", "uses": "Facts, Animations", "url": ""},
]
PREFERENCES = ("quality", "balanced", "speed", "cost")
FABRIC_DEFAULTS: dict[str, Any] = {"preference": "balanced", "max_cost_per_shot": None, "max_seconds_per_shot": None,
                                   "max_attempts": 3, "quality_threshold": 0.6, "allow_hosted": True,
                                   "auto_qa": True, "review_shots": False}
TASKS = ("image", "video", "avatar", "llm")
KINDS = ("fal", "replicate", "comfyui", "openai")
NAME_RX = re.compile(r"^[A-Z][A-Z0-9_]{1,63}$")
ID_RX = re.compile(r"^[a-z0-9][a-z0-9._-]{1,38}$")
SECRET_RX = re.compile(r"KEY|TOKEN|SECRET|PASSWORD", re.I)

_lock = threading.Lock()
_cache: dict[str, Any] = {"mtime": None, "data": None, "path": None}
_ORIG: dict[str, str | None] = {}     # .env values replaced by settings, restored when the setting is cleared
_SET: dict[str, str] = {}              # what this process put into os.environ from the settings file


def path() -> Path:
    env = os.environ.get("AVOS_SETTINGS_FILE")
    if env:
        return Path(env)
    if Path("/data/settings").is_dir():            # Docker: the shared avos_settings volume
        return Path("/data/settings/avos.json")
    here = Path(__file__).resolve()
    apps = next((p for p in here.parents if (p / "docker-compose.yml").is_file()), here.parents[1])
    return apps / ".avos" / "settings.json"      # without Docker: apps/.avos/settings.json


def _empty() -> dict[str, Any]:
    return {"env": {}, "gpu": {"comfyui_url": "", "model_backend": "auto"}, "models": [], "workers": [],
            "fabric": dict(FABRIC_DEFAULTS)}


def load() -> dict[str, Any]:
    p = path()
    try:
        mtime = p.stat().st_mtime
    except OSError:
        return _empty()
    if _cache["path"] == str(p) and _cache["mtime"] == mtime and _cache["data"] is not None:
        return _cache["data"]
    try:
        data = json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return _empty()
    out = _empty()
    out["env"] = {str(k): str(v) for k, v in (data.get("env") or {}).items() if NAME_RX.match(str(k))}
    out["gpu"].update({k: v for k, v in (data.get("gpu") or {}).items() if k in ("comfyui_url", "model_backend")})
    out["models"] = [m for m in data.get("models") or [] if isinstance(m, dict) and ID_RX.match(str(m.get("id", "")))]
    out["workers"] = [w for w in data.get("workers") or [] if isinstance(w, dict) and ID_RX.match(str(w.get("id", "")))]
    out["fabric"].update({k: v for k, v in (data.get("fabric") or {}).items() if k in FABRIC_DEFAULTS})
    _cache.update(path=str(p), mtime=mtime, data=out)
    return out


def save(data: dict[str, Any]) -> dict[str, Any]:
    p = path()
    with _lock:
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=1, ensure_ascii=False), "utf-8")
        try:
            os.chmod(tmp, 0o600)
        except OSError:
            pass
        os.replace(tmp, p)
        _cache.update(mtime=None, data=None)
    apply()
    return load()


def _set(name: str, value: str | None) -> None:
    current = os.environ.get(name)
    if value:
        if name not in _SET or current != _SET[name]:     # first override, or the env changed since: remember it
            _ORIG[name] = current
        os.environ[name] = value
        _SET[name] = value
    elif name in _SET:
        if current == _SET[name]:                         # still ours: put the .env value back
            if _ORIG.get(name):
                os.environ[name] = _ORIG[name]  # type: ignore[assignment]
            else:
                os.environ.pop(name, None)
        _SET.pop(name, None)
        _ORIG.pop(name, None)


def apply() -> dict[str, Any]:
    """Put saved values into os.environ (cheap when nothing changed). Call before reading provider settings."""
    data = load()
    wanted = dict(data["env"])
    gpu = data["gpu"]
    if gpu.get("comfyui_url"):
        wanted["COMFYUI_URL"] = gpu["comfyui_url"]
    mb = (gpu.get("model_backend") or "auto").lower()
    if mb in ("gpu", "fal", "comfyui"):
        wanted["MODEL_BACKEND"] = mb
    for name in set(wanted) | set(_SET):
        _set(name, wanted.get(name) or None)
    return data


# ---------- views and edits for the Settings page ----------
def mask(value: str) -> str:
    return "•" * 6 + value[-4:] if len(value) > 8 else "•" * len(value)


def public() -> dict[str, Any]:
    """What the Settings page shows: secrets masked, where each value comes from."""
    data = apply()
    names = [k["name"] for k in KNOWN_KEYS] + [n for n in data["env"] if n not in {k["name"] for k in KNOWN_KEYS}]
    rows = []
    for n in names:
        saved = data["env"].get(n)
        from_env = _ORIG.get(n) if n in _SET else os.environ.get(n)
        value = saved or from_env or ""
        meta = next((k for k in KNOWN_KEYS if k["name"] == n), {"name": n, "label": n, "group": "Custom", "uses": "Your models", "url": ""})
        secret = bool(SECRET_RX.search(n))
        rows.append({**meta, "set": bool(value), "source": "settings" if saved else (".env" if from_env else None),
                     "value": (mask(value) if secret else value) if value else "", "secret": secret})
    return {"file": str(path()), "keys": rows, "gpu": data["gpu"], "models": data["models"], "workers": data["workers"],
            "fabric": data["fabric"]}


def set_env(updates: dict[str, str | None]) -> dict[str, Any]:
    data = load()
    env = dict(data["env"])
    for name, value in updates.items():
        if not NAME_RX.match(name):
            raise ValueError(f"'{name}' isn't a valid name: use CAPITALS, digits and _ (for example MY_API_KEY).")
        if value is None or str(value).strip() == "":
            env.pop(name, None)
        else:
            env[name] = str(value).strip()
    return save({**data, "env": env})


def set_gpu(comfyui_url: str | None = None, model_backend: str | None = None) -> dict[str, Any]:
    data = load()
    gpu = dict(data["gpu"])
    if comfyui_url is not None:
        url = comfyui_url.strip().rstrip("/")
        if url and not re.match(r"^https?://[^\s/]+", url):
            raise ValueError("The GPU server address must look like http://203.0.113.5:8188")
        gpu["comfyui_url"] = url
    if model_backend is not None:
        if model_backend not in ("auto", "gpu", "fal", "comfyui"):
            raise ValueError("Backend must be auto, gpu (your GPU workers), fal or comfyui.")
        gpu["model_backend"] = model_backend
    return save({**data, "gpu": gpu})


# ---------- GPU workers and the Model Fabric's defaults ----------
def workers(enabled_only: bool = False) -> list[dict[str, Any]]:
    return [w for w in load()["workers"] if not enabled_only or w.get("enabled", True)]


def clean_worker(w: dict[str, Any]) -> dict[str, Any]:
    url = str(w.get("url") or "").strip().rstrip("/")
    if not re.match(r"^https?://[^\s/]+", url):
        raise ValueError("The worker address must look like http://203.0.113.5:8700 (or your RunPod proxy URL).")
    wid = str(w.get("id") or "").strip().lower() or re.sub(r"[^a-z0-9]+", "-", re.sub(r"^https?://", "", url).lower()).strip("-")[:38]
    if not ID_RX.match(wid):
        raise ValueError("Worker id: 2-39 characters, lower-case letters, digits, '.', '-' or '_'.")
    out: dict[str, Any] = {"id": wid, "name": str(w.get("name") or wid).strip()[:60], "url": url,
                           "enabled": bool(w.get("enabled", True))}
    cph = w.get("cost_per_hour")
    if cph not in (None, ""):
        try:
            cph = float(cph)
        except (TypeError, ValueError) as e:
            raise ValueError("Cost per hour must be a number (0 for your own GPU).") from e
        if cph < 0 or cph > 100:
            raise ValueError("Cost per hour must be between 0 and 100 (USD).")
        out["cost_per_hour"] = cph
    return out


def upsert_worker(w: dict[str, Any]) -> dict[str, Any]:
    clean = clean_worker(w)
    data = load()
    rest = [x for x in data["workers"] if x.get("id") != clean["id"]]
    return save({**data, "workers": rest + [clean]})


def delete_worker(wid: str) -> dict[str, Any]:
    data = load()
    return save({**data, "workers": [x for x in data["workers"] if x.get("id") != wid]})


def fabric() -> dict[str, Any]:
    return dict(load()["fabric"])


def clean_policy(p: dict[str, Any], *, partial: bool = True) -> dict[str, Any]:
    """Generation limits (Settings defaults or one project's): preference, max cost / seconds per shot, attempts, QA bar."""
    out: dict[str, Any] = {}
    for k, v in (p or {}).items():
        if k not in FABRIC_DEFAULTS and k not in ("preferred_model", "fallback_model"):
            raise ValueError(f"Unknown setting '{k}'.")
        if k == "preference":
            if v not in PREFERENCES:
                raise ValueError(f"Preference must be one of {', '.join(PREFERENCES)}.")
            out[k] = v
        elif k in ("max_cost_per_shot", "max_seconds_per_shot"):
            if v in (None, ""):
                out[k] = None
                continue
            try:
                v = float(v)
            except (TypeError, ValueError) as e:
                raise ValueError(f"{k} must be a number.") from e
            if v <= 0:
                raise ValueError(f"{k} must be above 0 (leave it empty for no limit).")
            out[k] = v
        elif k == "max_attempts":
            try:
                v = int(v)
            except (TypeError, ValueError) as e:
                raise ValueError("max_attempts must be a whole number.") from e
            if not 1 <= v <= 10:
                raise ValueError("max_attempts must be between 1 and 10.")
            out[k] = v
        elif k == "quality_threshold":
            try:
                v = float(v)
            except (TypeError, ValueError) as e:
                raise ValueError("quality_threshold must be a number between 0 and 1.") from e
            if not 0 <= v <= 1:
                raise ValueError("quality_threshold must be between 0 and 1.")
            out[k] = v
        elif k in ("allow_hosted", "auto_qa", "review_shots"):
            out[k] = bool(v)
        else:   # preferred_model / fallback_model
            out[k] = (str(v).strip() or None) if v else None
    if not partial:
        out = {**FABRIC_DEFAULTS, **out}
    return out


def set_fabric(p: dict[str, Any]) -> dict[str, Any]:
    data = load()
    clean = {k: v for k, v in clean_policy(p).items() if k in FABRIC_DEFAULTS}
    return save({**data, "fabric": {**data["fabric"], **clean}})


DEFAULT_INPUTS: dict[tuple[str, str], dict[str, Any]] = {
    ("fal", "image"): {"prompt": "{{prompt}}", "image_size": {"width": "{{width}}", "height": "{{height}}"}, "seed": "{{seed}}"},
    ("fal", "video"): {"prompt": "{{prompt}}", "image_url": "{{image_url}}"},
    ("fal", "avatar"): {"prompt": "{{prompt}}", "image_url": "{{image_url}}", "audio_url": "{{audio_url}}"},
    ("replicate", "image"): {"prompt": "{{prompt}}", "aspect_ratio": "{{aspect_ratio}}", "seed": "{{seed}}"},
    ("replicate", "video"): {"prompt": "{{prompt}}", "image": "{{image_url}}"},
    ("replicate", "avatar"): {"image": "{{image_url}}", "audio": "{{audio_url}}"},
}


def clean_model(m: dict[str, Any], builtin_ids: set[str] | frozenset[str] = frozenset()) -> dict[str, Any]:
    """Validate one model definition from the Settings page."""
    mid = str(m.get("id") or "").strip().lower()
    if not ID_RX.match(mid):
        raise ValueError("Model id: 2-39 characters, lower-case letters, digits, '.', '-' or '_' (for example my-flux-pro).")
    if mid in builtin_ids or mid in ("best", "avatar", "free", "chain", "mock", "motion", "blender", "fal", "replicate",
                                     "comfyui", "local", "pollinations", "cloudflare", "stability", "openai", "ollama", "groq"):
        raise ValueError(f"'{mid}' is already used by a built-in option; pick another id.")
    task, kind = m.get("task"), m.get("kind")
    if task not in TASKS:
        raise ValueError(f"Task must be one of {', '.join(TASKS)}.")
    if kind not in KINDS:
        raise ValueError(f"Kind must be one of {', '.join(KINDS)}.")
    if (task == "llm") != (kind == "openai"):
        raise ValueError("Text models (task llm) use kind openai (any OpenAI-compatible API); image/video models use fal, replicate or comfyui.")
    out: dict[str, Any] = {"id": mid, "name": str(m.get("name") or mid).strip()[:60], "task": task, "kind": kind,
                           "license": str(m.get("license") or "").strip()[:60], "notes": str(m.get("notes") or "").strip()[:300]}
    key_env = str(m.get("key_env") or "").strip().upper()
    if key_env and not NAME_RX.match(key_env):
        raise ValueError("API key name must be CAPITALS, digits and _ (for example DEEPSEEK_API_KEY).")
    if kind == "fal":
        ep = str(m.get("endpoint") or "").strip().strip("/")
        if not re.match(r"^[\w.-]+/[\w./-]+$", ep):
            raise ValueError("fal.ai endpoint looks like fal-ai/flux-pro/v1.1 (copy it from the model's page on fal.ai).")
        out.update(endpoint=ep, key_env=key_env or "FAL_KEY")
    elif kind == "replicate":
        ref = str(m.get("endpoint") or "").strip()
        if not re.match(r"^[\w.-]+/[\w.-]+(:[0-9a-f]{16,})?$", ref):
            raise ValueError("Replicate model looks like owner/name or owner/name:version.")
        out.update(endpoint=ref, key_env=key_env or "REPLICATE_API_TOKEN")
    elif kind == "comfyui":
        out.update(workflow=f"{mid}.json")
    else:
        base = str(m.get("base_url") or "").strip().rstrip("/")
        if not re.match(r"^https?://\S+$", base):
            raise ValueError("Base URL looks like https://api.deepseek.com/v1 or http://localhost:1234/v1 (LM Studio).")
        model = str(m.get("model") or "").strip()
        if not model:
            raise ValueError("Model name is required (for example deepseek-chat).")
        out.update(base_url=base, model=model, key_env=key_env)
    if kind in ("fal", "replicate"):
        inputs = m.get("inputs")
        if isinstance(inputs, str) and inputs.strip():
            try:
                inputs = json.loads(inputs)
            except ValueError as e:
                raise ValueError(f"Inputs must be JSON: {e}") from e
        if inputs and not isinstance(inputs, dict):
            raise ValueError("Inputs must be a JSON object.")
        out["inputs"] = inputs or DEFAULT_INPUTS[(kind, task)]
        out["output"] = str(m.get("output") or "").strip()
    return out


def upsert_model(m: dict[str, Any], builtin_ids: set[str] | frozenset[str] = frozenset()) -> dict[str, Any]:
    clean = clean_model(m, builtin_ids)
    data = load()
    models = [x for x in data["models"] if x.get("id") != clean["id"]] + [clean]
    return save({**data, "models": models})


def delete_model(mid: str) -> dict[str, Any]:
    data = load()
    return save({**data, "models": [x for x in data["models"] if x.get("id") != mid]})


def custom_models(task: str | None = None) -> list[dict[str, Any]]:
    return [m for m in load()["models"] if task is None or m.get("task") == task]


def custom_model(mid: str) -> dict[str, Any] | None:
    return next((m for m in load()["models"] if m.get("id") == mid), None)


# ---------- input templates ----------
PLACEHOLDER = re.compile(r"\{\{\s*(\w+)\s*\}\}")


def fill(node: Any, values: dict[str, Any]) -> Any:
    """{{name}} placeholders in a JSON template. A field that is exactly one placeholder takes the value's type;
    a field whose placeholder has no value (e.g. {{audio_url}} with no audio) is dropped."""
    if isinstance(node, dict):
        out = {}
        for k, v in node.items():
            f = fill(v, values)
            if f is not _DROP:
                out[k] = f
        return out
    if isinstance(node, list):
        return [x for x in (fill(v, values) for v in node) if x is not _DROP]
    if isinstance(node, str):
        whole = PLACEHOLDER.fullmatch(node.strip())
        if whole:
            v = values.get(whole.group(1))
            return _DROP if v is None else v
        return PLACEHOLDER.sub(lambda mt: "" if values.get(mt.group(1)) is None else str(values[mt.group(1)]), node)
    return node


class _Drop:
    pass


_DROP = _Drop()


def uses(template: Any, name: str) -> bool:
    return f"{{{{{name}}}}}" in re.sub(r"\{\{\s*(\w+)\s*\}\}", r"{{\1}}", json.dumps(template or {}))
