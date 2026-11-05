"""A stand-in backend that needs no GPU: colour pictures, short clips made with ffmpeg and tones for speech, sound
and music, with realistic progress and load times. For trying the GPU page, the router and Series, and for tests
(WORKER_MOCK=1)."""
from __future__ import annotations

import asyncio
import hashlib
import io
import math
import shutil
import struct
import wave
import tempfile
import zlib
from pathlib import Path

from worker import config
from worker.adapters.base import Adapter, JobSpec, Progress

MODELS = ["z-image", "qwen-image", "flux-schnell", "qwen-image-edit", "wan-2.2", "ltx-2.3", "wan-vace", "longcat-avatar",
          "infinitetalk", "wan-2.2-animate", "chatterbox", "indicf5", "indic-parler-tts", "hunyuan-foley", "ace-step"]
SPEECH = {"chatterbox", "indicf5", "indic-parler-tts"}


def wav(seconds: float, freq: float, rate: int = 24000) -> bytes:
    """A short tone (a stand-in voice / sound / music), 16-bit mono."""
    n = max(1, int(seconds * rate))
    frames = b"".join(struct.pack("<h", int(6000 * math.sin(2 * math.pi * freq * i / rate) * (0.6 + 0.4 * math.sin(i / 900))))
                      for i in range(n))
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(frames)
    return buf.getvalue()


def wav_seconds(data: bytes) -> float | None:
    try:
        with wave.open(io.BytesIO(data)) as w:
            return w.getnframes() / float(w.getframerate())
    except (wave.Error, EOFError):
        return None


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
        if job.want == "audio" or job.task in ("speech", "sound", "music"):
            if job.model in SPEECH or job.task == "speech":       # ~14 characters a second, like real speech
                secs = max(0.8, min(30.0, len(job.prompt or "") / 14))
                return wav(secs, 180 + h[3] % 120), "wav"
            if job.task == "sound" and job.inputs.get("video"):
                secs = job.seconds or 3.0
            else:
                secs = job.seconds or 8.0
            return wav(max(0.5, secs), 90 + h[3] % 400, rate=22050), "wav"
        w, hh = max(16, job.width // 8 * 2), max(16, job.height // 8 * 2)
        if job.want == "image" or job.task == "image":
            # the requested aspect ratio, at most 512 px on the long side (quick to make)
            k = min(1.0, 512 / max(job.width, job.height, 1))
            return png(max(16, int(job.width * k)), max(16, int(job.height * k)), rgb, gradient=True), "png"
        if job.inputs.get("audio") and job.task == "avatar":       # lip-sync: the clip lasts as long as the line
            job.seconds = wav_seconds(job.inputs["audio"]) or job.seconds
        if not shutil.which("ffmpeg"):
            return b"\x00\x00\x00\x18ftypmp42" + h * 4, "mp4"
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "clip.mp4"
            W2, H2 = w - w % 2, hh - hh % 2
            size = f"{W2}x{H2}"
            img = job.inputs.get("image") or b""
            if img[:8] == b"\x89PNG\r\n\x1a\n" or img[:3] == b"\xff\xd8\xff" or img[8:12] == b"WEBP":   # animate the given picture (a slow zoom), like an image-to-video model
                src = Path(tmp) / "in.img"
                src.write_bytes(job.inputs["image"])
                n = max(2, int(max(1.0, job.seconds) * (job.fps or 16)))
                args = ["-loop", "1", "-i", str(src), "-vf", f"scale={W2}:{H2}:force_original_aspect_ratio=increase,crop={W2}:{H2},"
                        f"zoompan=z='1+0.002*on':d={n}:s={size}:fps={job.fps or 16}", "-frames:v", str(n)]
            else:
                args = ["-f", "lavfi", "-i", f"color=c=0x{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}:s={size}:d={max(1.0, job.seconds):.2f}:r={job.fps or 16}"]
            proc = await asyncio.create_subprocess_exec(
                "ffmpeg", "-y", "-loglevel", "error", *args, "-pix_fmt", "yuv420p", "-c:v", "libx264", "-preset", "ultrafast", str(out))
            await proc.wait()
            if not out.is_file() or out.stat().st_size == 0:       # a picture ffmpeg can't read: plain colour
                proc = await asyncio.create_subprocess_exec(
                    "ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                    f"color=c=0x{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}:s={size}:d={max(1.0, job.seconds):.2f}:r={job.fps or 16}",
                    "-pix_fmt", "yuv420p", "-c:v", "libx264", "-preset", "ultrafast", str(out))
                await proc.wait()
            return out.read_bytes(), "mp4"

    async def cancel(self) -> None:
        self._cancel.set()
