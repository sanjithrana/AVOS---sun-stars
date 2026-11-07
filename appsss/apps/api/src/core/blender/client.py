"""
Blender stage client (Week 3 Day 12, physics-before-pixels).

The Blender stage turns a ShotSpec into a *physics proxy*: a simple 3D
layout of the shot, rendered into control passes that later condition
image/video generation (ComfyUI):

    depth   - distance from camera (grayscale)
    normal  - surface orientation (RGB)
    canny   - edge map (grayscale)
    mask    - subject mask (grayscale)

Two implementations behind one interface:

- MockBlenderClient (default): deterministic, CPU-only. Produces real,
  valid PNGs whose pixels are seeded from the ShotSpec content hash, so
  the same ShotSpec always yields the same bytes (cache-friendly) and
  different shots never collide. Every result is tagged renderer=MOCK and
  logged with a [MOCK] prefix - nothing downstream can mistake it for a
  real render.
- HttpBlenderClient: posts the ShotSpec to a headless Blender service
  (set BLENDER_SERVICE_URL). Expected response:
      {"renderer": "...", "width": W, "height": H,
       "passes": {"depth": "<base64 png>", "normal": ..., "canny": ..., "mask": ...},
       "scene": {...}}
"""

import base64
import hashlib
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx

from src.core.blender.png import encode_png

logger = logging.getLogger(__name__)

PASS_NAMES = ("depth", "normal", "canny", "mask")

# Proxy render resolution per aspect ratio (control passes don't need
# final resolution; generation upsamples).
RESOLUTIONS = {"9:16": (144, 256), "16:9": (256, 144), "1:1": (192, 192)}


@dataclass(frozen=True)
class BlenderRequest:
    project_id: str
    shot_id: str
    shotspec_id: str
    version: int
    content_hash: str
    aspect_ratio: str
    content: dict[str, Any]


@dataclass
class BlenderResult:
    renderer: str
    width: int
    height: int
    passes: dict[str, bytes]
    scene: dict[str, Any] = field(default_factory=dict)

    @property
    def is_mock(self) -> bool:
        return self.renderer == "MOCK"


class BlenderClient(Protocol):
    async def render_proxy(self, request: BlenderRequest) -> BlenderResult: ...


class MockBlenderClient:
    renderer = "MOCK"

    async def render_proxy(self, request: BlenderRequest) -> BlenderResult:
        width, height = RESOLUTIONS.get(request.aspect_ratio, RESOLUTIONS["9:16"])
        seed = int(hashlib.sha256(request.content_hash.encode()).hexdigest()[:8], 16)
        shot_type = request.content.get("camera", {}).get("shot_type", "medium")

        # Subject box grows with tighter framing.
        scale = {"wide": 0.3, "medium": 0.5, "close_up": 0.75, "insert": 0.6}.get(shot_type, 0.5)
        box_w, box_h = int(width * scale), int(height * scale)
        x0 = (width - box_w) // 2 + (seed % 9) - 4
        y0 = (height - box_h) // 2 + (seed // 9 % 9) - 4
        x1, y1 = x0 + box_w, y0 + box_h

        def inside(x: int, y: int) -> bool:
            return x0 <= x < x1 and y0 <= y < y1

        depth, normal, canny, mask = [], [], [], []
        for y in range(height):
            d_row, n_row, c_row, m_row = bytearray(), bytearray(), bytearray(), bytearray()
            floor = int(40 + 180 * y / max(1, height - 1))  # nearer toward the bottom
            for x in range(width):
                subject = inside(x, y)
                d_row.append(230 if subject else floor)
                if subject:
                    n_row += bytes(((x - x0) * 255 // max(1, box_w), (y - y0) * 255 // max(1, box_h), 230))
                else:
                    n_row += bytes((128, 200, 128))  # floor facing up
                # 2px lines so the edges survive thumbnail downscaling.
                edge = subject and (x - x0 < 2 or x1 - 1 - x < 2 or y - y0 < 2 or y1 - 1 - y < 2)
                horizon = 0 <= y - height * 2 // 3 < 2 and not subject
                c_row.append(255 if edge or horizon else 0)  # subject outline + horizon
                m_row.append(255 if subject else 0)
            depth.append(bytes(d_row))
            normal.append(bytes(n_row))
            canny.append(bytes(c_row))
            mask.append(bytes(m_row))

        # tEXt makes every pass self-describing and unique per ShotSpec
        # version, so content-addressed storage never merges two shots.
        def meta(name: str) -> dict[str, str]:
            return {"avos:pass": name, "avos:renderer": "MOCK", "avos:shotspec_id": request.shotspec_id}

        passes = {
            "depth": encode_png(width, height, depth, channels=1, text=meta("depth")),
            "normal": encode_png(width, height, normal, channels=3, text=meta("normal")),
            "canny": encode_png(width, height, canny, channels=1, text=meta("canny")),
            "mask": encode_png(width, height, mask, channels=1, text=meta("mask")),
        }
        scene = {
            "camera": request.content.get("camera", {}),
            "subject_box": [x0, y0, x1, y1],
            "environment": request.content.get("environment", {}),
            "requires_physics": request.content.get("requires_physics", False),
        }

        logger.warning(
            "[MOCK] Blender stage: generated placeholder depth/normal/canny/mask for shot %s v%s "
            "(%dx%d). Set BLENDER_SERVICE_URL to use a real headless Blender service.",
            request.shot_id, request.version, width, height,
        )
        return BlenderResult(renderer="MOCK", width=width, height=height, passes=passes, scene=scene)


class HttpBlenderClient:
    def __init__(self, base_url: str, timeout: float = 300.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    async def render_proxy(self, request: BlenderRequest) -> BlenderResult:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/render",
                json={
                    "project_id": request.project_id,
                    "shot_id": request.shot_id,
                    "shotspec_id": request.shotspec_id,
                    "version": request.version,
                    "aspect_ratio": request.aspect_ratio,
                    "content": request.content,
                    "passes": list(PASS_NAMES),
                },
            )
        response.raise_for_status()
        data = response.json()
        missing = [p for p in PASS_NAMES if p not in data.get("passes", {})]
        if missing:
            raise ValueError(f"Blender service response missing passes: {missing}")
        return BlenderResult(
            renderer=str(data.get("renderer", "blender")),
            width=int(data["width"]),
            height=int(data["height"]),
            passes={name: base64.b64decode(data["passes"][name]) for name in PASS_NAMES},
            scene=data.get("scene", {}),
        )


def get_blender_client() -> BlenderClient:
    url = os.getenv("BLENDER_SERVICE_URL")
    return HttpBlenderClient(url) if url else MockBlenderClient()
