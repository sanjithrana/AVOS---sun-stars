"""Screen-space effects (particles, weather, anime speed lines) and frame post-processing per engine."""
from __future__ import annotations

import functools
import math
import random

import numpy as np
import skia

from .color import parse, skc
from .rig import _heart, _star

FX = ("sparkles", "confetti", "hearts", "rain", "snow", "petals", "bubbles", "speedlines", "focuslines", "sunrays", "bokeh",
      "stars", "notes", "dust", "glow")
FX_WORDS = {"rain": r"\brain(?!bow|coat)|\braining\b|\brainy\b|下雨|雨天|大雨", "snow": r"\bsnow|雪", "hearts": r"\blove|romance|愛|\bhearts?\b|心動|\bcrush",
            "confetti": r"\bparty|celebrat|birthday|慶|派對|生日|\bwins?\b|\bwinner|victory", "sparkles": r"\bmagic|sparkl|\bshine|閃|魔法|\bwow\b",
            "speedlines": r"\bruns?\b|\brunning\b|\bfast\b|\brush|\bspeed|衝|快", "focuslines": r"\bshock|surprise|驚|\bscream|爆",
            "petals": r"\bspring\b|cherry|blossom|花瓣|櫻", "bubbles": r"\bbath|bubble|泡泡|洗澡|underwater", "notes": r"\bsing|\bmusic|\bdanc|唱|音樂|跳舞",
            "stars": r"\bdream|night sky|starry|星空", "sunrays": r"\bsunny\b|\bmorning\b|\bhope\b|陽光|早晨|希望"}



def guess_fx(text: str, limit: int = 2) -> list[str]:
    import re
    low = (text or "").lower()
    hits = [(m.start(), k) for k, pat in FX_WORDS.items() if (m := re.search(pat, low))]
    return [k for _, k in sorted(hits)][:limit]


def draw_fx(c: skia.Canvas, kind: str, t: float, W: int, H: int, seed: int, palette: list[str], white: bool = False,
            center: tuple[float, float] | None = None) -> None:
    rng = random.Random(seed * 131 + len(kind))
    ink = "#232327"
    if kind == "rain":
        p = skia.Paint(AntiAlias=True, Color=skc("#9EC9FF" if not white else ink, 0.55), StrokeWidth=max(1.5, H * 0.0025), StrokeCap=skia.Paint.kRound_Cap)
        for i in range(140):
            x0, sp = rng.random() * (W + 200) - 100, 0.9 + rng.random() * 0.6
            y = ((rng.random() + t * sp * 1.6) % 1.2 - 0.1) * H
            x = x0 - (y / H) * 60
            c.drawLine(x, y, x - 6, y + H * 0.04, p)
    elif kind == "snow":
        for i in range(90):
            sp = 0.08 + rng.random() * 0.12
            x = (rng.random() * W + math.sin(t * 1.3 + i) * 20) % W
            y = ((rng.random() + t * sp) % 1.1 - 0.05) * H
            c.drawCircle(x, y, H * (0.003 + rng.random() * 0.004), skia.Paint(AntiAlias=True, Color=skc("#FFFFFF" if not white else ink, 0.9)))
    elif kind in ("confetti", "petals"):
        cols = palette if kind == "confetti" else ["#FFC1D6", "#FFD6E5", "#FFB3C9"]
        for i in range(80 if kind == "confetti" else 45):
            sp = 0.15 + rng.random() * 0.2
            x = (rng.random() * W + math.sin(t * 2 + i) * 30) % W
            y = ((rng.random() + t * sp) % 1.1 - 0.05) * H
            a = t * (2 + rng.random() * 4) + i
            sz = H * (0.008 + rng.random() * 0.008)
            c.save()
            c.translate(x, y)
            c.rotate(math.degrees(a))
            p = skia.Paint(AntiAlias=True, Color=skc(ink if white else cols[i % len(cols)], 0.95))
            if kind == "confetti":
                c.drawRect(skia.Rect.MakeXYWH(-sz, -sz * 0.4, sz * 2, sz * 0.8 * abs(math.cos(a))), p)
            else:
                c.drawOval(skia.Rect.MakeXYWH(-sz, -sz * 0.5, sz * 2, sz), p)
            c.restore()
    elif kind in ("hearts", "notes", "bubbles", "sparkles", "stars"):
        n = {"hearts": 14, "notes": 10, "bubbles": 22, "sparkles": 24, "stars": 30}[kind]
        cx, cy = center or (W * 0.5, H * 0.5)
        for i in range(n):
            ph = rng.random()
            life = (t * (0.35 + rng.random() * 0.3) + ph) % 1.0
            if kind in ("sparkles", "stars"):
                x, y = rng.random() * W, rng.random() * H * (0.9 if kind == "sparkles" else 0.6)
                a = max(0.0, math.sin(life * math.pi))
                sz = H * (0.01 + rng.random() * 0.016) * (0.4 + a)
                c.drawPath(_star(x, y, sz, sz * 0.32, 4), skia.Paint(AntiAlias=True, Color=skc(ink if white else "#FFF3A0", 0.9 * a)))
                continue
            x = cx + (rng.random() - 0.5) * W * 0.7 + math.sin(life * 6 + i) * 18
            y = cy + H * 0.25 - life * H * 0.8
            a = max(0.0, 1 - life) * min(1.0, life * 5)
            sz = H * (0.018 + rng.random() * 0.014)
            if kind == "hearts":
                c.drawPath(_heart(x, y, sz), skia.Paint(AntiAlias=True, Color=skc(ink if white else "#FF6B8B", 0.85 * a)))
            elif kind == "bubbles":
                c.drawCircle(x, y, sz, skia.Paint(AntiAlias=True, Color=skc("#FFFFFF" if not white else ink, 0.75 * a), Style=skia.Paint.kStroke_Style, StrokeWidth=2))
                c.drawCircle(x - sz * 0.35, y - sz * 0.35, sz * 0.2, skia.Paint(AntiAlias=True, Color=skc("#FFFFFF", 0.8 * a)))
            else:
                p = skia.Paint(AntiAlias=True, Color=skc(ink if white else palette[i % len(palette)], 0.9 * a))
                c.drawOval(skia.Rect.MakeXYWH(x - sz * 0.6, y - sz * 0.4, sz * 1.2, sz * 0.8), p)
                c.drawRect(skia.Rect.MakeXYWH(x + sz * 0.45, y - sz * 1.6, sz * 0.18, sz * 1.5), p)
    elif kind in ("speedlines", "focuslines"):
        cx, cy = center or (W * 0.5, H * 0.45)
        rr = random.Random(seed * 7 + int(t * 12))
        p = skia.Paint(AntiAlias=True, Color=skc(ink if (white or kind == "focuslines") else "#FFFFFF", 0.55))
        for i in range(70):
            if kind == "speedlines":
                y = rr.random() * H
                L = W * (0.15 + rr.random() * 0.35)
                x = rr.random() * W
                c.drawRect(skia.Rect.MakeXYWH(x, y, L, max(1.5, H * 0.003)), p)
            else:
                a = rr.random() * math.tau
                r0 = H * (0.38 + rr.random() * 0.12)
                w = 0.01 + rr.random() * 0.012
                tri = skia.Path()
                tri.moveTo(cx + math.cos(a) * r0, cy + math.sin(a) * r0)
                tri.lineTo(cx + math.cos(a - w) * W, cy + math.sin(a - w) * W)
                tri.lineTo(cx + math.cos(a + w) * W, cy + math.sin(a + w) * W)
                tri.close()
                c.drawPath(tri, p)
    elif kind == "sunrays":
        cx, cy = W * 0.85, -H * 0.05
        for i in range(9):
            a = math.radians(100 + i * 9 + 3 * math.sin(t * 0.5 + i))
            tri = skia.Path()
            tri.moveTo(cx, cy)
            tri.lineTo(cx + math.cos(a - 0.03) * W * 1.5, cy + math.sin(a - 0.03) * W * 1.5)
            tri.lineTo(cx + math.cos(a + 0.03) * W * 1.5, cy + math.sin(a + 0.03) * W * 1.5)
            tri.close()
            c.drawPath(tri, skia.Paint(AntiAlias=True, Color=skc("#FFF6C8", 0.12)))
    elif kind in ("bokeh", "glow", "dust"):
        for i in range(18 if kind != "dust" else 40):
            x = (rng.random() * W + t * 8 * (1 + i % 3)) % W
            y = rng.random() * H
            sz = H * (0.03 + rng.random() * 0.05) if kind != "dust" else H * 0.003
            col = palette[i % len(palette)] if kind == "bokeh" else "#FFFFFF"
            p = skia.Paint(AntiAlias=True, Color=skc(col, 0.18 if kind != "dust" else 0.6))
            if kind == "bokeh":
                p.setMaskFilter(skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, sz * 0.25))
            c.drawCircle(x, y, sz, p)


# ---------- post-processing ----------
@functools.lru_cache(maxsize=8)
def _paper(w: int, h: int, seed: int = 7) -> np.ndarray:
    import cv2
    rng = np.random.default_rng(seed)
    n = rng.random((h // 4 + 1, w // 4 + 1)).astype(np.float32)
    n = cv2.resize(n, (w, h), interpolation=cv2.INTER_CUBIC)
    fine = rng.random((h, w)).astype(np.float32)
    fine = cv2.GaussianBlur(fine, (0, 0), 0.8)
    tex = 0.8 * n + 0.2 * fine
    tex = (tex - tex.mean()) / (tex.std() + 1e-6)
    return tex


@functools.lru_cache(maxsize=8)
def _crayon(w: int, h: int, seed: int = 11) -> np.ndarray:
    import cv2
    rng = np.random.default_rng(seed)
    n = rng.random((h, w)).astype(np.float32)
    k = np.zeros((9, 9), np.float32)
    for i in range(9):
        k[i, 8 - i] = 1.0 / 9
    streak = cv2.filter2D(n, -1, k)
    tex = (streak - streak.mean()) / (streak.std() + 1e-6)
    return tex


@functools.lru_cache(maxsize=8)
def _vignette(w: int, h: int, k: float) -> np.ndarray:
    y, x = np.ogrid[:h, :w]
    d = np.sqrt(((x - w / 2) / (w / 2)) ** 2 + ((y - h / 2) / (h / 2)) ** 2)
    return (1 - k * np.clip(d - 0.55, 0, 1) ** 1.6).astype(np.float32)[..., None]


def post(img: np.ndarray, lk: dict, frame: int, palette: list[str] | None = None) -> np.ndarray:
    """img: HxWx3 uint8 RGB. Returns the processed frame."""
    import cv2
    ops = lk.get("post") or []
    if not ops:
        return img
    h, w = img.shape[:2]
    f = img.astype(np.float32)
    boil = frame // max(1, int(lk.get("step", 1)))
    for op in ops:
        if op == "paper":
            f *= (1 + 0.022 * _paper(w, h))[..., None]
        elif op == "bleed":
            soft = cv2.GaussianBlur(f, (0, 0), 1.3)
            f = f * 0.72 + soft * 0.28
            gran = _paper(w, h, 3 + boil % 3)
            f *= (1 - 0.014 * np.clip(gran, -2, 2))[..., None]
        elif op == "crayon":
            tex = _crayon(w, h, 11 + boil % 2)
            lum = f.mean(axis=2, keepdims=True) / 255
            f = f + (255 - f) * np.clip(tex[..., None] * 0.1 - 0.05, 0, 0.4) * (1 - lum * 0.3)
        elif op == "fiber":
            f *= (1 + 0.028 * _paper(w, h, 5))[..., None]
        elif op == "bloom":
            bright = np.clip(f - 200, 0, 55) * 3.0
            f = f + cv2.GaussianBlur(bright, (0, 0), max(4, h * 0.012)) * 0.35
        elif op == "vignette_soft":
            f *= _vignette(w, h, 0.22)
    return np.clip(f, 0, 255).astype(np.uint8)


def pixelate(img: np.ndarray, out_w: int, out_h: int, palette: list[str]) -> np.ndarray:
    """Low-res frame → limited palette (with a few derived shades) → crisp nearest-neighbour upscale."""
    import cv2
    pal = []
    for c in palette:
        r, g, b = parse(c)
        for k in (0.55, 1.0, 1.25):
            pal.append([min(1, r * k), min(1, g * k), min(1, b * k)])
    pal += [[0.08, 0.08, 0.1], [0.97, 0.97, 0.95], [0.55, 0.57, 0.62], [0.36, 0.62, 0.95], [0.4, 0.75, 0.42], [0.98, 0.82, 0.35],
            [0.95, 0.55, 0.35], [0.98, 0.85, 0.73], [0.85, 0.3, 0.32], [0.62, 0.45, 0.32]]
    P = (np.array(pal, np.float32) * 255)
    small = img.reshape(-1, 3).astype(np.float32)
    d = ((small[:, None, :] - P[None, :, :]) ** 2).sum(-1)
    q = P[d.argmin(1)].reshape(img.shape).astype(np.uint8)
    return cv2.resize(q, (out_w, out_h), interpolation=cv2.INTER_NEAREST)
