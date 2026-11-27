import asyncio
import copy
import json
import math
import time
import uuid
from pathlib import Path
from typing import Any

import httpx

from agentic_core.models.video.base import VideoProvider

VIDEO_EXTS = (".mp4", ".webm", ".mov", ".mkv", ".gif", ".webp")
IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".webp")

# Placeholders you type into the workflow (API format) before exporting.
# A field whose whole value is one of the numeric placeholders becomes a
# number; {{PROMPT}} / {{NEGATIVE_PROMPT}} may also sit inside longer text.
NUMERIC = ("{{SEED}}", "{{WIDTH}}", "{{HEIGHT}}", "{{FRAMES}}", "{{FPS}}", "{{DURATION}}", "{{STEPS}}")
# Input files: uploaded to ComfyUI's input folder, the field gets the file name.
#   {{IMAGE}} LoadImage   {{AUDIO}} LoadAudio   {{VIDEO}} VHS_LoadVideo / LoadVideo
FILES = ("{{IMAGE}}", "{{AUDIO}}", "{{VIDEO}}")
FILE_EXT = {"{{IMAGE}}": "png", "{{AUDIO}}": "wav", "{{VIDEO}}": "mp4"}


def frame_count(duration_seconds: float, fps: int, multiple: int, max_frames: int) -> int:
    """Video models want specific lengths: LTX-Video 8k+1, Wan 4k+1."""
    wanted = max(1, round(duration_seconds * fps))
    k = max(1, math.ceil((wanted - 1) / multiple))
    frames = k * multiple + 1
    while frames > max_frames and k > 1:
        k -= 1
        frames = k * multiple + 1
    return frames


def fill_placeholders(node: Any, values: dict[str, Any]) -> Any:
    if isinstance(node, dict):
        return {k: fill_placeholders(v, values) for k, v in node.items()}
    if isinstance(node, list):
        return [fill_placeholders(v, values) for v in node]
    if isinstance(node, str):
        stripped = node.strip()
        if stripped in values and stripped in NUMERIC:
            return values[stripped]
        if stripped in FILES:
            return values.get(stripped, "")
        out = node
        for key in ("{{PROMPT}}", "{{NEGATIVE_PROMPT}}"):
            out = out.replace(key, str(values.get(key, "")))
        return out
    return node


class ComfyUIVideoProvider(VideoProvider):
    """
    Free AI video on your own GPU through a running ComfyUI server
    (github.com/comfyanonymous/ComfyUI) and ITS native API - no wrapper
    service needed.

    You supply the workflow: open one of ComfyUI's built-in video
    templates (Workflow -> Browse Templates -> Video, e.g. "LTXV Image to
    Video" or "Wan 2.2 Image to Video"), check it runs, then type these
    placeholders into its fields and use Workflow -> Export (API):

        {{PROMPT}}  positive prompt text     {{IMAGE}}  LoadImage's image
        {{SEED}}    sampler seed             {{FRAMES}} length / frame count
        {{WIDTH}} {{HEIGHT}} {{FPS}} {{NEGATIVE_PROMPT}} (optional)

    Save it where COMFYUI_WORKFLOW points (default
    /app/comfyui_workflows/video.json, i.e. apps/comfyui_workflows/ on
    your machine). End the workflow with a node that saves MP4/WebM
    (core "Save Video", or VideoHelperSuite "Video Combine").
    """

    name = "comfyui"
    cost_per_clip_usd = 0.0

    def __init__(
        self,
        base_url: str,
        workflow_path: str,
        *,
        fps: int = 24,
        frame_multiple: int = 8,
        max_frames: int = 121,
        negative_prompt: str = "blurry, low quality, distorted, watermark, text",
        timeout: float = 1800.0,
        poll_interval: float = 3.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.workflow_path = workflow_path
        self.fps = fps
        self.frame_multiple = frame_multiple
        self.max_frames = max_frames
        self.negative_prompt = negative_prompt
        self.timeout = timeout
        self.poll_interval = poll_interval

    def _load_workflow(self) -> dict[str, Any]:
        path = Path(self.workflow_path)
        if not path.is_file():
            raise RuntimeError(
                f"ComfyUI workflow not found at {path}. Export your video workflow from ComfyUI "
                "with Workflow -> Export (API) and save it there (see apps/comfyui_workflows/README.md)."
            )
        data = json.loads(path.read_text(encoding="utf-8"))
        if "nodes" in data and "links" in data:
            raise RuntimeError(
                f"{path} is a regular ComfyUI save, not the API format. Use Workflow -> Export (API)."
            )
        return data

    async def generate(
        self,
        prompt: str,
        *,
        width: int = 512,
        height: int = 896,
        seed: int | None = None,
        duration_seconds: float = 4.0,
        image: bytes | None = None,
    ) -> bytes:
        return await self.run(prompt, width=width, height=height, seed=seed,
                              duration_seconds=duration_seconds, files={"{{IMAGE}}": image})

    async def run(
        self,
        prompt: str,
        *,
        width: int = 512,
        height: int = 896,
        seed: int | None = None,
        duration_seconds: float = 4.0,
        files: dict[str, bytes | None] | None = None,
        steps: int | None = None,
        want: str = "video",
    ) -> bytes:
        """Queue the workflow with these values and input files, return the first saved video (or image)."""
        workflow = self._load_workflow()
        text = json.dumps(workflow)
        files = files or {}
        for ph in FILES:
            if ph in text and not files.get(ph):
                what = {"{{IMAGE}}": "an input image", "{{AUDIO}}": "an audio track",
                        "{{VIDEO}}": "a driving video"}[ph]
                raise RuntimeError(
                    f"The ComfyUI workflow {Path(self.workflow_path).name} expects {what} ({ph}) but none was given. "
                    + ("Pick an image provider for the project, or use a text-to-video workflow."
                       if ph == "{{IMAGE}}" else "")
                )

        async with httpx.AsyncClient(timeout=120.0) as client:
            try:
                names = {ph: await self._upload(client, data, FILE_EXT[ph])
                         for ph, data in files.items() if data and ph in text}
                values = {
                    "{{PROMPT}}": prompt,
                    "{{NEGATIVE_PROMPT}}": self.negative_prompt,
                    "{{SEED}}": int(seed if seed is not None else time.time()) % 2_147_483_647,
                    "{{WIDTH}}": width - width % 32,
                    "{{HEIGHT}}": height - height % 32,
                    "{{FRAMES}}": frame_count(duration_seconds, self.fps, self.frame_multiple, self.max_frames),
                    "{{FPS}}": self.fps,
                    "{{DURATION}}": round(duration_seconds, 2),
                    "{{STEPS}}": int(steps or 20),
                    **names,
                }
                graph = fill_placeholders(copy.deepcopy(workflow), values)
                response = await client.post(
                    f"{self.base_url}/prompt",
                    json={"prompt": graph, "client_id": str(uuid.uuid4())},
                )
                if response.status_code >= 400:
                    raise RuntimeError(f"ComfyUI rejected the workflow: {response.text[:800]}")
                prompt_id = response.json()["prompt_id"]
                outputs = await self._wait(client, prompt_id)
                if want == "image":
                    return await self._download_image(client, outputs)
                return await self._download_video(client, outputs)
            except httpx.ConnectError as exc:
                raise RuntimeError(
                    f"Could not reach ComfyUI at {self.base_url}. Start ComfyUI (with --listen if it "
                    "runs on another machine) and set COMFYUI_URL; from Docker on the same PC use "
                    "http://host.docker.internal:8188."
                ) from exc

    async def _upload(self, client: httpx.AsyncClient, data: bytes, ext: str = "png") -> str:
        """ComfyUI's /upload/image stores any file in its input folder (LoadAudio and the video loaders read from there too)."""
        if ext == "png" and data[:3] == b"\xff\xd8\xff":
            ext = "jpg"
        if ext == "wav" and (data[:3] == b"ID3" or data[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2")):
            ext = "mp3"
        filename = f"avos_{uuid.uuid4().hex[:12]}.{ext}"
        response = await client.post(
            f"{self.base_url}/upload/image",
            files={"image": (filename, data, "application/octet-stream")},
            data={"overwrite": "true"},
        )
        if response.status_code >= 400:
            raise RuntimeError(f"ComfyUI upload of {filename} failed: {response.text[:300]}")
        info = response.json()
        return f"{info['subfolder']}/{info['name']}" if info.get("subfolder") else info["name"]

    async def _wait(self, client: httpx.AsyncClient, prompt_id: str) -> dict[str, Any]:
        deadline = time.monotonic() + self.timeout
        while True:
            response = await client.get(f"{self.base_url}/history/{prompt_id}")
            if response.status_code == 200:
                entry = response.json().get(prompt_id)
                if entry:
                    status = entry.get("status") or {}
                    if status.get("status_str") == "error":
                        messages = [m for m in status.get("messages", []) if m and m[0] == "execution_error"]
                        detail = messages[-1][1].get("exception_message") if messages else "unknown error"
                        raise RuntimeError(f"ComfyUI workflow failed: {detail}")
                    if status.get("completed", True):
                        return entry.get("outputs") or {}
            if time.monotonic() > deadline:
                raise RuntimeError(f"ComfyUI did not finish within {self.timeout:.0f}s (prompt {prompt_id}).")
            await asyncio.sleep(self.poll_interval)

    @staticmethod
    def _files(outputs: dict[str, Any]) -> list[dict[str, Any]]:
        files: list[dict[str, Any]] = []
        for node_output in outputs.values():
            for items in node_output.values():
                if isinstance(items, list):
                    files.extend(i for i in items if isinstance(i, dict) and "filename" in i)
        return files

    async def _view(self, client: httpx.AsyncClient, f: dict[str, Any]) -> bytes:
        response = await client.get(
            f"{self.base_url}/view",
            params={"filename": f["filename"], "subfolder": f.get("subfolder", ""), "type": f.get("type", "output")},
        )
        if response.status_code >= 400:
            raise RuntimeError(f"Could not download {f['filename']} from ComfyUI.")
        return response.content

    async def _download_image(self, client: httpx.AsyncClient, outputs: dict[str, Any]) -> bytes:
        images = [f for f in self._files(outputs) if f["filename"].lower().endswith(IMAGE_EXTS)
                  and f.get("type", "output") == "output"]
        if not images:
            raise RuntimeError("ComfyUI finished but saved no image. End the workflow with 'Save Image'.")
        return await self._view(client, images[0])

    async def _download_video(self, client: httpx.AsyncClient, outputs: dict[str, Any]) -> bytes:
        files: list[dict[str, Any]] = []
        for node_output in outputs.values():
            for items in node_output.values():
                if isinstance(items, list):
                    files.extend(i for i in items if isinstance(i, dict) and "filename" in i)
        videos = [f for f in files if f["filename"].lower().endswith(VIDEO_EXTS)]
        if not videos:
            raise RuntimeError(
                "ComfyUI finished but saved no video. End the workflow with 'Save Video' (MP4) "
                "or VideoHelperSuite 'Video Combine'."
            )
        videos.sort(key=lambda f: 0 if f["filename"].lower().endswith((".mp4", ".webm", ".mov")) else 1)
        chosen = videos[0]
        if chosen["filename"].lower().endswith(".webp"):
            raise RuntimeError(
                "ComfyUI saved an animated WebP, which ffmpeg can't read. Replace 'Save Animated "
                "WEBP' with 'Save Video' (MP4) in the workflow."
            )
        response = await client.get(
            f"{self.base_url}/view",
            params={
                "filename": chosen["filename"],
                "subfolder": chosen.get("subfolder", ""),
                "type": chosen.get("type", "output"),
            },
        )
        if response.status_code >= 400:
            raise RuntimeError(f"Could not download {chosen['filename']} from ComfyUI.")
        return response.content
