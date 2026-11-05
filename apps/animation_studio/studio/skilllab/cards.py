"""The paper cards of a company story, drawn by code over the moving picture so every word and number is exact.

The layout copies the reference look (a 16:9 business-story channel): the founder stands in the LEFT third of the picture and the
cards live in the open space beside him, never on top of him and never on top of each other.

  title    top right: small kicker, the company name, a red square and the years ("1937 – 2026"); the name shrinks to fit
  year     a big red year stamp, under the title (or top right on its own)
  stat     white cards whose number counts up ("210,000 employees"), stacked down the right half, staggered
  caption  a bold paper strip bottom left with one word in red ("ALL FROM ONE GARAGE")
  vs       rivalry scene: the caption becomes a banner across the top ("THE PRICE WAR"), a red VS badge in the middle and a name tag
           under each character (the company on the left, the rival on the right)

plan(cards, W, H) works out every card's place once (no overlaps, everything inside the frame, cards that can't fit are left out);
overlay(cards, W, H, t) draws the layer for time t; burn(base, cards, out, W, H, seconds) composites it over a clip OR over a list of
pose pictures (a crossfaded, slowly pushing montage: the founder changes gesture every few seconds, like the reference)."""
from __future__ import annotations

import io
import json
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
GAP = 0.012                       # space between cards, as a share of the frame width


@lru_cache(maxsize=64)
def font(size: int, serif: bool = True, italic: bool = False) -> ImageFont.FreeTypeFont:
    names = (["DejaVuSerif-BoldItalic.ttf"] if italic else []) + (["DejaVuSerif-Bold.ttf", "LiberationSerif-Bold.ttf"] if serif else []) + \
        ["DejaVuSans-Bold.ttf", "LiberationSans-Bold.ttf", "arialbd.ttf"]
    roots = ["", "/usr/share/fonts/truetype/dejavu/", "/usr/share/fonts/truetype/liberation/"]
    for n in names:
        for r in roots:
            try:
                return ImageFont.truetype(r + n, max(6, size))
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


def _wrap(text: str, f: ImageFont.FreeTypeFont, width: float, lines: int = 2) -> list[str] | None:
    """Words in at most `lines` lines no wider than `width`; None when they don't fit (no word is ever cut)."""
    out, cur = [], ""
    for w in text.split():
        nxt = (cur + " " + w).strip()
        if f.getlength(nxt) <= width:
            cur = nxt
        elif not cur or f.getlength(w) > width:
            return None
        else:
            out.append(cur)
            cur = w
    out.append(cur)
    return out if len(out) <= lines else None


def _fit(text: str, size: float, width: float, lines: int, serif: bool = True, floor: float = 0.45) -> tuple[ImageFont.FreeTypeFont, list[str]]:
    """The biggest font (down to floor × size) whose wrapped text fits; the last resort is the smallest size, cut with an ellipsis."""
    s = size
    while s >= size * floor:
        f = font(int(s), serif)
        got = _wrap(text, f, width, lines)
        if got:
            return f, got
        s *= 0.92
    f = font(int(size * floor), serif)
    t = text
    while t and f.getlength(t + "…") > width:
        t = t[:-1]
    return f, [t.rstrip() + "…"]


def title_card(c: dict, u: float, max_w: float) -> Image.Image:
    name = str(c.get("text") or "").upper()
    kicker = str(c.get("kicker") or "THE STORY OF").upper()
    f, lines = _fit(name, u * 5.2, max_w - u * 4 - 8, 2)
    fk, fy = font(int(u * 1.5), serif=False), font(int(u * 1.7), serif=False)
    lh = f.size * 1.08
    years = str(c.get("years") or "")
    w = int(max([f.getlength(x) for x in lines] + [fk.getlength(kicker), fy.getlength(years) + u * 2.2]) + u * 4)
    h = int(u * 3.2 + len(lines) * lh + u * 3.4)
    im = _card((w, h))
    d = ImageDraw.Draw(im)
    d.text((u * 2 + 4, u * 1.4), kicker, font=fk, fill=(110, 104, 92, 255))
    y = u * 3.2
    for ln in lines:
        d.text((u * 2 + 4, y), ln, font=f, fill=(20, 20, 24, 255))
        y += lh
    d.rectangle((u * 2 + 4, y + u * 0.9, u * 3.4 + 4, y + u * 2.3), fill=RED)
    d.text((u * 4.2 + 4, y + u * 0.6), years, font=fy, fill=(60, 60, 64, 255))
    return im


def stat_card(c: dict, u: float, k: float, max_w: float) -> Image.Image:
    full = str(c.get("value") or "")
    unit = str(c.get("unit") or "")
    f, _ = _fit(full, u * 5.0, max_w - u * 4 - 8, 1)
    fu, ul = _fit(unit, u * 1.5, max_w - u * 4 - 8, 1, serif=True)
    fu = font(fu.size, italic=True)
    val = counted(full, k)
    w = int(max(f.getlength(full), fu.getlength(ul[0])) + u * 4)
    h = int(f.size * 1.18 + u * 4.0)
    im = _card((w, h))
    d = ImageDraw.Draw(im)
    d.text((4 + (w - f.getlength(val)) / 2, u * 1.0), val, font=f, fill=INK)
    d.text((4 + (w - fu.getlength(ul[0])) / 2, u * 1.4 + f.size * 1.12), ul[0], font=fu, fill=(90, 90, 96, 255))
    return im


def caption_card(c: dict, u: float, max_w: float, big: bool = False) -> Image.Image:
    text = str(c.get("text") or "").upper()
    accent = {w.strip(".,!?:;'\"") for w in str(c.get("accent") or "").upper().split()}
    f, lines = _fit(text, u * (3.6 if big else 3.0), max_w - u * 4 - 8, 1, serif=False)
    text = lines[0]
    w = int(f.getlength(text) + u * 4)
    im = _card((w, int(f.size * 1.25 + u * 2.0)), radius=3)
    d = ImageDraw.Draw(im)
    x = u * 2 + 4
    for word in text.split():
        col = RED if word.strip(".,!?:;'\"…") in accent else (22, 22, 26, 255)
        d.text((x, u * 1.0), word, font=f, fill=col)
        x += f.getlength(word + " ")
    return im


def tag(text: str, u: float, dark: bool, max_w: float) -> Image.Image:
    t = text.upper()
    f, lines = _fit(t, u * 2.0, max_w - u * 2.4 - 8, 1, serif=False)
    w, h = int(f.getlength(lines[0]) + u * 2.4), int(f.size * 1.2 + u * 1.0)
    im = Image.new("RGBA", (w + 8, h + 8), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((4, 4, w + 4, h + 4), 4, fill=INK if dark else PAPER, outline=INK, width=2)
    d.text((4 + u * 1.2, 4 + u * 0.5), lines[0], font=f, fill=PAPER if dark else INK)
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
    f = font(int(u * 5.6))
    t = str(c.get("value") or c.get("text") or "")
    w = int(f.getlength(t) + u * 4)
    im = _card((w, int(f.size * 1.2 + u * 1.8)))
    ImageDraw.Draw(im).text((u * 2 + 4, u * 0.8), t, font=f, fill=RED)
    return im


# ---------------------------------------------------------------- layout
def _rect(cx: float, cy: float, im: Image.Image, pad: float) -> tuple[float, float, float, float]:
    return (cx - im.width / 2 - pad, cy - im.height / 2 - pad, cx + im.width / 2 + pad, cy + im.height / 2 + pad)


def _hits(a, b) -> bool:
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def _render(item: dict, u: float, k: float = 1.0) -> Image.Image:
    c, kind, mw = item["card"], item["kind"], item["max_w"]
    if kind == "title":
        return title_card(c, u, mw)
    if kind == "stat":
        return stat_card(c, u, k, mw)
    if kind in ("caption", "banner"):
        return caption_card(c, u, mw, big=kind == "banner")
    if kind == "year":
        return year_card(c, u)
    if kind == "badge":
        return vs_badge(u)
    return tag(item["text"], u, kind == "tag_r", mw)


@lru_cache(maxsize=32)
def _plan(key: str, W: int, H: int) -> tuple:
    cards = json.loads(key)
    portrait = H > W
    u = min(W, H) / 72 * (1.25 if portrait else 1.0)
    vs = next((c for c in cards if c.get("type") == "vs"), None)
    title = next((c for c in cards if c.get("type") == "title"), None)
    year = next((c for c in cards if c.get("type") == "year"), None)
    cap = next((c for c in cards if c.get("type") == "caption"), None)
    stats = [c for c in cards if c.get("type") == "stat"][:3]
    m = W * 0.03                                  # safe margin
    # The open area beside the founder: the right half in landscape, the top half in portrait.
    zx0, zx1 = (W * 0.50, W - m) if not portrait else (m, W - m)
    items: list[dict] = []

    def add(kind: str, card: dict | None, anchor: str, x: float, y: float, at: float, angle: float, max_w: float, text: str = "", zone=None) -> None:
        items.append({"kind": kind, "card": card or {}, "anchor": anchor, "x": x, "y": y, "at": at, "angle": angle, "max_w": max_w, "text": text,
                      "zone": zone or (zx0, m, zx1, H - m)})

    if vs:
        if cap:
            add("banner", cap, "top", W / 2, m, 0.3, -0.8, W * 0.70, zone=(m, m, W - m, H * 0.30))
        add("badge", None, "center", W / 2, H * 0.47, 0.6, 0, W * 0.2, zone=(W * 0.38, H * 0.25, W * 0.62, H * 0.72))
        if vs.get("left"):
            add("tag_l", None, "center", W * 0.22, H * 0.74, 1.0, -1.5, W * 0.40, str(vs["left"]), zone=(m, H * 0.6, W * 0.49, H - m))
        if vs.get("right"):
            add("tag_r", None, "center", W * 0.76, H * 0.74, 1.2, 1.5, W * 0.40, str(vs["right"]), zone=(W * 0.51, H * 0.6, W - m, H - m))
    else:
        if title:
            add("title", title, "topright", zx1, m, 0.3, -1.5, (zx1 - zx0) * (0.86 if not portrait else 0.9))
        if year and not title:                     # the title card already carries the years
            add("year", year, "topright", zx1 - (W * 0.02 if title else 0), m, 0.5, -2.5, W * 0.3)
        right = not portrait
        for i, c in enumerate(stats):
            # Staggered down the open area like pinned paper notes; each card at most half the area wide.
            if portrait:
                x = (W * (0.28, 0.72, 0.5)[i])
            else:
                x = zx0 + (zx1 - zx0) * (0.36, 0.68, 0.42)[i]
            add("stat", c, "center", x, H * (0.36 if right else 0.44) + i * H * 0.04, 0.9 + i * 0.7, (-1.8, 1.4, -0.8)[i],
                (zx1 - zx0) * (0.62 if not portrait else 0.48))
        if cap:
            cx0 = W * 0.36 if not portrait else m                  # landscape: right of the character, who stands in the left third
            add("caption", cap, "bottomleft" if not portrait else "bottom", cx0 if not portrait else W / 2, H - m, 1.8 + 0.4 * len(stats), 1.0,
                W * 0.60 if not portrait else W - 2 * m, zone=(cx0, H * 0.55, W - m, H - m))

    order = {"title": 0, "banner": 0, "caption": 1, "badge": 2, "tag_l": 3, "tag_r": 3, "year": 4, "stat": 5}
    items.sort(key=lambda it: order[it["kind"]])          # stable: stats keep their order
    placed: list[tuple] = []
    out = []
    pad = W * GAP / 2
    for it in items:
        scale = 1.0
        ok = None
        while scale >= 0.6 and ok is None:
            im = _render(it, u * scale)
            w2, h2 = im.width / 2, im.height / 2
            a = it["anchor"]
            cx = {"topright": it["x"] - w2, "bottomleft": it["x"] + w2}.get(a, it["x"])
            cy = {"top": it["y"] + h2, "topright": it["y"] + h2, "bottom": it["y"] - h2, "bottomleft": it["y"] - h2}.get(a, it["y"])
            z = it["zone"]
            cx = min(max(cx, z[0] + w2), z[2] - w2) if z[2] - z[0] >= im.width else (z[0] + z[2]) / 2
            step = H * 0.01
            direction = -1 if a in ("bottom", "bottomleft") else 1
            xs = [cx] + ([z[0] + w2, z[2] - w2] if it["kind"] == "stat" and z[2] - z[0] >= im.width else [])
            for _ in range(200):
                r = _rect(cx, cy, im, pad)
                if r[1] + pad < z[1] - 0.5 or r[3] - pad > z[3] + 0.5:
                    break
                free = next((x for x in xs if not any(_hits(_rect(x, cy, im, pad), q) for q in placed)), None)
                if free is not None:
                    ok = (free, cy)
                    break
                cy += step * direction
            if ok is None:
                scale *= 0.88
        if ok is None:
            continue                                   # it can't fit without covering something: leave it out
        placed.append(_rect(ok[0], ok[1], im, pad))
        out.append({**{k: v for k, v in it.items() if k != "zone"}, "cx": ok[0], "cy": ok[1], "u": u * scale})
    return tuple(json.dumps(x) for x in out)


def plan(cards: list[dict], W: int, H: int) -> list[dict]:
    """Where every card goes: [{kind, cx, cy, u, at, angle, …}], no two overlapping, all inside the frame."""
    return [json.loads(x) for x in _plan(json.dumps(cards, sort_keys=True), W, H)]


def _place(layer: Image.Image, im: Image.Image, cx: float, cy: float, scale: float, angle: float) -> None:
    if scale <= 0.02:
        return
    w, h = im.size
    if abs(scale - 1) > 1e-3:
        im = im.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.LANCZOS)
    if angle:
        im = im.rotate(angle, expand=True, resample=Image.BICUBIC)
    layer.alpha_composite(im, (int(cx - im.width / 2), int(cy - im.height / 2)))


@lru_cache(maxsize=256)
def _still(key: str, k: float) -> Image.Image:
    it = json.loads(key)
    return _render(it, it["u"], k)


def overlay(cards: list[dict], W: int, H: int, t: float) -> Image.Image:
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    for it in plan(cards, W, H):
        s = _pop(t, it["at"])
        if s <= 0:
            continue
        k = round(_ease((t - it["at"]) / 1.3), 3) if it["kind"] == "stat" else 1.0
        angle = it["angle"] + (math.sin(t * 22) * 2.5 if it["kind"] == "badge" and it["at"] < t < it["at"] + 0.6 else 0)
        im = _still(json.dumps(it, sort_keys=True), k) if k >= 1.0 or it["kind"] != "stat" else _render(it, it["u"], k)
        _place(layer, im, it["cx"], it["cy"], s, angle)
    return layer


# ---------------------------------------------------------------- frames
def _cover(img: Image.Image, W: int, H: int, extra: float = 1.0) -> Image.Image:
    """Scale to cover W×H (times `extra`, room for the push-in) and centre-crop: never a letterbox gap."""
    img = img.convert("RGB")
    s = max(W * extra / img.width, H * extra / img.height)
    img = img.resize((max(1, round(img.width * s)), max(1, round(img.height * s))), Image.LANCZOS)
    tw, th = round(W * extra), round(H * extra)
    x, y = (img.width - tw) // 2, (img.height - th) // 2
    return img.crop((x, y, x + tw, y + th))


def pose_frames(pictures: list[bytes], W: int, H: int, seconds: float, fade: float = 0.25, active: float | None = None):
    """A montage of the pose pictures: each holds for an equal share of the scene with a slow push-in (alternating a little left and
    right, so the cut reads as a new camera set-up), and crossfades into the next. The poses share the first `active` seconds (the part
    that is surely shown); the last one holds to the end. Yields W×H RGB frames."""
    ims = [_cover(Image.open(io.BytesIO(b)), W, H, 1.08) for b in pictures if b] or [Image.new("RGB", (W, H), (120, 160, 120))]
    n = int(round(seconds * FPS))
    seg = min(seconds, active or seconds) / len(ims)

    def frame(i: int, t: float) -> Image.Image:
        im = ims[i]
        span = seg if i < len(ims) - 1 else max(seg, seconds - i * seg)
        k = min(1.0, max(0.0, (t - i * seg) / span))
        z = 1.08 - 0.06 * _ease(k * 0.9 + 0.1 * k)              # from 8 % zoomed in toward 2 %: a gentle push
        cw, ch = min(im.width, W * z), min(im.height, H * z)
        drift = (0.5 + (0.12 if i % 2 else -0.12) * (k - 0.5))
        x0 = max(0.0, (im.width - cw) * drift)
        y0 = max(0.0, (im.height - ch) * 0.45)
        return im.resize((W, H), Image.BILINEAR, box=(x0, y0, x0 + cw, y0 + ch))

    for f in range(n):
        t = f / FPS
        i = min(len(ims) - 1, int(t / seg))
        out = frame(i, t)
        into = (i + 1) * seg - t
        if i + 1 < len(ims) and into < fade:
            out = Image.blend(out, frame(i + 1, t), 1 - into / fade)
        yield out


def _clip_frames(base: Path, W: int, H: int, seconds: float, ffmpeg: str):
    n = int(round(seconds * FPS))
    dec = subprocess.Popen([ffmpeg, "-v", "error", "-i", str(base), "-an", "-vf",
                            f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS},tpad=stop_mode=clone:stop_duration={seconds:.2f}",
                            "-frames:v", str(n), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
    size, last = W * H * 3, None
    try:
        for _ in range(n):
            buf = dec.stdout.read(size) if dec.stdout else b""
            if len(buf) == size:
                last = buf
            elif last is None:
                raise RuntimeError("the base clip has no frames")
            yield Image.frombuffer("RGB", (W, H), last, "raw", "RGB", 0, 1)
    finally:
        dec.kill()
        dec.wait()


def burn(base: Path | list[bytes], cards: list[dict], out: Path, W: int, H: int, seconds: float, ffmpeg: str = "ffmpeg", active: float | None = None) -> Path:
    """Composite the cards over `base`: a clip (any size; scaled and cropped to W×H, held on its last frame to `seconds`) or a list
    of pose pictures (made into a pose montage)."""
    frames = pose_frames(base, W, H, seconds, active=active) if isinstance(base, list) else _clip_frames(Path(base), W, H, seconds, ffmpeg)
    enc = subprocess.Popen([ffmpeg, "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                            "-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-pix_fmt", "yuv420p", str(out)], stdin=subprocess.PIPE)
    try:
        for i, fr in enumerate(frames):
            if cards:
                fr = fr.convert("RGBA")
                fr.alpha_composite(overlay(cards, W, H, i / FPS))
            enc.stdin.write(fr.convert("RGB").tobytes())
    finally:
        if enc.stdin:
            enc.stdin.close()
        enc.wait()
    if enc.returncode:
        raise RuntimeError("FFmpeg could not write the scene with its cards")
    return out
