"""The open AI models the Animations tab can use, from the shared AVOS model catalog
(apps/agentic_core/models/catalog.json, the same list as the Facts tab and the Models page).

    AI pictures (backdrops):  free chain (default) | best | z-image | qwen-image | flux-schnell
    AI finish (whole film):   wan-vace (re-style keeping the motion) | wan-2.2-animate | scail-2 (character performs
                              each shot's motion) | ltx-2.3 (re-animate each shot from its first frame)

Each model runs on your AVOS GPU workers (Settings → GPU workers; studio/gpu.py picks the worker, backend and
precision), on your GPU server (ComfyUI, COMFYUI_URL + COMFYUI_WORKFLOW_DIR/<model id>.json) when its workflow is
there, else on fal.ai (FAL_KEY); FLUX also on Cloudflare's free tier. MODEL_BACKEND=gpu|fal|comfyui forces one.
"""
from __future__ import annotations

import base64
import copy
import functools
import json
import math
import os
import re
import time
import uuid
from pathlib import Path
from typing import Any

import httpx

from . import avos_settings, config, gpu, provider_health as PH

IMAGE_CHOICES = ("free", "best", "z-image", "qwen-image", "flux-schnell")
FINISH_CHOICES = ("wan-vace", "wan-2.2-animate", "scail-2", "ltx-2.3")
NEGATIVE = "blurry, low quality, distorted, deformed hands, extra limbs, flicker, watermark, text"


class ModelUnavailable(RuntimeError):
    pass


def catalog_path() -> Path | None:
    for cand in (os.environ.get("AVOS_MODEL_CATALOG"),
                 config.SERVICE_ROOT / "catalog.json",                                          # Docker (mounted / copied)
                 config.SERVICE_ROOT.parent / "agentic_core" / "models" / "catalog.json"):     # apps/ checkout
        if cand and Path(cand).is_file():
            return Path(cand)
    return None


@functools.lru_cache(maxsize=1)
def catalog() -> dict:
    p = catalog_path()
    return json.loads(p.read_text("utf-8")) if p else {"models": [], "tasks": {}, "backends": {}}


def custom(model_id: str) -> dict | None:
    """A model added on the AVOS Settings page (shared with the Facts tab)."""
    return avos_settings.custom_model(model_id)


def image_choices() -> tuple[str, ...]:
    return (*IMAGE_CHOICES, *[m["id"] for m in avos_settings.custom_models("image")])


def finish_choices() -> tuple[str, ...]:
    return (*FINISH_CHOICES, *[m["id"] for m in avos_settings.custom_models("video")])


def get(model_id: str) -> dict:
    for m in catalog()["models"]:
        if m["id"] == model_id:
            return m
    c = custom(model_id)
    if c:
        return {"id": c["id"], "name": c["name"], "task": c["task"], "custom": True, "kind": c["kind"],
                "best_for": c.get("notes") or "Your own model", "license": c.get("license") or "Check the model's licence",
                "commercial": "unknown", **({"comfyui": {"workflow": c.get("workflow") or f"{c['id']}.json", "template": "your uploaded workflow"}}
                                           if c["kind"] == "comfyui" else {}), "definition": c}
    raise ModelUnavailable(f"Unknown model {model_id} (the model catalog wasn't found or doesn't list it).")


def workflow_dir() -> Path:
    env = os.environ.get("COMFYUI_WORKFLOW_DIR")
    if env:
        return Path(env)
    for cand in (Path("/app/comfyui_workflows"), config.SERVICE_ROOT.parent / "comfyui_workflows"):
        if cand.is_dir():
            return cand
    return config.SERVICE_ROOT.parent / "comfyui_workflows"


def available(model_id: str) -> dict[str, str | None]:
    avos_settings.apply()
    m = get(model_id)
    out: dict[str, str | None] = {}
    if m.get("custom"):
        c = m["definition"]
        if c["kind"] == "comfyui":
            wf = workflow_dir() / m["comfyui"]["workflow"]
            out["comfyui"] = ("Set your GPU server address (Settings → GPU server)." if not os.environ.get("COMFYUI_URL")
                              else None if wf.is_file() else "Upload its ComfyUI workflow (Settings → Models).")
        else:
            key = c.get("key_env")
            out[c["kind"]] = None if (not key or os.environ.get(key)) else f"Add the {key} key (Settings → API keys)."
        return out
    if gpu.workers() and (m.get("fabric") or m.get("comfyui")):
        out["gpu"] = gpu.why_not(model_id, m.get("fabric")) or None
    if m.get("comfyui"):
        wf = workflow_dir() / m["comfyui"]["workflow"]
        out["comfyui"] = ("Set your GPU server address (Settings → GPU server, or AI settings)." if not os.environ.get("COMFYUI_URL")
                          else None if wf.is_file() else f"Upload its '{m['comfyui']['template']}' workflow (Settings → Models).")
    if m.get("cloudflare"):
        out["cloudflare"] = PH.down("cloudflare") if os.environ.get("CLOUDFLARE_ACCOUNT_ID") and os.environ.get("CLOUDFLARE_API_TOKEN") \
            else "Set CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_API_TOKEN."
    if m.get("fal"):
        out["fal"] = PH.down("fal") if os.environ.get("FAL_KEY") else "Add a fal.ai key (AI settings or FAL_KEY)."
    return out


def backend_for(model_id: str, prefer: str | None = None) -> str:
    """Where the model runs now. prefer: the place you picked (gpu / comfyui / fal / cloudflare); used when it's usable,
    else the usual order (your GPUs, free tiers, then paid)."""
    m, avail = get(model_id), available(model_id)
    if prefer and prefer != "auto" and not m.get("custom") and avail.get(prefer, "missing") is None:
        return prefer
    if m.get("custom"):
        kind, why = next(iter(avail.items()))
        if why:
            raise ModelUnavailable(f"{m['name']}: {why}")
        return kind
    forced = (os.environ.get("MODEL_BACKEND") or "").strip().lower()
    if forced in ("gpu", "fal", "comfyui", "cloudflare"):
        if forced not in avail:
            raise ModelUnavailable(f"{m['name']} can't run on {forced} (MODEL_BACKEND).")
        if avail[forced]:
            raise ModelUnavailable(f"{m['name']} on {forced}: {avail[forced]}")
        return forced
    for b in ("gpu", "comfyui", "cloudflare", "fal"):      # your GPUs first, then free tiers, then paid
        if b in avail and avail[b] is None:
            return b
    why = "; ".join(f"{b}: {r}" for b, r in avail.items() if r)
    raise ModelUnavailable(f"{m['name']} isn't set up yet. {why or 'It runs only on your GPU server.'}")


def ready(model_id: str) -> tuple[bool, str]:
    try:
        return True, backend_for(model_id)
    except ModelUnavailable as e:
        return False, str(e)


TEXT_RX = re.compile(r"\b(text|title|headline|caption|label(?:s|ed)?|signboard|poster|banner|infographic|diagram|chart|"
                     r"graph|slide|menu|typography|lettering|written|words?|quote|equation|formula|timeline)\b"
                     r"|[\"“][^\"”]{2,40}[\"”]|文字|標題|标题|海報|海报|招牌", re.I)


NEGATED_TEXT_RX = re.compile(r"\b(?:no|without|free of|avoid)\s+(?:any\s+)?(?:text|words?|letters|lettering|captions?|labels?|titles?|logos?|watermarks?)\b", re.I)


def route_image(prompt: str) -> list[str]:
    first = "qwen-image" if TEXT_RX.search(NEGATED_TEXT_RX.sub(" ", prompt or "")) else "z-image"
    return [first, *[m for m in ("z-image", "qwen-image", "flux-schnell") if m != first]]


def status() -> dict:
    """For AI settings: each image / finish model, ready or what's missing."""
    def row(mid: str) -> dict:
        try:
            m = get(mid)
        except ModelUnavailable as e:
            return {"id": mid, "name": mid, "ready": False, "why": str(e)}
        ok, why = ready(mid)
        return {"id": mid, "name": m["name"], "ready": ok, "custom": bool(m.get("custom")), "backend": why if ok else None, "why": None if ok else why,
                "bestFor": m.get("best_for"), "license": m.get("license"), "commercial": m.get("commercial"),
                "price": (m.get("fal") or {}).get("price")}
    avos_settings.apply()
    return {"images": [row(m) for m in image_choices()[2:]], "finish": [row(m) for m in finish_choices()],
            "fal": bool(os.environ.get("FAL_KEY")), "comfyui": os.environ.get("COMFYUI_URL") or "",
            "catalog": bool(catalog_path())}


# ---------- fal.ai (queue API) ----------
def data_uri(data: bytes) -> str:
    mime = "application/octet-stream"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        mime = "image/png"
    elif data[:3] == b"\xff\xd8\xff":
        mime = "image/jpeg"
    elif data[4:8] == b"ftyp":
        mime = "video/mp4"
    elif data[:4] == b"RIFF" and data[8:12] == b"WAVE":
        mime = "audio/wav"
    return f"data:{mime};base64,{base64.b64encode(data).decode()}"


def _fal_check(r: httpx.Response, endpoint: str) -> None:
    if r.status_code < 400:
        return
    kind = PH.classify(r.status_code, r.text)
    if kind:      # an empty balance / refused key won't fix itself: skip fal.ai for a while, fall through to the next option
        raise ModelUnavailable(PH.mark("fal", kind, r.text))
    hint = {401: " Check the fal.ai key.", 403: " Check the fal.ai key.", 402: " Add credit at fal.ai/dashboard/billing."}.get(r.status_code, "")
    raise RuntimeError(f"fal.ai {endpoint}: error {r.status_code}: {r.text[:300]}{hint}")


def fal_run(endpoint: str, payload: dict, timeout: float = 1200, poll: float = 4.0, key: str | None = None) -> dict:
    key = key or os.environ.get("FAL_KEY")
    if not key:
        raise ModelUnavailable("No fal.ai key.")
    queue = (os.environ.get("FAL_QUEUE_URL") or "https://queue.fal.run").rstrip("/")
    h = {"Authorization": f"Key {key}"}
    with httpx.Client(timeout=120, follow_redirects=True) as c:
        r = c.post(f"{queue}/{endpoint}", headers=h, json=payload)
        _fal_check(r, endpoint)
        j = r.json()
        status_url = j.get("status_url") or f"{queue}/{endpoint}/requests/{j['request_id']}/status"
        result_url = j.get("response_url") or f"{queue}/{endpoint}/requests/{j['request_id']}"
        end = time.monotonic() + timeout
        while True:
            s = c.get(status_url, headers=h)
            _fal_check(s, endpoint)
            st = s.json().get("status")
            if st == "COMPLETED":
                break
            if st not in ("IN_QUEUE", "IN_PROGRESS"):
                raise RuntimeError(f"fal.ai {endpoint}: {st}")
            if time.monotonic() > end:
                raise RuntimeError(f"fal.ai {endpoint} didn't finish in {timeout:.0f}s")
            time.sleep(poll)
        res = c.get(result_url, headers=h)
        _fal_check(res, endpoint)
        return res.json()


def _first_url(res: dict, *keys: str) -> str | None:
    for k in keys:
        v = res.get(k)
        if isinstance(v, dict) and v.get("url"):
            return v["url"]
        if isinstance(v, list) and v:
            return v[0]["url"] if isinstance(v[0], dict) else v[0]
        if isinstance(v, str):
            return v
    return None


def _download(url: str) -> bytes:
    if url.startswith("data:"):
        return base64.b64decode(url.split(",", 1)[1])
    r = httpx.get(url, timeout=300, follow_redirects=True)
    r.raise_for_status()
    return r.content


# ---------- ComfyUI on your GPU server ----------
NUMERIC = ("{{SEED}}", "{{WIDTH}}", "{{HEIGHT}}", "{{FRAMES}}", "{{FPS}}", "{{DURATION}}", "{{STEPS}}")
FILES = {"{{IMAGE}}": "png", "{{AUDIO}}": "wav", "{{VIDEO}}": "mp4", "{{IMAGE2}}": "png", "{{IMAGE3}}": "png", "{{IMAGE4}}": "png"}
TEXTS = ("{{PROMPT}}", "{{NEGATIVE_PROMPT}}", "{{LYRICS}}", "{{LANGUAGE}}")
WANT_EXTS = {"image": (".png", ".jpg", ".jpeg", ".webp"), "audio": (".flac", ".wav", ".mp3", ".ogg", ".m4a"),
             "video": (".mp4", ".webm", ".mov")}
JPEG_MAGIC = b"\xff\xd8\xff"


def _fill(node: Any, values: dict) -> Any:
    if isinstance(node, dict):
        return {k: _fill(v, values) for k, v in node.items()}
    if isinstance(node, list):
        return [_fill(v, values) for v in node]
    if isinstance(node, str):
        s = node.strip()
        if s in NUMERIC or s in FILES:
            return values.get(s, node)
        for k in TEXTS:
            node = node.replace(k, str(values.get(k, "")))
    return node


def comfy_run(model_id: str, values: dict, files: dict[str, bytes | None], want: str, timeout: float = 1800) -> bytes:
    base = os.environ["COMFYUI_URL"].rstrip("/")
    wf_path = workflow_dir() / get(model_id)["comfyui"]["workflow"]
    wf = json.loads(wf_path.read_text("utf-8"))
    if "nodes" in wf and "links" in wf:
        raise RuntimeError(f"{wf_path.name} is a regular ComfyUI save; use Workflow → Export (API).")
    text = json.dumps(wf)
    with httpx.Client(timeout=120) as c:
        for ph, ext in FILES.items():
            if ph not in text:
                continue
            data = files.get(ph)
            if not data:
                raise RuntimeError(f"{wf_path.name} expects {ph} but none was given.")
            if ext == "png" and data[:3] == JPEG_MAGIC:
                ext = "jpg"
            name = f"avos_{uuid.uuid4().hex[:12]}.{ext}"
            r = c.post(f"{base}/upload/image", files={"image": (name, data, "application/octet-stream")}, data={"overwrite": "true"})
            r.raise_for_status()
            info = r.json()
            values[ph] = f"{info['subfolder']}/{info['name']}" if info.get("subfolder") else info["name"]
        r = c.post(f"{base}/prompt", json={"prompt": _fill(copy.deepcopy(wf), values), "client_id": uuid.uuid4().hex})
        if r.status_code >= 400:
            raise RuntimeError(f"ComfyUI rejected {wf_path.name}: {r.text[:500]}")
        pid = r.json()["prompt_id"]
        end = time.monotonic() + timeout
        while True:
            h = c.get(f"{base}/history/{pid}")
            entry = h.json().get(pid) if h.status_code == 200 else None
            if entry:
                st = entry.get("status") or {}
                if st.get("status_str") == "error":
                    msgs = [m for m in st.get("messages", []) if m and m[0] == "execution_error"]
                    raise RuntimeError("ComfyUI: " + (msgs[-1][1].get("exception_message") if msgs else "workflow failed"))
                if st.get("completed", True):
                    break
            if time.monotonic() > end:
                raise RuntimeError(f"ComfyUI didn't finish in {timeout:.0f}s")
            time.sleep(2)
        outs = [f for node in (entry.get("outputs") or {}).values() for items in node.values() if isinstance(items, list)
                for f in items if isinstance(f, dict) and "filename" in f]
        exts = WANT_EXTS.get(want, WANT_EXTS["video"])
        pick = [f for f in outs if f["filename"].lower().endswith(exts) and f.get("type", "output") == "output"]
        if not pick:
            raise RuntimeError(f"ComfyUI saved no {want}; end {wf_path.name} with Save "
                               f"{ {'image': 'Image', 'audio': 'Audio'}.get(want, 'Video (MP4)') }.")
        f = pick[0]
        v = c.get(f"{base}/view", params={"filename": f["filename"], "subfolder": f.get("subfolder", ""), "type": f.get("type", "output")})
        v.raise_for_status()
        return v.content


# ---------- the jobs ----------
IMAGE_STEPS = {"z-image": 8, "qwen-image": 30, "flux-schnell": 4}


def _size(w: int, h: int, long_side: int = 1280, mult: int = 16) -> tuple[int, int]:
    s = long_side / max(w, h, 1)
    return max(mult, round(w * s / mult) * mult), max(mult, round(h * s / mult) * mult)


def _vals(prompt: str, w: int, h: int, seed: int | None, seconds: float = 5.0, image: bytes | None = None,
          video: bytes | None = None) -> dict:
    return {"prompt": prompt, "negative_prompt": NEGATIVE, "width": w, "height": h,
            "aspect_ratio": "1:1" if abs(w - h) < 8 else ("9:16" if h > w else "16:9"),
            "seed": None if seed is None else int(seed) % 2_147_483_647, "duration": round(seconds, 2), "duration_int": max(1, round(seconds)),
            "num_frames": int(round(seconds * 16)) + 1, "fps": 16, "image_url": data_uri(image) if image else None,
            "audio_url": None, "video_url": data_uri(video) if video else None}


def replicate_run(ref: str, payload: dict, key: str, timeout: float = 1200, poll: float = 4.0):
    api = (os.environ.get("REPLICATE_API_URL") or "https://api.replicate.com/v1").rstrip("/")
    h = {"Authorization": f"Bearer {key}"}
    url, body = ((f"{api}/predictions", {"version": ref.split(":", 1)[1], "input": payload}) if ":" in ref
                 else (f"{api}/models/{ref}/predictions", {"input": payload}))
    with httpx.Client(timeout=120, follow_redirects=True) as c:
        r = c.post(url, headers={**h, "Prefer": "wait=60"}, json=body)
        if r.status_code >= 400:
            raise RuntimeError(f"Replicate {ref}: error {r.status_code}: {r.text[:300]}")
        pred = r.json()
        end = time.monotonic() + timeout
        while pred.get("status") not in ("succeeded", "failed", "canceled"):
            if time.monotonic() > end:
                raise RuntimeError(f"Replicate {ref} didn't finish in {timeout:.0f}s")
            time.sleep(poll)
            g = c.get((pred.get("urls") or {}).get("get") or f"{api}/predictions/{pred['id']}", headers=h)
            g.raise_for_status()
            pred = g.json()
        if pred["status"] != "succeeded":
            raise RuntimeError(f"Replicate {ref} {pred['status']}: {pred.get('error')}")
        return pred.get("output")


def _any_url(res, preferred: str = "") -> str | None:
    if preferred and isinstance(res, dict):
        node = res
        for part in preferred.split("."):
            node = node.get(part) if isinstance(node, dict) else (node[int(part)] if isinstance(node, list) and part.isdigit() and int(part) < len(node) else None)
        if node is not None:
            return _any_url(node)
    if isinstance(res, str):
        return res if res.startswith(("http", "data:")) else None
    if isinstance(res, list):
        return next((u for u in (_any_url(x) for x in res) if u), None)
    if isinstance(res, dict):
        if isinstance(res.get("url"), str):
            return res["url"]
        return next((u for u in (_any_url(res[k]) for k in ("video", "videos", "images", "image", "output", "outputs") if k in res) if u), None)
    return None


def run_custom(model_id: str, vals: dict, files: dict, want: str) -> bytes:
    """A model added in Settings: fal.ai / Replicate with its input template, or its ComfyUI workflow."""
    c = custom(model_id)
    backend_for(model_id)
    if c["kind"] == "comfyui":
        return comfy_run(model_id, {"{{PROMPT}}": vals["prompt"], "{{NEGATIVE_PROMPT}}": NEGATIVE, "{{SEED}}": vals.get("seed") or 1,
                                    "{{WIDTH}}": vals["width"] - vals["width"] % 32, "{{HEIGHT}}": vals["height"] - vals["height"] % 32,
                                    "{{FRAMES}}": vals["num_frames"], "{{FPS}}": 16, "{{DURATION}}": vals["duration"], "{{STEPS}}": 20},
                         files, want)
    payload = avos_settings.fill(c.get("inputs") or {}, vals)
    key = os.environ.get(c.get("key_env") or "") or ""
    if c["kind"] == "fal":
        res = fal_run(c["endpoint"], payload, key=key or None)
    else:
        if not key:
            raise ModelUnavailable(f"{c['name']}: add the {c.get('key_env')} key (Settings → API keys).")
        res = replicate_run(c["endpoint"], payload, key)
    url = _any_url(res, c.get("output") or "")
    if not url:
        raise RuntimeError(f"{c['name']} returned no file (set its 'output' field in Settings).")
    return _download(url)


def uses_references(model_id: str) -> bool:
    """A model you added whose input template takes pictures ({{image_url}} or {{image_urls}}): it can edit from references."""
    c = custom(model_id)
    return bool(c and c.get("task") == "image" and c["kind"] in ("fal", "replicate")
                and (avos_settings.uses(c.get("inputs"), "image_urls") or avos_settings.uses(c.get("inputs"), "image_url")))


def image_edit(model_id: str, prompt: str, refs: list[bytes], w: int, h: int, seed: int | None = None) -> bytes:
    """A picture drawn from reference pictures (character sheets, the place) by a model you added in Settings.
    {{image_url}} = the first reference, {{image_urls}} = all of them."""
    W, H = _size(w, h)
    vals = _vals(prompt, W, H, seed, image=refs[0] if refs else None)
    vals["image_urls"] = [data_uri(r) for r in refs[:4]] or None
    return run_custom(model_id, vals, {}, "image")


def image(model_id: str, prompt: str, w: int, h: int, seed: int | None = None, backend: str | None = None) -> bytes:
    if custom(model_id):
        W, H = _size(w, h)
        return run_custom(model_id, _vals(prompt, W, H, seed), {}, "image")
    backend = backend_for(model_id, backend)
    W, H = _size(w, h)
    if backend == "gpu":
        pl = gpu.pick(model_id, get(model_id).get("fabric"))
        if pl is None:
            raise ModelUnavailable(gpu.why_not(model_id, get(model_id).get("fabric")))
        return gpu.run(pl, model_id=model_id, prompt=prompt, negative_prompt=NEGATIVE, width=W - W % 32, height=H - H % 32,
                       task="image", want="image", seed=seed, steps=IMAGE_STEPS[model_id], timeout=600)
    if backend == "comfyui":
        return comfy_run(model_id, {"{{PROMPT}}": prompt, "{{NEGATIVE_PROMPT}}": NEGATIVE, "{{SEED}}": int(seed or time.time()) % 2_147_483_647,
                                    "{{WIDTH}}": W - W % 32, "{{HEIGHT}}": H - H % 32, "{{STEPS}}": IMAGE_STEPS[model_id]}, {}, "image")
    if backend == "cloudflare":
        acc, tok = os.environ["CLOUDFLARE_ACCOUNT_ID"], os.environ["CLOUDFLARE_API_TOKEN"]
        r = httpx.post(f"https://api.cloudflare.com/client/v4/accounts/{acc}/ai/run/{get(model_id)['cloudflare']['model']}",
                       headers={"Authorization": f"Bearer {tok}"}, json={"prompt": prompt[:2000], "steps": 6}, timeout=120)
        if r.status_code >= 400 and (kind := PH.classify(r.status_code, r.text)):
            raise ModelUnavailable(PH.mark("cloudflare", kind, r.text))
        r.raise_for_status()
        return base64.b64decode(r.json()["result"]["image"])
    payload: dict[str, Any] = {"prompt": prompt, "image_size": {"width": W, "height": H}, "num_images": 1,
                               "num_inference_steps": IMAGE_STEPS[model_id], "output_format": "png"}
    if model_id == "qwen-image":
        payload.update(guidance_scale=2.5, negative_prompt=NEGATIVE)
    if seed is not None:
        payload["seed"] = int(seed) % 2_147_483_647
    url = _first_url(fal_run(get(model_id)["fal"]["endpoint"], payload, timeout=300), "images", "image")
    if not url:
        raise RuntimeError(f"fal.ai {model_id} returned no image")
    return _download(url)


FPS = {"wan-vace": 16, "wan-2.2-animate": 16, "scail-2": 16, "ltx-2.3": 25}


def frames(model_id: str, seconds: float) -> int:
    fps, mult = FPS[model_id], (8 if model_id == "ltx-2.3" else 4)
    lo, hi = {"wan-vace": (81, 241), "ltx-2.3": (9, 481)}.get(model_id, (17, 241))
    n = max(lo, round(seconds * fps) + 1)
    n = math.ceil((n - 1) / mult) * mult + 1
    while n > hi:
        n -= mult
    return n


def finish_shot(model_id: str, prompt: str, *, first_frame: bytes, clip: bytes, seconds: float, w: int, h: int,
                seed: int | None = None) -> bytes:
    """One shot through an AI finish model. Returns an mp4 (any length; the caller fits it to the shot)."""
    if custom(model_id):
        return run_custom(model_id, _vals(prompt, w, h, seed, seconds, image=first_frame, video=clip),
                          {"{{IMAGE}}": first_frame, "{{VIDEO}}": clip}, "video")
    backend = backend_for(model_id)
    if backend == "gpu":
        pl = gpu.pick(model_id, get(model_id).get("fabric"))
        if pl is None:
            raise ModelUnavailable(gpu.why_not(model_id, get(model_id).get("fabric")))
        return gpu.run(pl, model_id=model_id, prompt=prompt, negative_prompt=NEGATIVE, width=w - w % 32, height=h - h % 32,
                       task="video", want="video", seconds=seconds, frames=frames(model_id, seconds), fps=FPS[model_id],
                       seed=seed, inputs={"image": first_frame, "video": clip})
    if backend == "comfyui":
        return comfy_run(model_id, {"{{PROMPT}}": prompt, "{{NEGATIVE_PROMPT}}": NEGATIVE, "{{SEED}}": int(seed or 1) % 2_147_483_647,
                                    "{{WIDTH}}": w - w % 32, "{{HEIGHT}}": h - h % 32, "{{FRAMES}}": frames(model_id, seconds),
                                    "{{FPS}}": FPS[model_id], "{{DURATION}}": round(seconds, 2)},
                         {"{{IMAGE}}": first_frame, "{{VIDEO}}": clip}, "video")
    m = get(model_id)
    img, vid = data_uri(first_frame), data_uri(clip)
    if model_id == "wan-vace":
        payload = {"prompt": prompt, "video_url": vid, "task": "depth", "ref_image_urls": [img], "first_frame_url": img,
                   "num_frames": frames(model_id, seconds), "resolution": os.environ.get("WAN_VACE_RESOLUTION") or "720p",
                   "negative_prompt": NEGATIVE}
    elif model_id == "wan-2.2-animate":
        payload = {"video_url": vid, "image_url": img, "resolution": os.environ.get("WAN_2_2_ANIMATE_RESOLUTION") or "480p"}
    elif model_id == "ltx-2.3":
        payload = {"prompt": prompt, "image_url": img, "duration": next((d for d in (6, 8, 10) if seconds <= d + 0.5), 10),
                   "resolution": os.environ.get("LTX_2_3_RESOLUTION") or "1080p", "aspect_ratio": "auto", "generate_audio": False}
    else:
        raise ModelUnavailable(f"{m['name']} has no hosted API: run it on your GPU server (ComfyUI).")
    if seed is not None:
        payload["seed"] = int(seed) % 2_147_483_647
    url = _first_url(fal_run(m["fal"]["endpoint"], payload), "video", "videos")
    if not url:
        raise RuntimeError(f"fal.ai {model_id} returned no video")
    return _download(url)


# ---------- any catalog model on your GPUs (Series: keyframes from references, voices, lip-sync, sound, music) ----------
def run_model(model_id: str, *, task: str, want: str, prompt: str, w: int = 1280, h: int = 720, seconds: float = 5.0,
              frames: int | None = None, fps: int | None = None, seed: int | None = None, steps: int | None = None,
              inputs: dict[str, bytes | None] | None = None, options: dict | None = None, negative: str = NEGATIVE,
              timeout: float = 1800, priority: int = 5, tag: str | None = None, backend: str | None = None) -> bytes:
    """One job on your GPU workers (the studio picks worker, backend and precision), your ComfyUI server, or (video,
    lip-sync, motion transfer) fal.ai.

    inputs: image, image2..image4 (reference pictures), audio, video. options: model settings (speech language,
    voice transcript / description, emotion; music lyrics). backend: the place you picked (else the usual order)."""
    backend = backend_for(model_id, backend)
    m = get(model_id)
    W, H = (w - w % 32, h - h % 32) if want in ("image", "video") else (w, h)
    if m.get("custom") and backend in ("fal", "replicate"):
        # a model you added in Settings (fal.ai / Replicate): its own input template, filled from this job
        ins = inputs or {}
        vals = _vals(prompt, W, H, seed, seconds, image=ins.get("image"), video=ins.get("video"))
        vals["negative_prompt"] = negative
        if ins.get("audio"):
            vals["audio_url"] = data_uri(ins["audio"])
        return run_custom(model_id, vals, {}, want)
    if backend == "gpu":
        pl = gpu.pick(model_id, m.get("fabric"))
        if pl is None:
            raise ModelUnavailable(gpu.why_not(model_id, m.get("fabric")))
        return gpu.run(pl, model_id=model_id, prompt=prompt, negative_prompt=negative, width=W, height=H, task=task,
                       want=want, seconds=seconds, frames=frames, fps=fps, seed=seed, steps=steps, inputs=inputs or {},
                       options=options or {}, timeout=timeout, priority=priority, tag=tag)
    if backend == "comfyui":
        files = {"{{IMAGE}}": (inputs or {}).get("image"), "{{AUDIO}}": (inputs or {}).get("audio"),
                 "{{VIDEO}}": (inputs or {}).get("video"), "{{IMAGE2}}": (inputs or {}).get("image2"),
                 "{{IMAGE3}}": (inputs or {}).get("image3"), "{{IMAGE4}}": (inputs or {}).get("image4")}
        return comfy_run(model_id, {"{{PROMPT}}": prompt, "{{NEGATIVE_PROMPT}}": negative,
                                    "{{SEED}}": int(seed if seed is not None else time.time()) % 2_147_483_647,
                                    "{{WIDTH}}": W, "{{HEIGHT}}": H, "{{FRAMES}}": frames or max(1, round(seconds * (fps or 16)) + 1),
                                    "{{FPS}}": fps or 16, "{{DURATION}}": round(seconds, 2), "{{STEPS}}": steps or 20,
                                    "{{LYRICS}}": (options or {}).get("lyrics") or "[instrumental]",
                                    "{{LANGUAGE}}": (options or {}).get("language") or "en"},
                         files, want, timeout=timeout)
    if backend == "fal" and m.get("fal") and task in ("video", "avatar", "control"):
        return fal_video(model_id, prompt=prompt, w=W, h=H, seed=seed, seconds=seconds, inputs=inputs or {}, negative=negative)
    raise ModelUnavailable(f"{m['name']} runs on your GPU workers or GPU server (Settings → GPU workers).")


def fal_video(model_id: str, *, prompt: str, w: int, h: int, seed: int | None, seconds: float, inputs: dict[str, bytes | None],
              negative: str = NEGATIVE) -> bytes:
    """A clip on fal.ai: image-to-video (Wan 2.2, LTX-2.3), lip-sync (InfiniteTalk, LongCat Avatar), motion transfer
    (Wan 2.2 Animate, Wan VACE). The same inputs as AVOS Facts (agentic_core/models/video/catalog_video.py)."""
    m = get(model_id)
    endpoint = m["fal"]["endpoint"]
    img = data_uri(inputs["image"]) if inputs.get("image") else None
    aud = data_uri(inputs["audio"]) if inputs.get("audio") else None
    vid = data_uri(inputs["video"]) if inputs.get("video") else None

    def nframes(fps: int, mult: int, lo: int, hi: int) -> int:
        n = max(lo, round(seconds * fps) + 1)
        n = math.ceil((n - 1) / mult) * mult + 1
        while n > hi:
            n -= mult
        return n
    data: dict[str, Any] = {"prompt": prompt}
    if model_id == "wan-2.2":
        data.update(image_url=img, num_frames=nframes(16, 4, 17, 161), frames_per_second=16, resolution=os.environ.get("WAN_2_2_RESOLUTION") or "720p",
                    aspect_ratio="auto", negative_prompt=negative)
    elif model_id == "ltx-2.3":
        data.update(image_url=img, duration=next((d for d in (6, 8, 10) if seconds <= d + 0.5), 10),
                    resolution=os.environ.get("LTX_2_3_RESOLUTION") or "1080p", aspect_ratio="auto", generate_audio=False)
    elif model_id == "infinitetalk":
        data.update(image_url=img, audio_url=aud, num_frames=nframes(25, 4, 41, 721), resolution=os.environ.get("INFINITETALK_RESOLUTION") or "480p")
    elif model_id == "longcat-avatar":
        data.update(image_url=img, audio_url=aud, negative_prompt=negative, resolution=os.environ.get("LONGCAT_AVATAR_RESOLUTION") or "480p",
                    num_segments=min(10, max(1, math.ceil(seconds / 5.0))))
    elif model_id == "wan-2.2-animate":
        data = {"video_url": vid, "image_url": img, "resolution": os.environ.get("WAN_2_2_ANIMATE_RESOLUTION") or "480p"}
    elif model_id == "wan-vace":
        data.update(num_frames=nframes(16, 4, 81, 241), resolution=os.environ.get("WAN_VACE_RESOLUTION") or "720p", negative_prompt=negative,
                    **({"ref_image_urls": [img], "first_frame_url": img} if img else {}), **({"video_url": vid, "task": "depth"} if vid else {}))
    else:
        raise ModelUnavailable(f"{m['name']} has no hosted API: run it on your GPU worker.")
    if seed is not None:
        data["seed"] = int(seed) % 2_147_483_647
    url = _first_url(fal_run(endpoint, {k: v for k, v in data.items() if v is not None}), "video", "videos")
    if not url:
        raise RuntimeError(f"fal.ai {model_id} returned no video")
    return _download(url)
