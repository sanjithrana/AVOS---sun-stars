"""
Thin async wrappers around the ffmpeg / ffprobe binaries.

ffmpeg is installed in the api/worker image (api/Dockerfile). Every call
runs in a subprocess so the event loop is never blocked, and errors
carry the tail of ffmpeg's stderr - the only place ffmpeg says what went
wrong.
"""

import asyncio
import json
import os
import shutil
import tempfile
from collections.abc import Sequence
from pathlib import Path


class FFmpegError(RuntimeError):
    """ffmpeg/ffprobe is missing or exited non-zero."""


def ffmpeg_binary() -> str:
    path = os.getenv("FFMPEG_BINARY") or shutil.which("ffmpeg")
    if not path:
        raise FFmpegError(
            "ffmpeg is not installed. It ships in the api/worker Docker image; "
            "rebuild with `docker compose up -d --build`."
        )
    return path


def ffprobe_binary() -> str:
    path = os.getenv("FFPROBE_BINARY") or shutil.which("ffprobe")
    if not path:
        raise FFmpegError("ffprobe is not installed (it comes with ffmpeg).")
    return path


async def _run(cmd: Sequence[str], *, timeout: float) -> bytes:
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError as exc:
        proc.kill()
        await proc.wait()
        raise FFmpegError(f"{Path(cmd[0]).name} timed out after {timeout:.0f}s.") from exc
    if proc.returncode != 0:
        tail = stderr.decode("utf-8", "replace").strip().splitlines()[-12:]
        raise FFmpegError(
            f"{Path(cmd[0]).name} exited with code {proc.returncode}:\n" + "\n".join(tail)
        )
    return stdout


async def run_ffmpeg(args: Sequence[str], *, timeout: float = 600.0) -> None:
    """Run ffmpeg with the given arguments (no leading 'ffmpeg')."""
    await _run([ffmpeg_binary(), "-hide_banner", "-loglevel", "error", "-y", *args], timeout=timeout)


async def probe_duration(path: str | Path, *, timeout: float = 60.0) -> float:
    """Duration in seconds of any media file ffprobe can read."""
    out = await _run(
        [
            ffprobe_binary(), "-v", "error", "-show_entries", "format=duration",
            "-of", "json", str(path),
        ],
        timeout=timeout,
    )
    try:
        return float(json.loads(out)["format"]["duration"])
    except (KeyError, ValueError, TypeError) as exc:
        raise FFmpegError(f"ffprobe could not read a duration from {path}.") from exc


async def probe_duration_bytes(data: bytes, suffix: str) -> float:
    """Duration of in-memory media (written to a temp file for ffprobe)."""
    with tempfile.TemporaryDirectory(prefix="avos-probe-") as tmp:
        path = Path(tmp) / f"media.{suffix.lstrip('.')}"
        path.write_bytes(data)
        return await probe_duration(path)


def sniff_video_ext(data: bytes) -> str:
    """Best-effort container detection for clips returned by providers
    (they don't always say what they sent)."""
    if len(data) >= 12 and data[4:8] == b"ftyp":
        return "mp4"
    if data[:4] == b"\x1a\x45\xdf\xa3":
        return "webm"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return "mp4"
