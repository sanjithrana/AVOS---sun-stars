"""The paper cards of a company story, drawn by code over the moving picture so every word and number is exact:

  title    top right: small kicker, the company name, a red square and the years ("1937 – 2026")
  stat     white cards whose number counts up ("210,000 employees", "$44B in revenue")
  caption  a bold strip at the bottom with one word in red ("ALL FROM ONE GARAGE")
  vs       a red VS badge between two name tags (the company and its rival)
  year     a big year stamp top left ("1984")

overlay(cards, W, H, t) gives the RGBA layer for time t; burn(base_mp4, cards, out, W, H, seconds) composites it frame by frame."""
from __future__ import annotations

import math
import re
import subprocess
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

PAPER = (247, 242, 230, 255)
INK = (24, 38, 74, 255)          # navy
RED = (210, 48, 40, 255)
SHADOW = (0, 0, 0, 90)
FPS = 24


@lru_cache(maxsize=64)
def font(size: int, serif: bool = True, italic: bool = False) -> ImageFont.FreeTypeFont:
    names = (["DejaVuSerif-BoldItalic.ttf"] if italic else []) + (["DejaVuSerif-Bold.ttf", "LiberationSerif-Bold.ttf"] if serif else []) + \
        ["DejaVuSans-Bold.ttf", "LiberationSans-Bold.ttf", "arialbd.ttf"]
    roots = ["", "/usr/share/fonts/truetype/dejavu/", "/usr/share/fonts/truetype/liberation/"]
    for n in names:
        for r in roots:
            try:
                return ImageFont.truetype(r + n, size)
            except OSError:
                continue
    return ImageFont.load_default()


def parse_number(v: str) -> tuple[str, float, str, int]:
    """'$44B' → ('$', 44, 'B', 0) · '210,000' → ('', 210000, '', 0) · '4.5%' → ('', 4.5, '%', 1)."""
    m = re.search(r"(\d[\d,]*(?:\.\d+)?)", v or "")
    if not m:
        return v or "", 0.0, "", 0
    num = m.group(1).replace(",", "")
    dec = len(num.split(".")[1]) if "." in num else 0
    return v[:m.start()], float(num), v[m.end():], dec


def counted(v: str, k: float) -> str:
    pre, n, suf, dec = parse_number(v)
    if not n:
        return v
    x = n * min(1.0, max(0.0, k))
    body = f"{x:,.{dec}f}" if "," in v or n >= 10000 else f"{x:.{dec}f}"
    return f"{pre}{body}{suf}"


def _ease(k: float) -> float:
    k = min(1.0, max(0.0, k))
    return 1 - (1 - k) ** 3


def _pop(t: float, at: float) -> float:
    """0 before `at`, a quick overshoot pop to 1."""
    k = (t - at) / 0.35
    if k <= 0:
        return 0.0
    if k >= 1:
        return 1.0
    return 1.08 * _ease(k / 0.6) if k < 0.6 else 1.08 - 0.08 * (k - 0.6) / 0.4


def _card(size: tuple[int, int], radius: int = 6) -> Image.Image:
    w, h = size
    im = Image.new("RGBA", (w + 16, h + 16), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((10, 12, w + 10, h + 12), radius, fill=SHADOW)
    d.rounded_rectangle((4, 4, w + 4, h + 4), radius, fill=PAPER, outline=(205, 196, 176, 255), width=2)
    return im


def _place(layer: Image.Image, im: Image.Image, cx: float, cy: float, scale: float, angle: float) -> None:
    if scale <= 0.02:
        return
    w, h = im.size
    im = im.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.LANCZOS).rotate(angle, expand=True, resample=Image.BICUBIC)
    layer.alpha_composite(im, (int(cx - im.width / 2), int(cy - im.height / 2)))


def _wrap(text: str, f: ImageFont.FreeTypeFont, width: int, lines: int = 2) -> list[str]:
    words, out, cur = text.split(), [], ""
    for w in words:
        nxt = (cur + " " + w).strip()
        if f.getlength(nxt) <= width or not cur:
            cur = nxt
        else:
            out.append(cur)
            cur = w
    out.append(cur)
    return out[:lines]


def title_card(c: dict, u: float) -> Image.Image:
    name = str(c.get("text") or "").upper()
    kicker = str(c.get("kicker") or "THE STORY OF").upper()
    f, fk, fy = font(int(u * 5.2)), font(int(u * 1.5), serif=False), font(int(u * 1.7), serif=False)
    lines = _wrap(name, f, int(u * 30))
    w = int(max(f.getlength(x) for x in lines) + u * 4)
    h = int(u * 3 + len(lines) * u * 5.6 + u * 3.6)
    im = _card((w, h))
    d = ImageDraw.Draw(im)
    d.text((u * 2 + 4, u * 1.4), kicker, font=fk, fill=(110, 104, 92, 255))
    y = u * 3.2
    for ln in lines:
        d.text((u * 2 + 4, y), ln, font=f, fill=(20, 20, 24, 255))
        y += u * 5.6
    d.rectangle((u * 2 + 4, y + u * 0.9, u * 3.4 + 4, y + u * 2.3), fill=RED)
    d.text((u * 4.2 + 4, y + u * 0.6), str(c.get("years") or ""), font=fy, fill=(60, 60, 64, 255))
    return im


def stat_card(c: dict, u: float, k: float) -> Image.Image:
    val = counted(str(c.get("value") or ""), k)
    full = str(c.get("value") or "")
    f, fu = font(int(u * 5.6)), font(int(u * 1.5), italic=True)
    w = int(max(f.getlength(full), fu.getlength(str(c.get("unit") or ""))) + u * 4)
    im = _card((w, int(u * 9.6)))
    d = ImageDraw.Draw(im)
    tw = f.getlength(val)
    d.text((4 + (w - tw) / 2, u * 1.0), val, font=f, fill=INK)
    unit = str(c.get("unit") or "")
    d.text((4 + (w - fu.getlength(unit)) / 2, u * 7.0), unit, font=fu, fill=(90, 90, 96, 255))
    return im


def caption_card(c: dict, u: float) -> Image.Image:
    text = str(c.get("text") or "").upper()
    accent = str(c.get("accent") or "").upper().strip()
    f = font(int(u * 3.0), serif=False)
    w = int(f.getlength(text) + u * 4)
    im = _card((w, int(u * 5.2)), radius=3)
    d = ImageDraw.Draw(im)
    x = u * 2 + 4
    for word in text.split():
        col = RED if accent and word.strip(".,!?") in accent.split() else (22, 22, 26, 255)
        d.text((x, u * 1.0), word, font=f, fill=col)
        x += f.getlength(word + " ")
    return im


def tag(text: str, u: float, dark: bool) -> Image.Image:
    f = font(int(u * 2.0), serif=False)
    t = text.upper()
    w, h = int(f.getlength(t) + u * 2.4), int(u * 3.4)
    im = Image.new("RGBA", (w + 8, h + 8), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((4, 4, w + 4, h + 4), 4, fill=INK if dark else PAPER, outline=INK, width=2)
    d.text((4 + u * 1.2, 4 + u * 0.55), t, font=f, fill=PAPER if dark else INK)
    return im


def vs_badge(u: float) -> Image.Image:
    r = int(u * 4.2)
    im = Image.new("RGBA", (r * 2 + 12, r * 2 + 12), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.ellipse((8, 10, r * 2 + 8, r * 2 + 10), fill=SHADOW)
    d.ellipse((4, 4, r * 2 + 4, r * 2 + 4), fill=RED, outline=PAPER, width=max(2, int(u * 0.5)))
    f = font(int(u * 3.6), serif=False)
    d.text((4 + r - f.getlength("VS") / 2, 4 + r - u * 2.2), "VS", font=f, fill=PAPER)
    return im


def year_card(c: dict, u: float) -> Image.Image:
    f = font(int(u * 6.4))
    t = str(c.get("value") or c.get("text") or "")
    w = int(f.getlength(t) + u * 4)
    im = _card((w, int(u * 8.6)))
    ImageDraw.Draw(im).text((u * 2 + 4, u * 0.8), t, font=f, fill=RED)
    return im


def _angle(i: int, kind: str) -> float:
    return {"title": -1.5, "caption": 1.2, "year": -2.5}.get(kind, (-1.8, 1.4, -0.8)[i % 3])


def overlay(cards: list[dict], W: int, H: int, t: float) -> Image.Image:
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    portrait = H > W
    u = min(W, H) / 72 * (1.25 if portrait else 1.0)
    stats = [c for c in cards if c.get("type") == "stat"][:3]
    spots = ([(0.52, 0.40), (0.78, 0.56), (0.56, 0.68)] if not portrait else [(0.30, 0.42), (0.72, 0.40), (0.50, 0.56)])
    for c in cards:
        kind = c.get("type")
        if kind == "title":
            im = title_card(c, u)
            s = _pop(t, 0.3)
            _place(layer, im, W - im.width / 2 - u * 2.5 if not portrait else W / 2, im.height / 2 + u * 2.5, s, _angle(0, "title"))
        elif kind == "caption":
            s = _pop(t, 1.6)
            _place(layer, caption_card(c, u), W * 0.5, H - u * (6 if not portrait else 14), s, _angle(0, "caption"))
        elif kind == "year":
            s = _pop(t, 0.4)
            im = year_card(c, u)
            _place(layer, im, im.width / 2 + u * 3, im.height / 2 + u * 3, s, _angle(0, "year"))
        elif kind == "vs":
            s = _pop(t, 0.6)
            shake = math.sin(t * 22) * 2.5 if 0.6 < t < 1.2 else 0
            _place(layer, vs_badge(u), W * 0.5, H * (0.40 if not portrait else 0.46), s, shake)
            if c.get("left"):
                _place(layer, tag(str(c["left"]), u, False), W * 0.26, H * 0.62, _pop(t, 1.0), -1.5)
            if c.get("right"):
                _place(layer, tag(str(c["right"]), u, True), W * 0.74, H * 0.62, _pop(t, 1.2), 1.5)
    for i, c in enumerate(stats):
        at = 0.8 + i * 0.6
        x, y = spots[i]
        _place(layer, stat_card(c, u, _ease((t - at) / 1.3)), W * x, H * y, _pop(t, at), _angle(i, "stat"))
    return layer


def burn(base: Path, cards: list[dict], out: Path, W: int, H: int, seconds: float, ffmpeg: str = "ffmpeg") -> Path:
    """Composite the cards over `base` (any size; scaled and cropped to W×H, held on its last frame to `seconds`)."""
    n = int(round(seconds * FPS))
    dec = subprocess.Popen([ffmpeg, "-v", "error", "-i", str(base), "-an", "-vf",
                            f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS},tpad=stop_mode=clone:stop_duration={seconds:.2f}",
                            "-frames:v", str(n), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
    enc = subprocess.Popen([ffmpeg, "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                            "-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-pix_fmt", "yuv420p", str(out)], stdin=subprocess.PIPE)
    size, last, i = W * H * 3, None, 0
    try:
        while i < n:
            buf = dec.stdout.read(size) if dec.stdout else b""
            if len(buf) == size:
                last = buf
            elif last is None:
                raise RuntimeError("the base clip has no frames")
            frame = Image.frombuffer("RGB", (W, H), last, "raw", "RGB", 0, 1).convert("RGBA")
            if cards:
                frame.alpha_composite(overlay(cards, W, H, i / FPS))
            enc.stdin.write(frame.convert("RGB").tobytes())
            i += 1
    finally:
        if enc.stdin:
            enc.stdin.close()
        enc.wait()
        dec.kill()
        dec.wait()
    if enc.returncode:
        raise RuntimeError("FFmpeg could not write the scene with its cards")
    return out
