"""Motion graphics drawn in Python: a line graph, minimal line art, a map route and an exploded breakdown.

These are the four quick animation skills from github.com/artemnovitckii/claude-animation-skills (MIT, Artem Novitckii),
rewritten here with Pillow and ffmpeg instead of three.js, GSAP and a headless browser, so they need nothing that the
studio container does not already have: no Node, no npx, no Chromium.

Everything is drawn at SS times the final size and shrunk at the end, which is what gives the edges their smoothness
without a real antialiasing pass. Frames go straight down a pipe into ffmpeg, so nothing is written to disk per frame.
"""
from __future__ import annotations

import math
import subprocess
from pathlib import Path
from typing import Any, Callable, Iterator

from PIL import Image, ImageDraw, ImageFont

FPS = 30
SS = 2                                     # supersample factor
SAFE_TOP, SAFE_BOTTOM = 0.115, 0.78        # Instagram covers the top ~11% and everything below ~78%

INK = (17, 17, 19)
PAPER = (250, 250, 248)
ACCENT = (232, 72, 62)


# ---------------------------------------------------------------- easing
def ease(t: float) -> float:
    """Slow in, slow out. The move that makes code-drawn motion look designed rather than linear."""
    t = min(1.0, max(0.0, t))
    return t * t * (3 - 2 * t)


def ease_out(t: float) -> float:
    t = min(1.0, max(0.0, t))
    return 1 - (1 - t) ** 3


def spring(t: float) -> float:
    """Overshoots once and settles: for anything that lands."""
    t = min(1.0, max(0.0, t))
    return 1 - math.cos(t * math.pi * 1.6) * math.exp(-4.2 * t)


def seg(t: float, a: float, b: float) -> float:
    """Where t sits inside the window a..b, as 0..1."""
    return 0.0 if b <= a else min(1.0, max(0.0, (t - a) / (b - a)))


# ---------------------------------------------------------------- text
_FONTS = ("DejaVuSans-Bold.ttf", "DejaVuSans.ttf")


def font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
    for name in (_FONTS if bold else _FONTS[::-1]):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default(size)


def text(d: ImageDraw.ImageDraw, xy, s: str, size: int, fill, anchor: str = "mm", bold: bool = True, spacing: float = 0.0):
    f = font(size, bold)
    if not spacing:
        d.text(xy, s, font=f, fill=fill, anchor=anchor)
        return
    widths = [d.textlength(c, font=f) for c in s]
    total = sum(widths) + spacing * max(0, len(s) - 1)
    x = xy[0] - total / 2 if anchor[0] == "m" else (xy[0] - total if anchor[0] == "r" else xy[0])
    for c, w in zip(s, widths):
        d.text((x, xy[1]), c, font=f, fill=fill, anchor="l" + anchor[1])
        x += w + spacing


def fit(d: ImageDraw.ImageDraw, s: str, size: int, width: float, bold: bool = True) -> int:
    """The biggest size at or below `size` that keeps `s` inside `width`."""
    while size > 8 and d.textlength(s, font=font(size, bold)) > width:
        size -= 2
    return size


def wrap(d: ImageDraw.ImageDraw, s: str, size: int, width: float, bold: bool = False) -> list[str]:
    f, out, line = font(size, bold), [], ""
    for w in s.split():
        trial = f"{line} {w}".strip()
        if d.textlength(trial, font=f) <= width or not line:
            line = trial
        else:
            out.append(line)
            line = w
    return out + ([line] if line else [])


def number(v: float, decimals: int = 0, prefix: str = "", suffix: str = "") -> str:
    """1200 -> 1.2K, 1_200_000 -> 1.2M, so a counter never runs out of frame."""
    n, unit = float(v), ""
    for cut, u in ((1e9, "B"), (1e6, "M"), (1e3, "K")):
        if abs(n) >= cut:
            n, unit, decimals = n / cut, u, max(decimals, 1 if abs(n / cut) < 100 else 0)
            break
    s = f"{n:,.{decimals}f}".rstrip("0").rstrip(".") if decimals else f"{n:,.0f}"
    return f"{prefix}{s}{unit}{suffix}"


# ---------------------------------------------------------------- geometry
def smooth(points: list[tuple[float, float]], per: int = 14) -> list[tuple[float, float]]:
    """A Catmull-Rom spline through the points, so the line curves instead of bending."""
    if len(points) < 3:
        return list(points)
    pts = [points[0]] + list(points) + [points[-1]]
    out: list[tuple[float, float]] = []
    for i in range(len(pts) - 3):
        p0, p1, p2, p3 = pts[i], pts[i + 1], pts[i + 2], pts[i + 3]
        for j in range(per):
            t = j / per
            t2, t3 = t * t, t * t * t
            out.append((0.5 * ((2 * p1[0]) + (-p0[0] + p2[0]) * t + (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2 + (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3),
                        0.5 * ((2 * p1[1]) + (-p0[1] + p2[1]) * t + (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2 + (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3)))
    out.append(points[-1])
    return out


def along(path: list[tuple[float, float]], frac: float) -> list[tuple[float, float]]:
    """The first `frac` of a path, cut mid-segment so a line can draw itself smoothly."""
    if frac <= 0 or len(path) < 2:
        return path[:1]
    if frac >= 1:
        return list(path)
    lens = [math.dist(path[i], path[i + 1]) for i in range(len(path) - 1)]
    want, run = sum(lens) * frac, 0.0
    out = [path[0]]
    for i, ln in enumerate(lens):
        if run + ln >= want:
            k = (want - run) / ln if ln else 0
            out.append((path[i][0] + (path[i + 1][0] - path[i][0]) * k, path[i][1] + (path[i + 1][1] - path[i][1]) * k))
            return out
        run += ln
        out.append(path[i + 1])
    return out


def iso(x: float, y: float, z: float, ox: float, oy: float, scale: float) -> tuple[float, float]:
    """Isometric projection: a 3D look without a 3D engine."""
    return ox + (x - y) * 0.866 * scale, oy + ((x + y) * 0.5 - z) * scale


def card(d: ImageDraw.ImageDraw, box, radius: int, fill, shadow: int = 0, outline=None, width: int = 0):
    if shadow:
        d.rounded_rectangle([box[0] + shadow * 0.3, box[1] + shadow, box[2] + shadow * 0.3, box[3] + shadow],
                            radius, fill=(0, 0, 0, 40) if len(fill) == 4 else (210, 208, 203))
    d.rounded_rectangle(box, radius, fill=fill, outline=outline, width=width)


# ---------------------------------------------------------------- encoding
def encode(frames: Iterator[Image.Image], out: Path, w: int, h: int, ffmpeg: str = "ffmpeg", audio: Path | None = None) -> Path:
    """Frames straight down a pipe into H.264. veryfast because a slower preset keeps the person waiting for no visible gain."""
    cmd = [ffmpeg, "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}", "-r", str(FPS), "-i", "-"]
    if audio:
        cmd += ["-i", str(audio), "-c:a", "aac", "-b:a", "128k", "-shortest"]
    cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out)]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    assert p.stdin
    n = 0
    for im in frames:
        if im.size != (w, h):
            im = im.resize((w, h), Image.LANCZOS)
        p.stdin.write(im.convert("RGB").tobytes())
        n += 1
    p.stdin.close()
    if p.wait() != 0 or not out.is_file():
        raise RuntimeError("ffmpeg could not write the video")
    return out


def frames_of(seconds: float, draw: Callable[[float, ImageDraw.ImageDraw, Image.Image], None], w: int, h: int, bg) -> Iterator[Image.Image]:
    """Calls `draw(t, d, im)` once per frame on a fresh canvas at SS times size, and yields the shrunk frame."""
    W, H = w * SS, h * SS
    total = max(1, round(seconds * FPS))
    for i in range(total):
        im = Image.new("RGB", (W, H), bg)
        d = ImageDraw.Draw(im, "RGBA")
        draw(i / FPS, d, im)
        yield im.resize((w, h), Image.LANCZOS)
