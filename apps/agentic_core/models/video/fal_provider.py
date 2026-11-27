import asyncio
import base64
import json
import os
import time
from typing import Any

import httpx

from agentic_core.models.video.base import VideoProvider

QUEUE = "https://queue.fal.run"
DEFAULT_MODEL = "fal-ai/kling-video/v2.1/standard/image-to-video"
NEGATIVE = "blur, distort, low quality, extra limbs, deformed hands, text, watermark"


def _mime(image: bytes) -> str:
    if image[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if image[:4] == b"RIFF" and image[8:12] == b"WEBP":
        return "image/webp"
    return "image/png"


def build_fal_input(model: str, *, prompt: str, image_url: str | None, duration_seconds: float,
                    width: int, height: int, seed: int | None) -> dict[str, Any]:
    """Map to each fal model family's input names; FAL_VIDEO_INPUT_JSON
    adds/overrides anything for other models."""
    name = model.lower()
    data: dict[str, Any] = {"prompt": prompt}
    if image_url:
        data["image_url"] = image_url
    if "kling" in name:
        data["duration"] = "5" if duration_seconds <= 5.5 else "10"
        data["negative_prompt"] = NEGATIVE
        if not image_url:
            data["aspect_ratio"] = "9:16" if height > width else ("1:1" if width == height else "16:9")
    elif "minimax" in name or "hailuo" in name:
        data["prompt_optimizer"] = True
    else:  # wan, ltx, seedance... common optional fields
        data["negative_prompt"] = NEGATIVE
        if seed is not None:
            data["seed"] = int(seed) % 2_147_483_647
    extra = os.getenv("FAL_VIDEO_INPUT_JSON")
    if extra:
        try:
            data.update(json.loads(extra))
        except json.JSONDecodeError as exc:
            raise ValueError("FAL_VIDEO_INPUT_JSON is not valid JSON.") from exc
    return data


class FalVideoProvider(VideoProvider):
    """
    Real AI video clips from fal.ai (one key, many models). Default model
    is Kling 2.1 Standard image-to-video (about $0.25 per 5-second clip
    on fal's price list); change it with FAL_VIDEO_MODEL to any fal
    video endpoint id, e.g. fal-ai/kling-video/v2.1/pro/image-to-video
    (better motion, pricier) or a Wan / Hailuo endpoint.

    PAID per clip after any signup credits. Animates the shot's own image
    so clips match the storyboard. Uses fal's queue API: submit, poll the
    status URL, then fetch the result.
    """

    name = "fal"

    def __init__(self, api_key: str, model: str = DEFAULT_MODEL, cost_per_clip_usd: float = 0.25,
                 timeout: float = 900.0, poll_interval: float = 5.0) -> None:
        self.api_key = api_key
        self.model = model.strip("/")
        self.cost_per_clip_usd = cost_per_clip_usd
        self.timeout = timeout
        self.poll_interval = poll_interval

    @property
    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Key {self.api_key}"}

    async def generate(self, prompt: str, *, width: int = 720, height: int = 1280, seed: int | None = None,
                       duration_seconds: float = 5.0, image: bytes | None = None) -> bytes:
        image_url = f"data:{_mime(image)};base64,{base64.b64encode(image).decode()}" if image else None
        body = build_fal_input(self.model, prompt=prompt, image_url=image_url, duration_seconds=duration_seconds,
                               width=width, height=height, seed=seed)
        async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
            try:
                submit = await client.post(f"{QUEUE}/{self.model}", headers=self._headers, json=body)
                _check(submit, f"starting {self.model}")
                job = submit.json()
                status_url = job.get("status_url") or f"{QUEUE}/{self.model}/requests/{job['request_id']}/status"
                result_url = job.get("response_url") or f"{QUEUE}/{self.model}/requests/{job['request_id']}"

                deadline = time.monotonic() + self.timeout
                while True:
                    status = await client.get(status_url, headers=self._headers)
                    _check(status, "checking the clip")
                    state = status.json().get("status")
                    if state == "COMPLETED":
                        break
                    if state not in ("IN_QUEUE", "IN_PROGRESS"):
                        raise RuntimeError(f"fal {self.model} returned status {state}: {status.text[:300]}")
                    if time.monotonic() > deadline:
                        raise RuntimeError(f"fal {self.model} did not finish within {self.timeout:.0f}s.")
                    await asyncio.sleep(self.poll_interval)

                result = await client.get(result_url, headers=self._headers)
                _check(result, "fetching the result")
                video = (result.json().get("video") or {}).get("url")
                if not video:
                    raise RuntimeError(f"fal {self.model} finished but returned no video: {result.text[:300]}")
                clip = await client.get(video)
                _check(clip, "downloading the clip")
                return clip.content
            except httpx.ConnectError as exc:
                raise RuntimeError("Could not reach fal.ai (queue.fal.run).") from exc


def _check(response: httpx.Response, doing: str) -> None:
    if response.status_code < 400:
        return
    try:
        payload = response.json()
        detail = payload.get("detail") or payload
    except ValueError:
        detail = response.text[:300]
    hint = ""
    if response.status_code in (401, 403):
        hint = " Check FAL_KEY (fal.ai/dashboard/keys)."
    elif response.status_code == 402 or "balance" in str(detail).lower():
        hint = " Your fal.ai balance is empty - add credit at fal.ai/dashboard/billing."
    elif response.status_code == 422:
        hint = " The model rejected an input; adjust FAL_VIDEO_INPUT_JSON for this model."
    raise RuntimeError(f"fal.ai error {response.status_code} while {doing}: {detail}.{hint}")
