"""What the picture is doing, per second: how much of it moves, hard cuts, and camera shake. Runs locally with ffmpeg + numpy, no AI.
A crash, a stunt or a kill shows up as a burst of change even when nobody speaks, which loudness alone cannot see.
Values are 0..1 by rank against this video's own normal, so a calm video does not look exciting."""
from __future__ import annotations

import subprocess
from typing import Any

from .. import config

W, H, FPS = 64, 36, 4


def frames(path: str, start: float = 0.0, end: float | None = None):
    """Yield tiny grey frames (numpy H x W uint8) at FPS from `start` to `end`."""
    import numpy as np
    cmd = [config.ffmpeg(), "-v", "error", "-nostdin"]
    if start:
        cmd += ["-ss", f"{start:.2f}"]
    cmd += ["-i", path]
    if end:
        cmd += ["-t", f"{max(1.0, end - start):.2f}"]
    cmd += ["-an", "-vf", f"fps={FPS},scale={W}:{H}", "-pix_fmt", "gray", "-f", "rawvideo", "-"]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    n = W * H
    try:
        while True:
            b = p.stdout.read(n)  # type: ignore[union-attr]
            if len(b) < n:
                break
            yield np.frombuffer(b, dtype=np.uint8).reshape(H, W)
    finally:
        p.kill()


def _rank(v: list[float]) -> list[float]:
    """0..1 against the video's own typical level: median -> 0, 95th percentile -> 1."""
    if not v:
        return []
    s = sorted(v)
    med, p95 = s[len(s) // 2], s[min(len(s) - 1, int(len(s) * 0.95))]
    span = max(p95 - med, 1e-6)
    return [max(0.0, min(1.0, (x - med) / span)) for x in v]


def scan(path: str, start: float = 0.0, end: float | None = None, max_minutes: int = 90, region: tuple[float, float, float, float] | None = None) -> dict[str, Any] | None:
    """{"motion": [...], "cut": [...], "shake": [...], "react": [...]|None, "hype": [...]} per second from `start`; None when too long, too short or it fails.
    `region` (x, y, w, h as 0..1 fractions) measures the streamer's cam separately as "react"."""
    try:
        import numpy as np
    except Exception:  # noqa: BLE001
        return None
    if end is not None and (end - start) > max_minutes * 60:
        return None
    diffs, cuts, shakes, reacts = [], [], [], []
    prev = None
    ry = rx = None
    if region:
        x, y, w, h = region
        rx, ry = slice(int(x * W), max(int(x * W) + 2, int((x + w) * W))), slice(int(y * H), max(int(y * H) + 2, int((y + h) * H)))
    try:
        for f in frames(path, start, end):
            g = f.astype(np.int16)
            if prev is not None:
                d = np.abs(g - prev)
                diffs.append(float(d.mean()))
                cuts.append(float((d > 40).mean()))                      # most pixels changed at once = a hard cut or a flash
                top, bot = np.abs(g[: H // 2].mean() - prev[: H // 2].mean()), np.abs(g[H // 2:].mean() - prev[H // 2:].mean())
                shakes.append(float(abs(top - bot) + d.mean() * 0.3))
                if region:
                    reacts.append(float(d[ry, rx].mean()))
            prev = g
    except Exception:  # noqa: BLE001
        return None
    if len(diffs) < FPS * 3:
        return None
    n = len(diffs) // FPS
    per = lambda v: [max(v[i * FPS:(i + 1) * FPS]) for i in range(n)]       # noqa: E731 - the strongest quarter-second of each second
    motion, cut, shake = _rank(per(diffs)), _rank(per(cuts)), _rank(per(shakes))
    react = _rank(per(reacts)) if reacts else None
    hype = [min(1.0, 0.55 * motion[i] + 0.25 * cut[i] + 0.2 * shake[i]) for i in range(n)]
    if react:
        hype = [min(1.0, 0.8 * hype[i] + 0.35 * react[i]) for i in range(n)]
    return {"motion": motion, "cut": cut, "shake": shake, "react": react, "hype": hype}
