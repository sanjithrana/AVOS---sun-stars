"""A stand-in backend that needs no GPU: solid-colour pictures and short clips made with ffmpeg, with realistic
progress and load times. For trying the GPU page and the router, and for tests (WORKER_MOCK=1)."""
from __future__ import annotations

import asyncio
import hashlib
import shutil
import struct
import tempfile
import zlib
from pathlib import Path

from worker import config
from worker.adapters.base import Adapter, JobSpec, Progress

MODELS = ["z-image", "qwen-image", "flux-schnell", "wan-2.2", "ltx-2.3", "wan-vace", "longcat-avatar", "infinitetalk",
          "wan-2.2-animate"]


def png(width: int, height: int, rgb: tuple[int, int, int], gradient: bool = False) -> bytes:
    if gradient:   # a colour wash, so the stand-in passes AVOS's "not a blank frame" check like a real picture
        rows = []
        for y in range(height):
            g = (rgb[1] + 160 * y // max(1, height - 1)) % 256
            rows.append(b"\x00" + b"".join(bytes(((rgb[0] + 200 * x // max(1, width - 1)) % 256, g, rgb[2]))
                                          for x in range(width)))
        raw = b"".join(rows)
    else:
        raw = b"".join(b"\x00" + bytes(rgb) * width for _ in range(height))

    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)) + \
        chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b"")


class MockAdapter(Adapter):
    name = "mock"
    precisions = ("bf16", "fp8", "int8", "fp4", "int4")
    attentions = ("sage2", "sage", "flash", "sdpa")

    def __init__(self) -> None:
        self._cancel = asyncio.Event()

    async def ready(self) -> tuple[bool, str | None]:
        return True, None

    def models(self) -> list[str]:
        return list(MODELS)

    async def load(self, job: JobSpec, progress: Progress) -> None:
        await progress(0.0, f"loading {job.model} ({job.precision})")
        await asyncio.sleep(min(0.5, config.MOCK_SECONDS / 3))

    async def run(self, job: JobSpec, progress: Progress) -> tuple[bytes, str]:
        self._cancel.clear()
        steps = 6
        for i in range(steps):
            if self._cancel.is_set():
                raise asyncio.CancelledError()
            await progress(i / steps, f"sampling {i + 1}/{steps}")
            await asyncio.sleep(config.MOCK_SECONDS / steps)
        h = hashlib.sha256(f"{job.model}:{job.prompt}:{job.seed}".encode()).digest()
        rgb = (h[0], h[1], h[2])
        w, hh = max(16, job.width // 8 * 2), max(16, job.height // 8 * 2)
        if job.want == "image" or job.task == "image":
            # the requested aspect ratio, at most 512 px on the long side (quick to make)
            k = min(1.0, 512 / max(job.width, job.height, 1))
            return png(max(16, int(job.width * k)), max(16, int(job.height * k)), rgb, gradient=True), "png"
        if not shutil.which("ffmpeg"):
            return b"\x00\x00\x00\x18ftypmp42" + h * 4, "mp4"
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "clip.mp4"
            color = "0x%02x%02x%02x" % rgb
            proc = await asyncio.create_subprocess_exec(
                "ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                f"color=c={color}:s={w - w % 2}x{hh - hh % 2}:d={max(1.0, job.seconds):.2f}:r={job.fps or 16}",
                "-pix_fmt", "yuv420p", "-c:v", "libx264", "-preset", "ultrafast", str(out))
            await proc.wait()
            return out.read_bytes(), "mp4"

    async def cancel(self) -> None:
        self._cancel.set()
