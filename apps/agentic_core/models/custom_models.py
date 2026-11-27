"""Models added on the Settings page: any fal.ai or Replicate model, any ComfyUI workflow, any OpenAI-compatible text model.

The model definition (agentic_core/settings_store.py) carries a JSON input template with {{placeholders}}:
    {{prompt}} {{negative_prompt}} {{width}} {{height}} {{aspect_ratio}} {{seed}} {{duration}} {{num_frames}} {{fps}}
    {{image_url}} {{audio_url}} {{video_url}}   (files go as data: URIs, which fal.ai and Replicate accept)
Fields whose placeholder has no value (e.g. {{audio_url}} when there is no audio) are left out.
"""
from __future__ import annotations

import asyncio
import os
import time
from typing import Any

import httpx

from agentic_core import settings_store
from agentic_core.models import catalog, fal_client
from agentic_core.models.image.base import ImageProvider
from agentic_core.models.video.base import VideoProvider

REPLICATE_API = os.getenv("REPLICATE_API_URL", "https://api.replicate.com/v1").rstrip("/")


def _aspect(w: int, h: int) -> str:
    if abs(w - h) < 8:
        return "1:1"
    return "9:16" if h > w else "16:9"


def values(*, prompt: str, width: int, height: int, seed: int | None, seconds: float = 5.0, fps: int = 16,
           image: bytes | None = None, audio: bytes | None = None, video: bytes | None = None) -> dict[str, Any]:
    return {
        "prompt": prompt, "negative_prompt": "blurry, low quality, distorted, watermark", "width": int(width),
        "height": int(height), "aspect_ratio": _aspect(width, height), "seed": None if seed is None else int(seed) % 2_147_483_647,
        "duration": round(float(seconds), 2), "duration_int": max(1, round(seconds)), "num_frames": int(round(seconds * fps)) + 1,
        "fps": fps, "image_url": fal_client.data_uri(image) if image else None,
        "audio_url": fal_client.data_uri(audio) if audio else None, "video_url": fal_client.data_uri(video) if video else None,
    }


def _find_url(result: Any, preferred: str = "") -> str | None:
    """The first file URL in a result: the configured output key, else common shapes."""
    if preferred and isinstance(result, dict):
        node: Any = result
        for part in preferred.split("."):
            node = node.get(part) if isinstance(node, dict) else (node[int(part)] if isinstance(node, list) and part.isdigit() and int(part) < len(node) else None)
        if node is not None:
            return _find_url(node)
    if isinstance(result, str):
        return result if result.startswith(("http", "data:")) else None
    if isinstance(result, list):
        for x in result:
            u = _find_url(x)
            if u:
                return u
        return None
    if isinstance(result, dict):
        if isinstance(result.get("url"), str):
            return result["url"]
        for k in ("video", "videos", "images", "image", "output", "outputs", "audio"):
            if k in result:
                u = _find_url(result[k])
                if u:
                    return u
    return None


async def replicate_run(ref: str, payload: dict[str, Any], *, key: str, timeout: float = 1200.0, poll: float = 4.0) -> Any:
    headers = {"Authorization": f"Bearer {key}"}
    if ":" in ref:
        url, body = f"{REPLICATE_API}/predictions", {"version": ref.split(":", 1)[1], "input": payload}
    else:
        url, body = f"{REPLICATE_API}/models/{ref}/predictions", {"input": payload}
    async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as c:
        r = await c.post(url, headers={**headers, "Prefer": "wait=60"}, json=body)
        if r.status_code >= 400:
            hint = " Check the Replicate token." if r.status_code in (401, 403) else (" Add billing on replicate.com." if r.status_code == 402 else "")
            raise RuntimeError(f"Replicate {ref}: error {r.status_code}: {r.text[:300]}.{hint}")
        pred = r.json()
        deadline = time.monotonic() + timeout
        while pred.get("status") not in ("succeeded", "failed", "canceled"):
            if time.monotonic() > deadline:
                raise RuntimeError(f"Replicate {ref} did not finish within {timeout:.0f}s.")
            await asyncio.sleep(poll)
            g = await c.get((pred.get("urls") or {}).get("get") or f"{REPLICATE_API}/predictions/{pred['id']}", headers=headers)
            g.raise_for_status()
            pred = g.json()
        if pred["status"] != "succeeded":
            raise RuntimeError(f"Replicate {ref} {pred['status']}: {pred.get('error')}")
        return pred.get("output")


async def run_hosted(c: dict[str, Any], vals: dict[str, Any]) -> bytes:
    """A fal.ai or Replicate model: fill its template, run it, download the first file it returns."""
    payload = settings_store.fill(c.get("inputs") or {}, vals)
    key = os.getenv(c.get("key_env") or "") or None
    if c["kind"] == "fal":
        result: Any = await fal_client.run(c["endpoint"], payload, key=key)
    else:
        if not key:
            raise RuntimeError(f"{c['name']}: add the {c.get('key_env')} key (Settings → API keys).")
        result = await replicate_run(c["endpoint"], payload, key=key)
    url = _find_url(result, c.get("output") or "")
    if not url:
        raise RuntimeError(f"{c['name']} finished but returned no file (set the 'output' field to where its URL is).")
    return await fal_client.download(url)


def _comfy(c: dict[str, Any], fps: int = 16):
    from agentic_core.models.video.comfyui_provider import ComfyUIVideoProvider

    return ComfyUIVideoProvider(os.environ["COMFYUI_URL"], str(catalog.workflow_path(c["id"])), fps=fps, frame_multiple=4,
                                max_frames=int(os.getenv("COMFYUI_MAX_FRAMES") or 241),
                                timeout=float(os.getenv("COMFYUI_TIMEOUT") or 1800))


class CustomImageProvider(ImageProvider):
    def __init__(self, model_id: str) -> None:
        c = settings_store.custom_model(model_id)
        if not c or c["task"] != "image":
            raise ValueError(f"'{model_id}' isn't an image model added in Settings.")
        self.c, self.name = c, model_id

    async def generate(self, prompt: str, *, width: int = 512, height: int = 512, seed: int | None = None) -> bytes:
        catalog.backend_for(self.c["id"])        # says what's missing
        if self.c["kind"] == "comfyui":
            return await _comfy(self.c).run(prompt, width=width, height=height, seed=seed, want="image")
        return await run_hosted(self.c, values(prompt=prompt, width=width, height=height, seed=seed))


class CustomVideoProvider(VideoProvider):
    """A video or avatar model added in Settings. Avatar models get the presenter portrait and the shot's narration."""

    def __init__(self, model_id: str) -> None:
        c = settings_store.custom_model(model_id)
        if not c or c["task"] not in ("video", "avatar"):
            raise ValueError(f"'{model_id}' isn't a video model added in Settings.")
        self.c, self.name = c, model_id
        tpl = c.get("inputs") or {}
        audio = settings_store.uses(tpl, "audio_url") or c["task"] == "avatar"
        self.wants_audio = ("required" if c["task"] == "avatar" else "optional") if audio else None
        self.needs_presenter = c["task"] == "avatar"
        self.cost_per_clip_usd = 0.0

    async def generate(self, prompt: str, *, width: int = 512, height: int = 512, seed: int | None = None,
                       duration_seconds: float = 4.0, image: bytes | None = None, audio: bytes | None = None,
                       video: bytes | None = None) -> bytes:
        catalog.backend_for(self.c["id"])
        if self.c["kind"] == "comfyui":
            return await _comfy(self.c).run(prompt, width=width, height=height, seed=seed, duration_seconds=duration_seconds,
                                            files={"{{IMAGE}}": image, "{{AUDIO}}": audio, "{{VIDEO}}": video})
        return await run_hosted(self.c, values(prompt=prompt, width=width, height=height, seed=seed, seconds=duration_seconds,
                                               image=image, audio=audio, video=video))
