"""Puts one of the ready-made 2D characters on a scene's backdrop IN CODE, so the character in every scene is exactly the character you picked
(same face, hair, suit) and never depends on a picture model following a reference.

characters/<id>/<pose>.png   transparent cut-outs of the character from his model sheet (all at the same scale, feet at the bottom)
characters/<id>_2d.jpg    the picture shown on the create page

choose() maps a scene's three gestures ("pointing toward the right", "hand on chin, thinking"…) to the poses that character has;
place() stands the chosen pose in the left third of the backdrop with a soft ground shadow, leaving the right half for the paper cards."""
from __future__ import annotations

import io
import math
import random
import re
from functools import lru_cache
from pathlib import Path
from typing import NamedTuple

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageOps

DIR = Path(__file__).with_name("characters")
# first match wins; order matters ("holding a phone" before "holding a tablet")
INTENTS = [("phone", r"phone|\bcall"), ("device", r"tablet|laptop|computer|screen|paper|document|read|sketch|writ|napkin|notebook|hold"),
           ("cheer", r"cheer|celebrat|triumph|fist|victory|jump|excit|success|punch"), ("think", r"think|chin|ponder|worr|doubt|stare|puzzl|concern|plan"),
           ("open", r"open|wide|welcom|spread|embrace|greet|proud|shrug"), ("point", r"point|direct|toward|stretch|show|explain|present|chart|gestur")]
CANDIDATES = {"phone": ["call"], "device": ["laptop", "tablet"], "cheer": ["celebrate", "point"], "think": ["think"], "open": ["welcome"],
              "point": ["present", "explain", "point"], "neutral": ["front", "front34"]}
FALLBACK = ["welcome", "front34", "think", "front", "present", "explain"]


def sprites(cid: str) -> dict[str, Path]:
    return {f.stem: f for f in sorted((DIR / cid).glob("*.png"))} if (DIR / cid).is_dir() else {}


def intent(text: str) -> str:
    t = (text or "").lower()
    return next((k for k, rx in INTENTS if re.search(rx, t)), "neutral")


def choose(cid: str, texts: list[str], n: int = 3) -> list[str]:
    """n different pose names for this character, following the gestures in `texts` as far as the character has them."""
    pool = sprites(cid)
    if not pool:
        raise RuntimeError(f"The character “{cid}” has no pose pictures (animation_studio/studio/skilllab/characters/{cid}/).")
    used: list[str] = []
    for i in range(n):
        wanted = CANDIDATES.get(intent(texts[i] if i < len(texts) else ""), []) + CANDIDATES["neutral"] + FALLBACK
        pick = next((w for w in wanted if w in pool and w not in used), None) or next((k for k in pool if k not in used), next(iter(pool)))
        used.append(pick)
    return used


def _cover(img: Image.Image, W: int, H: int) -> Image.Image:
    img = img.convert("RGBA")
    s = max(W / img.width, H / img.height)
    img = img.resize((max(1, round(img.width * s)), max(1, round(img.height * s))), Image.LANCZOS)
    x, y = (img.width - W) // 2, (img.height - H) // 2
    return img.crop((x, y, x + W, y + H))


# ---------------------------------------------------------------- paper-cut look
CREAM = (238, 229, 207)
FPS = 24


def _grain(W: int, H: int, seed: int, strength: float = 7.0) -> np.ndarray:
    """Paper fibre: fine noise plus a few hundred short pale and dark fibres, as a signed (H, W, 1) float array."""
    rng = np.random.default_rng(seed)
    g = rng.normal(0, strength, (H, W)).astype(np.float32)
    f = Image.new("L", (W, H), 128)
    d = ImageDraw.Draw(f)
    r = random.Random(seed)
    for _ in range(int(W * H / 2600)):
        x, y, a, l = r.uniform(0, W), r.uniform(0, H), r.uniform(0, math.pi), r.uniform(6, 22)
        d.line((x, y, x + math.cos(a) * l, y + math.sin(a) * l), fill=r.choice((150, 108)), width=1)
    g += (np.asarray(f.filter(ImageFilter.GaussianBlur(0.6)), dtype=np.float32) - 128) * 0.55
    return g[:, :, None]


def paper_bg(raw: bytes, W: int, H: int, seed: int = 7) -> Image.Image:
    """Turns whatever the picture model drew into a paper-cut collage backdrop: the model's watermark strip is cropped off, the detail is
    smoothed and posterised into flat paper colours, then paper fibre, a warm tint and a soft vignette are laid over it. Same look for every
    scene, whatever the model did."""
    im = Image.open(io.BytesIO(raw)).convert("RGB")
    im = im.crop((0, 0, im.width, int(im.height * 0.90)))              # the free picture models stamp a watermark across the bottom-right
    im = _cover(im.convert("RGBA"), W, H).convert("RGB")
    for _ in range(2):
        im = im.filter(ImageFilter.MedianFilter(5))
    im = ImageOps.posterize(ImageEnhance.Color(im).enhance(1.22), 5)
    im = ImageEnhance.Contrast(im).enhance(1.06).filter(ImageFilter.UnsharpMask(2, 90, 3))
    a = np.asarray(im, dtype=np.float32) * 0.93 + np.array(CREAM, dtype=np.float32) * 0.07
    a += _grain(W, H, seed)
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    v = np.clip(((xx / W - 0.5) ** 2 + (yy / H - 0.5) ** 2) * 1.5, 0, 1)
    a *= (1 - 0.14 * v)[:, :, None]
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))


@lru_cache(maxsize=8)
def torn_frame(W: int, H: int, seed: int = 3) -> Image.Image:
    """A cream paper border with a hand-torn inner edge and a soft shadow, laid over every frame (the scene is a sheet pasted on paper)."""
    r = random.Random(seed)
    m = max(8, round(H * 0.022))
    amp = max(2.0, H * 0.006)

    def edge(n: int, fixed: float, sign: int, axis: int) -> list[tuple[float, float]]:
        pts = []
        steps = max(8, n // 14)
        for i in range(steps + 1):
            u = n * i / steps
            o = fixed + sign * (m + r.uniform(-amp, amp))
            pts.append((u, o) if axis == 0 else (o, u))
        return pts
    top = edge(W, 0, 1, 0)
    right = [(x, y) for x, y in edge(H, W, -1, 1)]
    bottom = [(x, y) for x, y in edge(W, H, -1, 0)][::-1]
    left = [(x, y) for x, y in edge(H, 0, 1, 1)][::-1]
    hole = Image.new("L", (W, H), 0)
    ImageDraw.Draw(hole).polygon(top + right + bottom + left, fill=255)
    border = ImageOps.invert(hole).filter(ImageFilter.GaussianBlur(0.8))
    shadow = hole.filter(ImageFilter.GaussianBlur(max(3, H * 0.008)))
    shadow = ImageOps.invert(shadow).point(lambda v: int(v * 0.35))
    out = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    out.paste(Image.new("RGBA", (W, H), (40, 30, 20, 255)), (0, 0), shadow)
    tint = np.clip(np.array(CREAM, dtype=np.float32)[None, None, :] + _grain(W, H, seed, 5.0), 0, 255).astype(np.uint8)
    out.paste(Image.fromarray(tint).convert("RGBA"), (0, 0), border)
    return out


@lru_cache(maxsize=64)
class Spot(NamedTuple):
    """Where the character stands on this scene: across (0-1), how tall he is as a fraction of the frame, whether he is mirrored so he
    faces into the scene, and how far down his feet are."""
    cx: float
    height: float
    mirror: bool
    floor: float


def layout(side: str, W: int, H: int) -> Spot:
    if side == "centre" or H > W:                 # a reel: he stands big and centred in the bottom third, the scene above him
        return Spot(0.5, 0.46, False, 0.94)
    if side == "right":
        return Spot(0.80, 0.76, True, 0.96)
    return Spot(0.20, 0.76, False, 0.96)


def _papery(sp: Image.Image) -> Image.Image:
    """Flattens the drawn character into the same paper colours as the backdrop, so he reads as another cut-out sheet and not as a
    render pasted on top. Alpha is untouched."""
    rgb = ImageOps.posterize(ImageEnhance.Color(sp.convert("RGB")).enhance(1.08), 5)
    a = np.asarray(rgb, dtype=np.float32) * 0.95 + np.array(CREAM, dtype=np.float32) * 0.05
    out = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)).convert("RGBA")
    out.putalpha(sp.split()[3])
    return out


def sticker(cid: str, name: str, W: int, H: int, height: float = 0.78, mirror: bool = False) -> tuple[Image.Image, int]:
    """The pose as a paper sticker: a white die-cut outline round the cartoon and a soft drop shadow. Returns the RGBA image (padded) and the
    pad, so the feet sit at (width / 2, height - pad)."""
    pool = sprites(cid)
    ref = Image.open(pool.get("front") or next(iter(pool.values()))).height            # the standing figure's height: poses keep one scale
    sp = Image.open(pool[name]).convert("RGBA")
    s = min(height * H / ref, 0.46 * W / sp.width)
    sp = _papery(sp.resize((max(1, round(sp.width * s)), max(1, round(sp.height * s))), Image.LANCZOS))
    if mirror:
        sp = sp.transpose(Image.FLIP_LEFT_RIGHT)
    ring = max(3, round(min(W, H) * 0.009))
    pad = ring * 3 + 12
    al = Image.new("L", (sp.width + 2 * pad, sp.height + 2 * pad), 0)
    al.paste(sp.split()[3], (pad, pad))
    cut = al.filter(ImageFilter.MaxFilter(ring * 2 + 1)).filter(ImageFilter.GaussianBlur(0.7))     # the die-cut outline
    out = Image.new("RGBA", al.size, (0, 0, 0, 0))
    sh = cut.filter(ImageFilter.GaussianBlur(max(3, ring * 1.1))).point(lambda v: int(v * 0.42))
    out.paste(Image.new("RGBA", al.size, (25, 20, 15, 255)), (ring, ring + 2), sh)
    out.paste(Image.new("RGBA", al.size, (253, 251, 247, 255)), (0, 0), cut)       # the die-cut edge stays the brightest thing on the sheet
    body = Image.new("RGBA", al.size, (0, 0, 0, 0))
    body.paste(sp, (pad, pad))
    out.alpha_composite(body)
    return out, pad


def _ground(W: int, H: int, x: float, w: float, floor: float) -> Image.Image:
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(sh).ellipse((x - w * 0.38, floor * H - H * 0.02, x + w * 0.38, floor * H + H * 0.016), fill=(20, 25, 40, 90))
    return sh.filter(ImageFilter.GaussianBlur(max(2, H * 0.008)))


def place(backdrop: bytes, cid: str, name: str, W: int, H: int, side: str = "") -> bytes:
    """The paper-cut backdrop with pose `name` standing on it as a paper sticker, as PNG bytes (the scene picture; the border and the sway
    are added when the scene is animated)."""
    sp = layout(side, W, H)
    cx, height, floor = sp.cx, sp.height, sp.floor
    st, pad = sticker(cid, name, W, H, height, sp.mirror)
    out = paper_bg(backdrop, W, H).convert("RGBA")
    x = min(max(round(cx * W - st.width / 2), round(0.01 * W) - pad), round(0.99 * W - st.width + pad))
    out.alpha_composite(_ground(W, H, x + st.width / 2, st.width - 2 * pad, floor))
    out.alpha_composite(st, (x, round(floor * H - st.height + pad)))
    b = io.BytesIO()
    out.convert("RGB").save(b, "PNG")
    return b.getvalue()


def _ease(k: float) -> float:
    k = min(1.0, max(0.0, k))
    return 1 - (1 - k) ** 3


def scene_frames(backdrop: bytes, cid: str, names: list[str], W: int, H: int, seconds: float, active: float | None = None, side: str = "",
                 move: str = "slow push in"):
    """The free motion: the paper backdrop moves slowly the way the scene asks (push in, pull out or a pan) while the character, a paper
    puppet, rises into the frame, sways on his feet and flips over like a card to the next pose every few seconds. Yields W×H RGB frames."""
    spot = layout(side, W, H)
    cx, floor, height = spot.cx, spot.floor, spot.height
    bg = paper_bg(backdrop, W, H)
    big = bg.resize((round(W * 1.08), round(H * 1.08)), Image.LANCZOS)
    sts = [sticker(cid, nm, W, H, height, spot.mirror) for nm in names]
    n = int(round(seconds * FPS))
    seg = min(seconds, active or seconds) / len(sts)
    flip = 0.14
    fx = round(cx * W)
    ground = _ground(W, H, fx, sts[0][0].width - 2 * sts[0][1], floor)
    mv = (move or "").lower()
    for f in range(n):
        t = f / FPS
        k = t / seconds
        e = _ease(k)
        z = 0.94 + 0.06 * e if "out" in mv else 1 - 0.06 * e           # a pull-out starts close and opens up
        cw, ch = big.width * z, big.height * z
        if "pan left" in mv:
            px = 0.64 - 0.28 * e
        elif "pan right" in mv:
            px = 0.36 + 0.28 * e
        else:
            px = 0.5 + 0.1 * math.sin(k * math.pi)
        x0 = (big.width - cw) * px
        y0 = (big.height - ch) * 0.5
        frame = big.resize((W, H), Image.BILINEAR, box=(x0, y0, x0 + cw, y0 + ch)).convert("RGBA")
        frame.alpha_composite(ground)
        i = min(len(sts) - 1, int(t / seg))
        sx = 1.0
        if i + 1 < len(sts) and (i + 1) * seg - t < flip:
            sx = max(0.06, ((i + 1) * seg - t) / flip)
        elif i > 0 and t - i * seg < flip:
            sx = max(0.06, (t - i * seg) / flip)
        st, pad = sts[i]
        im = st
        if sx < 0.999:
            im = st.resize((max(2, round(st.width * sx)), st.height), Image.BILINEAR)
        im = im.rotate(1.5 * math.sin(2 * math.pi * t / 2.6), center=(im.width / 2, im.height - pad), resample=Image.BICUBIC)
        rise = (1 - _ease(t / 0.5)) * H * 0.3
        bob = -abs(math.sin(2 * math.pi * t / 1.3)) * H * 0.005
        frame.alpha_composite(im, (round(fx - im.width / 2), round(floor * H - im.height + pad + rise + bob)))
        yield frame.convert("RGB")


def too_dull(raw: bytes) -> str:
    """Why a backdrop is unusable, or "" when it is fine. A picture model asked for a crisis scene likes to answer with a dark,
    almost empty room; no amount of paper texture saves that, so the scene is drawn again brighter instead."""
    try:
        im = Image.open(io.BytesIO(raw)).convert("RGB")
    except Exception:  # noqa: BLE001 - not a picture at all
        return "it isn't a readable picture"
    im = im.resize((160, 90) if im.width >= im.height else (90, 160), Image.BILINEAR)
    a = np.asarray(im, dtype=np.float32)
    lum = a @ np.array([0.299, 0.587, 0.114], dtype=np.float32)
    if float(lum.mean()) < 62:
        return "it came back almost black"
    if float(lum.std()) < 17:
        return "it came back nearly empty"
    return ""


def paper_scene(W: int, H: int, seed: int = 5, side: str = "", vs: bool = False) -> bytes:
    """A paper set drawn here in code: a sky, a sun, two hill ranges, a skyline of cut-paper blocks and a ground band, each sheet with its own
    drop shadow. It is the backdrop when no picture model will draw one, so a run always has something to stand the character on."""
    r = random.Random(seed)
    sky = (r.choice([(214, 230, 240), (236, 216, 186), (222, 226, 214)]))
    im = Image.new("RGB", (W, H), sky)
    horizon = H * (0.62 if H <= W else 0.70)

    def sheet_(points, fill, lift: float = 0.012) -> None:
        d = max(2, round(H * lift))
        sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(sh).polygon([(x + d * 0.5, y + d) for x, y in points], fill=(50, 40, 28, 90))
        im.paste(Image.alpha_composite(im.convert("RGBA"), sh.filter(ImageFilter.GaussianBlur(d * 0.8))).convert("RGB"), (0, 0))
        pg = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(pg).polygon(points, fill=(*fill, 255))
        im.paste(Image.alpha_composite(im.convert("RGBA"), pg).convert("RGB"), (0, 0))

    sun = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sx = W * (0.74 if side != "right" else 0.26)
    ImageDraw.Draw(sun).ellipse([sx - W * 0.09, horizon * 0.22, sx + W * 0.09, horizon * 0.22 + W * 0.18], fill=(230, 168, 104, 255))
    im.paste(Image.alpha_composite(im.convert("RGBA"), sun).convert("RGB"), (0, 0))
    sheet_([(0, horizon * 0.88), (W * 0.3, horizon * 0.64), (W * 0.62, horizon * 0.9), (W, horizon * 0.72), (W, horizon), (0, horizon)], (158, 152, 126))
    sheet_([(0, horizon * 0.98), (W * 0.45, horizon * 0.8), (W, horizon * 0.95), (W, horizon + H * 0.03), (0, horizon + H * 0.03)], (120, 134, 104))

    # the skyline keeps clear of the side the character stands on
    lo, hi = (0.42, 0.98) if side == "left" else ((0.02, 0.58) if side == "right" else (0.06, 0.94))
    n = r.randint(5, 8)
    for i in range(n):
        x0 = W * (lo + (hi - lo) * i / n) + W * 0.004
        bw = W * (hi - lo) / n * r.uniform(0.6, 0.94)
        tall = r.uniform(0.1, 0.30) * (1.5 if vs and x0 > W * 0.55 else 1.0)
        top = horizon - H * tall
        sheet_([(x0, top), (x0 + bw, top), (x0 + bw, horizon + H * 0.02), (x0, horizon + H * 0.02)],
               r.choice([(206, 190, 162), (188, 170, 150), (172, 164, 158), (214, 198, 170)]))
        for wy in range(3):                                           # punched paper windows
            for wx in range(max(1, int(bw / (W * 0.035)))):
                px, py = x0 + W * 0.012 + wx * W * 0.035, top + H * 0.03 + wy * H * 0.045
                if py < horizon - H * 0.03:
                    ImageDraw.Draw(im).rectangle([px, py, px + W * 0.016, py + H * 0.022], fill=(96, 92, 84))
    sheet_([(0, horizon + H * 0.02), (W, horizon + H * 0.02), (W, H), (0, H)], (198, 178, 142), 0.016)

    a = np.asarray(im, dtype=np.float32) * 0.94 + np.array(CREAM, dtype=np.float32) * 0.06
    a += _grain(W, H, seed)
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    v = np.clip(((xx / W - 0.5) ** 2 + (yy / H - 0.5) ** 2) * 1.5, 0, 1)
    a *= (1 - 0.18 * v)[:, :, None]
    b = io.BytesIO()
    Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)).save(b, "PNG")
    return b.getvalue()


def sheet(cid: str) -> bytes | None:
    """The user's full model sheet (all angles, expressions, poses) - handed to the video model as a reference."""
    f = DIR / cid / "sheet.jpg"
    return f.read_bytes() if f.exists() else None
