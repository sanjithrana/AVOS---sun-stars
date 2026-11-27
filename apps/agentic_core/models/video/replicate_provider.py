import asyncio
import base64
import json
import os
import time
from typing import Any

import httpx

from agentic_core.models.video.base import VideoProvider

API = "https://api.replicate.com/v1"
DATA_URI_LIMIT = 256 * 1024  # bigger images go through Replicate's Files API


def _aspect(width: int, height: int) -> str:
    if width == height:
        return "1:1"
    return "9:16" if height > width else "16:9"


def _image_mime(image: bytes) -> str:
    if image[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if image[:4] == b"RIFF" and image[8:12] == b"WEBP":
        return "image/webp"
    return "image/png"


def build_model_input(
    model: str,
    *,
    prompt: str,
    image_ref: str | None,
    seed: int | None,
    duration_seconds: float,
    width: int,
    height: int,
    resolution: str,
) -> dict[str, Any]:
    """
    Each hosted video model names its inputs differently. The common
    families are mapped here; anything else gets {prompt, image, seed}
    and REPLICATE_VIDEO_INPUT_JSON can add/override any field.
    """
    name = model.split(":", 1)[0].lower()
    aspect = _aspect(width, height)

    if "seedance" in name:  # bytedance/seedance-1-lite, -1-pro
        data: dict[str, Any] = {
            "prompt": prompt,
            "duration": 5 if duration_seconds <= 5.5 else 10,
            "resolution": resolution,
            "aspect_ratio": aspect,
        }
        if image_ref:
            data["image"] = image_ref
    elif "kling" in name:  # kwaivgi/kling-v2.x
        data = {"prompt": prompt, "duration": 5 if duration_seconds <= 5.5 else 10, "aspect_ratio": aspect}
        if image_ref:
            data["start_image"] = image_ref
    elif "minimax" in name or "hailuo" in name:  # minimax/video-01, hailuo-02
        data = {"prompt": prompt}
        if image_ref:
            data["first_frame_image"] = image_ref
    else:  # wan-video/*, others: the most common names
        data = {"prompt": prompt}
        if image_ref:
            data["image"] = image_ref

    if seed is not None and "minimax" not in name and "hailuo" not in name:
        data["seed"] = int(seed) % 2_147_483_647

    extra = os.getenv("REPLICATE_VIDEO_INPUT_JSON")
    if extra:
        try:
            data.update(json.loads(extra))
        except json.JSONDecodeError as exc:
            raise ValueError("REPLICATE_VIDEO_INPUT_JSON is not valid JSON.") from exc
    return data


class ReplicateVideoProvider(VideoProvider):
    """
    Real AI video clips from a model hosted on Replicate (replicate.com).
    PAID, pay-per-use: you need REPLICATE_API_TOKEN, and every clip is
    billed by Replicate. Only the first candidate of each shot gets a
    clip (not all 3), which keeps a 30-second video to ~6 clips.

    Image-to-video when the shot has an image (so the clip matches the
    storyboard), text-to-video otherwise. The model is
    REPLICATE_VIDEO_MODEL (default bytedance/seedance-1-lite); official
    models are called by name, community models as "owner/name:version".

    A clip takes ~30 s to a few minutes, so this polls the prediction
    rather than relying on Replicate's 60 s synchronous wait.
    """

    name = "replicate"

    def __init__(
        self,
        api_token: str,
        model: str = "bytedance/seedance-1-lite",
        resolution: str = "480p",
        cost_per_clip_usd: float = 0.15,
        timeout: float = 900.0,
        poll_interval: float = 4.0,
    ) -> None:
        self.api_token = api_token
        self.model = model
        self.resolution = resolution
        self.cost_per_clip_usd = cost_per_clip_usd
        self.timeout = timeout
        self.poll_interval = poll_interval

    @property
    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_token}"}

    async def _image_ref(self, client: httpx.AsyncClient, image: bytes) -> str:
        mime = _image_mime(image)
        if len(image) <= DATA_URI_LIMIT:
            return f"data:{mime};base64,{base64.b64encode(image).decode()}"
        ext = mime.split("/")[1]
        response = await client.post(
            f"{API}/files",
            headers=self._headers,
            files={"content": (f"shot.{ext}", image, mime)},
        )
        _raise_for_status(response, "uploading the shot image")
        return response.json()["urls"]["get"]

    async def generate(
        self,
        prompt: str,
        *,
        width: int = 720,
        height: int = 1280,
        seed: int | None = None,
        duration_seconds: float = 5.0,
        image: bytes | None = None,
    ) -> bytes:
        async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
            try:
                image_ref = await self._image_ref(client, image) if image else None
                model_input = build_model_input(
                    self.model, prompt=prompt, image_ref=image_ref, seed=seed,
                    duration_seconds=duration_seconds, width=width, height=height,
                    resolution=self.resolution,
                )
                if ":" in self.model:
                    url, body = f"{API}/predictions", {
                        "version": self.model.split(":", 1)[1], "input": model_input,
                    }
                else:
                    url, body = f"{API}/models/{self.model}/predictions", {"input": model_input}

                response = await client.post(
                    url, headers={**self._headers, "Prefer": "wait=60"}, json=body,
                )
                _raise_for_status(response, f"starting {self.model}")
                prediction = response.json()
                prediction = await self._wait(client, prediction)
                video_url = _first_url(prediction.get("output"))
                if not video_url:
                    raise RuntimeError(f"Replicate {self.model} finished but returned no video URL.")
                video = await client.get(video_url)
                _raise_for_status(video, "downloading the clip")
                return video.content
            except httpx.ConnectError as exc:
                raise RuntimeError("Could not reach Replicate (api.replicate.com).") from exc

    async def _wait(self, client: httpx.AsyncClient, prediction: dict[str, Any]) -> dict[str, Any]:
        deadline = time.monotonic() + self.timeout
        while prediction.get("status") not in ("succeeded", "failed", "canceled"):
            if time.monotonic() > deadline:
                raise RuntimeError(
                    f"Replicate {self.model} did not finish within {self.timeout:.0f}s "
                    f"(prediction {prediction.get('id')})."
                )
            await asyncio.sleep(self.poll_interval)
            get_url = (prediction.get("urls") or {}).get("get") or f"{API}/predictions/{prediction['id']}"
            response = await client.get(get_url, headers=self._headers)
            _raise_for_status(response, "checking the prediction")
            prediction = response.json()
        if prediction["status"] != "succeeded":
            raise RuntimeError(f"Replicate {self.model} {prediction['status']}: {prediction.get('error')}")
        return prediction


def _first_url(output: Any) -> str | None:
    if isinstance(output, str):
        return output
    if isinstance(output, list):
        for item in output:
            found = _first_url(item)
            if found:
                return found
    if isinstance(output, dict):
        for key in ("video", "output", "url"):
            if key in output:
                return _first_url(output[key])
    return None


def _raise_for_status(response: httpx.Response, doing: str) -> None:
    if response.status_code < 400:
        return
    try:
        detail = response.json().get("detail") or response.text
    except ValueError:
        detail = response.text
    hint = ""
    if response.status_code in (401, 403):
        hint = " Check REPLICATE_API_TOKEN."
    elif response.status_code == 402:
        hint = " Add billing/credit on replicate.com."
    elif response.status_code == 422:
        hint = " The model rejected an input; adjust REPLICATE_VIDEO_INPUT_JSON for this model."
    raise RuntimeError(f"Replicate error {response.status_code} while {doing}: {detail}.{hint}")
