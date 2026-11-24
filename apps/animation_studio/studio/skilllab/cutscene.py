"""The ASMR cutting shot, drawn in code: an object on a board, N knife strokes, a counter, then the slices fall apart.

It follows the Hinglish ASMR cutting guide: vertical 9:16, a wooden board, a steel knife, soft side light on a dark
ground, exactly N strokes, a counter that steps 0/N to N/N on contact, and the pieces falling after the last cut. The
guide drives Blender through Codex; this draws the same shot with Pillow, so it needs no Blender, no GPU and no model,
and one run costs nothing.

The object is drawn once into two layers -- the skin as seen from the side, and the flesh underneath -- and every slice
is a crop of those layers. That is what keeps the shading consistent across fifty pieces and lets a cut face appear in a
gap the moment two slices part, without drawing a single slice by hand.

Timing is the guide's own: the first impact lands about a second in and the rest follow a fixed beat, so a 50-cut
papaya comes out at a little over seventeen seconds, like the example in the guide.
"""
from __future__ import annotations

import math
import random
import re
from typing import Any

from PIL import Image, ImageChops, ImageDraw, ImageFilter

from .mgfx import FPS, SS, ease_out, fit, font, seg, text

INTRO = 1.2           # the whole object, counter at 0/N
GAP = 0.25            # one stroke every quarter second: the guide's six frames at 24 fps
AFTER = 0.9           # the beat after the last stroke, before anything moves
FALL = 1.9
OUTRO = 1.4
MAX_CUTS = 80

SHAPE_WORDS = (
    ("long", r"carrot|cucumber|banana|courgette|zucchini|baguette|chalk|candle|leek|celery|parsnip|plantain"),
    ("bar", r"soap|butter|cheese|chocolate|clay|tofu|brick|\bbar\b|block|sponge|eraser|fudge|halwa|barfi"),
    ("round", r"apple|orange|tomato|lemon|lime|onion|potato|kiwi|peach|egg|ball|beet|turnip|plum|guava"),
    ("tall", r"papaya|melon|cake|bread|loaf|pineapple|cabbage|lettuce|squash|pumpkin|mango|watermelon"),
)
SHAPES = ("round", "long", "bar", "tall")

# Skin, flesh and pip colours for the objects people actually ask for. Anything else gets the writer's own colours, and
# failing that the papaya, which is the guide's worked example.
PALETTE = {
    "papaya": ((126, 166, 74), (238, 132, 72), (38, 32, 36)),
    "watermelon": ((58, 110, 56), (226, 70, 84), (28, 26, 30)),
    "melon": ((206, 198, 142), (238, 168, 104), (226, 212, 160)),
    "mango": ((228, 166, 54), (244, 190, 78), (232, 206, 150)),
    "carrot": ((226, 118, 44), (240, 158, 86), (240, 176, 110)),
    "cucumber": ((78, 128, 62), (212, 228, 190), (170, 196, 150)),
    "apple": ((198, 54, 52), (244, 230, 192), (74, 56, 40)),
    "orange": ((234, 134, 42), (248, 178, 96), (248, 206, 150)),
    "lemon": ((234, 206, 68), (248, 236, 162), (240, 226, 150)),
    "tomato": ((206, 58, 48), (232, 110, 92), (238, 216, 140)),
    "onion": ((214, 178, 134), (246, 238, 226), (226, 212, 196)),
    "potato": ((178, 142, 100), (238, 224, 190), (222, 204, 166)),
    "banana": ((234, 206, 94), (248, 238, 206), (236, 224, 184)),
    "soap": ((126, 178, 206), (206, 230, 240), (206, 230, 240)),
    "butter": ((240, 220, 146), (248, 236, 184), (248, 236, 184)),
    "cheese": ((238, 196, 92), (248, 220, 138), (248, 230, 170)),
    "chocolate": ((88, 56, 38), (118, 78, 52), (142, 100, 68)),
    "bread": ((196, 146, 92), (244, 230, 198), (236, 218, 178)),
    "cake": ((238, 224, 212), (226, 162, 128), (248, 240, 232)),
    "clay": ((176, 126, 104), (206, 162, 140), (206, 162, 140)),
    "tofu": ((242, 238, 224), (248, 246, 236), (248, 246, 236)),
}
BOARD = (168, 124, 80)
BOARD_EDGE = (120, 84, 52)
STEEL = (208, 214, 222)


def shape_for(name: str) -> str:
    t = (name or "").lower()
    for shape, rx in SHAPE_WORDS:
        if re.search(rx, t):
            return shape
    return "tall"


def colours_for(name: str):
    t = (name or "").lower()
    for key, trio in PALETTE.items():
        if key in t:
            return trio
    return PALETTE["papaya"]


def _silhouette(w: int, h: int, shape: str) -> Image.Image:
    """An L mask: the object's profile from the side. Rounded ends, flat where it rests on the board."""
    m = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(m)
    if shape == "round":
        d.ellipse([0, 0, w - 1, h - 1], fill=255)
    elif shape == "bar":
        d.rounded_rectangle([0, 0, w - 1, h - 1], int(min(w, h) * 0.10), fill=255)
    elif shape == "long":
        r = h / 2
        d.rounded_rectangle([0, 0, w - 1, h - 1], int(r * 0.92), fill=255)
    else:                                                   # tall: a melon lying down, ends tapering
        r = h * 0.46
        d.rounded_rectangle([0, 0, w - 1, h - 1], int(r), fill=255)
        d.ellipse([-w * 0.04, h * 0.02, w * 0.30, h - 1], fill=255)
        d.ellipse([w * 0.70, h * 0.02, w * 1.04, h - 1], fill=255)
    return m


def _shade(w: int, h: int, base, lift: float = 1.26, drop: float = 0.52) -> Image.Image:
    """The body colour with the light coming from above and the left, so a crop of it reads as a solid object."""
    im = Image.new("RGB", (w, h))
    px = im.load()
    r, g, b = base
    for y in range(h):
        v = y / max(1, h - 1)
        k = lift + (drop - lift) * (v ** 0.82)
        row = (min(255, int(r * k)), min(255, int(g * k)), min(255, int(b * k)))
        for x in range(w):
            px[x, y] = row
    side = Image.new("L", (w, h))
    sp = side.load()
    for x in range(w):
        a = int(60 * max(0.0, (x / max(1, w - 1)) - 0.35) / 0.65)
        for y in range(h):
            sp[x, y] = a
    return Image.composite(Image.new("RGB", (w, h), (0, 0, 0)), im, side.point(lambda v: v // 2))


def _speckle(im: Image.Image, seed: int, n: int, colour, size: float) -> None:
    d = ImageDraw.Draw(im, "RGBA")
    r = random.Random(seed)
    w, h = im.size
    for _ in range(n):
        x, y = r.uniform(0, w), r.uniform(0, h)
        s = r.uniform(size * 0.5, size)
        d.ellipse([x - s, y - s, x + s, y + s], fill=colour + (r.randint(10, 26),))


def _body(w: int, h: int, shape: str, skin, seed: int) -> Image.Image:
    """The skin layer: shaded body, speckle, a soft specular band near the top."""
    mask = _silhouette(w, h, shape)
    im = _shade(w, h, skin).convert("RGBA")
    _speckle(im, seed, int(w * h / 9000), (255, 255, 255), max(1.0, w * 0.0022))
    _speckle(im, seed + 1, int(w * h / 14000), (0, 0, 0), max(1.0, w * 0.0024))
    gl = Image.new("L", (w, h), 0)
    ImageDraw.Draw(gl).ellipse([w * 0.08, h * 0.06, w * 0.62, h * 0.30], fill=92)
    im = Image.composite(Image.new("RGBA", (w, h), (255, 255, 255, 255)), im, gl.filter(ImageFilter.GaussianBlur(h * 0.07)))
    im.putalpha(mask)
    return im


def _inner(w: int, h: int, shape: str, flesh, pip, seed: int) -> Image.Image:
    """The flesh layer, seen when two slices part: a rind ring, flesh, and a pocket of pips down the middle."""
    mask = _silhouette(w, h, shape)
    im = _shade(w, h, flesh, 1.14, 0.70).convert("RGBA")
    d = ImageDraw.Draw(im, "RGBA")
    rind = mask.filter(ImageFilter.MinFilter(3))
    for _ in range(max(1, int(h * 0.012))):
        rind = rind.filter(ImageFilter.MinFilter(3))
    ring = ImageChops.subtract(mask, rind)
    im.paste(Image.new("RGBA", (w, h), tuple(int(c * 0.72) for c in flesh) + (255,)), (0, 0), ring)
    if shape in ("tall", "round"):
        d.ellipse([w * 0.26, h * 0.26, w * 0.74, h * 0.76], fill=tuple(int(c * 0.84) for c in flesh) + (255,))
        r = random.Random(seed)
        for _ in range(26):
            a, rr = r.uniform(0, math.tau), r.uniform(0, 1) ** 0.5
            cx, cy = w * 0.5 + math.cos(a) * rr * w * 0.19, h * 0.5 + math.sin(a) * rr * h * 0.21
            s = r.uniform(h * 0.012, h * 0.024)
            d.ellipse([cx - s, cy - s, cx + s, cy + s], fill=pip + (255,))
    im.putalpha(mask)
    return im


def _board(W: int, H: int, seed: int) -> Image.Image:
    """Dark room, one warm pool of light, a thick wooden board seen from a little above."""
    im = Image.new("RGB", (W, H), (13, 12, 14))
    pool = Image.new("L", (W, H), 0)
    ImageDraw.Draw(pool).ellipse([-W * 0.35, H * 0.34, W * 1.22, H * 0.96], fill=170)
    im = Image.composite(Image.new("RGB", (W, H), (62, 55, 52)), im, pool.filter(ImageFilter.GaussianBlur(H * 0.055)))
    d = ImageDraw.Draw(im, "RGBA")
    x0, x1 = W * 0.045, W * 0.955
    top, face, bot = H * 0.598, H * 0.760, H * 0.806
    d.rounded_rectangle([x0 - W * 0.01, top, x1 + W * 0.01, bot + H * 0.012], int(H * 0.012), fill=(0, 0, 0, 130))
    d.rounded_rectangle([x0, face - H * 0.02, x1, bot], int(H * 0.010), fill=BOARD_EDGE)
    d.rounded_rectangle([x0, top, x1, face], int(H * 0.008), fill=BOARD)
    g = random.Random(seed)
    gd = ImageDraw.Draw(im, "RGBA")
    for _ in range(120):
        y = g.uniform(top + 4, face - 4)
        wdt = g.uniform((x1 - x0) * 0.18, (x1 - x0) * 0.86)
        x = g.uniform(x0, x1 - wdt)
        gd.line([(x, y), (x + wdt, y + g.uniform(-2.5, 2.5))], fill=(64, 40, 20, g.randint(10, 30)), width=g.choice([1, 1, 2]))
    sh = Image.new("L", (W, H), 0)
    ImageDraw.Draw(sh).rectangle([x0, top, x1, face], fill=0)
    lit = Image.new("L", (W, H), 0)
    ImageDraw.Draw(lit).ellipse([-W * 0.2, top - H * 0.08, W * 0.92, face + H * 0.05], fill=70)
    im = Image.composite(Image.new("RGB", (W, H), (255, 246, 232)), im, lit.filter(ImageFilter.GaussianBlur(H * 0.04)).point(lambda v: v // 3))
    d.rounded_rectangle([x0, top, x1, face], int(H * 0.008), outline=(92, 62, 36, 150), width=max(2, int(H * 0.0012)))
    return im


def scene(spec: dict, w: int, h: int):
    """Returns (seconds, draw, (bg, size), impacts) -- the first three the way mgfx.frames_of wants them."""
    W, H = w * SS, h * SS
    n = max(1, min(MAX_CUTS, int(spec.get("cuts") or 12)))
    name = str(spec.get("object") or "papaya").strip() or "papaya"
    shape = spec.get("shape") if spec.get("shape") in SHAPES else shape_for(name)
    skin, flesh, pip = colours_for(name)
    skin = tuple(spec.get("skin") or skin)
    flesh = tuple(spec.get("flesh") or flesh)
    pip = tuple(spec.get("seeds") or pip)
    mark = str(spec.get("watermark") or "").strip()
    gap = max(0.12, float(spec.get("gap") or GAP))
    impacts = [INTRO + i * gap for i in range(n)]
    last = impacts[-1]
    seconds = last + AFTER + FALL + OUTRO
    seed = sum(ord(c) for c in name) + n

    # width across the frame, then height as a fraction of that width: an apple is small and round, a carrot long and thin
    wide, tall_ = {"round": (0.36, 0.98), "long": (0.74, 0.20), "bar": (0.56, 0.36), "tall": (0.62, 0.47)}[shape]
    ow = int(W * wide)
    oh = int(ow * tall_)
    ox0 = (W - ow) // 2
    oy1 = int(H * 0.726)                                     # resting on the board's top face
    oy0 = oy1 - oh
    body = _body(ow, oh, shape, skin, seed)
    inner = _inner(ow, oh, shape, flesh, pip, seed)
    back = _board(W, H, seed)
    contact = Image.new("L", (W, H), 0)
    ImageDraw.Draw(contact).ellipse([ox0 + ow * 0.02, oy1 - oh * 0.06, ox0 + ow * 0.98, oy1 + oh * 0.14], fill=140)
    back = Image.composite(Image.new("RGB", (W, H), (26, 18, 12)), back, contact.filter(ImageFilter.GaussianBlur(oh * 0.09)))

    edge = [round(ow * (i + 1) / (n + 1)) for i in range(n)]  # cut positions inside the body layer
    seam = max(2, int(W * 0.0024))
    face_max = max(4, int(W * 0.014))
    rng = random.Random(seed)
    lean = [0.82 + rng.uniform(-0.12, 0.14) for _ in range(n + 2)]
    dark = tuple(int(c * 0.42) for c in skin)
    counter_size = int(H * 0.050)
    label_size = int(H * 0.022)
    TOPPLE = 56.0                                            # how far over a slice tips once it has fallen

    def turned(card: Image.Image, deg: float):
        """The card turned clockwise about its bottom-right corner. Returns the image and where that corner went."""
        out = card.rotate(-deg, resample=Image.BILINEAR, expand=True)
        w0, h0 = card.size
        a = math.radians(-deg)
        dx, dy = w0 / 2, h0 / 2
        return out, (out.width / 2 + dx * math.cos(a) + dy * math.sin(a),
                     out.height / 2 - dx * math.sin(a) + dy * math.cos(a))

    def standing(im: Image.Image, done: int) -> None:
        """Before the fall nothing moves: the object is whole and each finished cut is a seam in its skin."""
        im.paste(body, (ox0, oy0), body)
        if not done:
            return
        lay = Image.new("RGBA", (ow, oh), (0, 0, 0, 0))
        ld = ImageDraw.Draw(lay, "RGBA")
        for i in range(done):
            x = edge[i]
            ld.line([(x, 0), (x, oh)], fill=dark + (236,), width=seam)
            ld.line([(x + seam, 0), (x + seam, oh)], fill=(255, 255, 255, 44), width=max(1, seam // 2))
        lay.putalpha(ImageChops.multiply(lay.getchannel("A"), body.getchannel("A")))
        im.paste(lay, (ox0, oy0), lay)

    def toppled(im: Image.Image, bounds: list, fall: float) -> None:
        """The slices go over like dominoes, left first, each leaning on the one to its right, cut faces turning up."""
        open_ = ease_out(min(1.0, fall / 0.85))
        slide = -oh * 0.34 * open_                            # tipping right throws the fan right, so walk it back
        mid = (len(bounds) - 2) / 2
        for k in range(len(bounds) - 2, -1, -1):             # rightmost first, so the left slice lies on top of it
            a, b = bounds[k], bounds[k + 1]
            if b - a < 1:
                continue
            f = max(0.0, fall - k * 0.028)
            deg = TOPPLE * lean[k] * ease_out(min(1.0, f / 0.80))
            g = max(1, round((b - a) * 0.95 * open_))        # a cut face is as wide as the slice is thick
            spread = (k - mid) * (b - a) * 0.26 * open_      # and they slide apart, the way a real fan does
            src = max(3, (b - a) // 2)
            strip = inner.crop((a, 0, min(ow, a + src), oh)).resize((g, oh), Image.BILINEAR) if k else None
            cut = body.crop((a, 0, b, oh))
            card = Image.new("RGBA", ((g if strip else 0) + cut.width, oh), (0, 0, 0, 0))
            if strip:
                card.paste(strip, (0, 0))
            card.paste(cut, (card.width - cut.width, 0), cut)
            img, (px, py) = turned(card, deg)
            im.paste(img, (int(ox0 + b - px + slide + spread), int(oy1 - py)), img)

    face_w = max(3, int(W * 0.010))
    rng = random.Random(seed)
    sway = [rng.uniform(-1, 1) for _ in range(n + 1)]
    counter_size = int(H * 0.050)
    label_size = int(H * 0.022)

    def draw(t: float, _d: ImageDraw.ImageDraw, im: Image.Image) -> None:
        im.paste(back, (0, 0))
        done = sum(1 for x in impacts if t >= x)
        fall = max(0.0, t - (last + AFTER))
        bounds = [0] + edge[:done] + [ow]
        if fall > 0 and done:
            toppled(im, bounds, fall)
        else:
            standing(im, done)
        held = next(((x, i) for i, x in enumerate(impacts) if 0 <= t - x < 0.10), None)
        nxt = next(((x, i) for i, x in enumerate(impacts) if x > t), None)
        if fall <= 0 and (held or nxt):
            if held:                                         # the blade rests in the cut for a beat before it lifts
                _, i = held
                k, rise = 1.0, 0.0
            else:
                _, i = nxt
                k, rise = seg(t, nxt[0] - gap * 0.86, nxt[0]), 0.0
            kx = ox0 + edge[i]
            tip = oy0 - H * 0.085 + (H * 0.085 + oh * 0.30) * ease_out(k) - rise
            bw, bl = W * 0.030, H * 0.175
            d = ImageDraw.Draw(im, "RGBA")
            d.polygon([(kx - bw, tip - bl), (kx + bw, tip - bl), (kx + bw * 0.55, tip - bl * 0.06), (kx - bw * 0.1, tip)], fill=STEEL)
            d.polygon([(kx - bw, tip - bl), (kx - bw * 0.42, tip - bl), (kx - bw * 0.42, tip - bl * 0.10), (kx - bw * 0.1, tip)], fill=(240, 245, 250))
            d.polygon([(kx - bw, tip - bl), (kx - bw * 0.80, tip - bl), (kx - bw * 0.80, tip - bl * 0.08), (kx - bw * 0.1, tip)], fill=(150, 160, 172))
            d.rounded_rectangle([kx - bw * 0.80, tip - bl - H * 0.072, kx + bw * 0.80, tip - bl + H * 0.004], int(H * 0.006), fill=(38, 34, 38))
            d.rounded_rectangle([kx - bw * 0.86, tip - bl - H * 0.006, kx + bw * 0.86, tip - bl + H * 0.006], int(H * 0.003), fill=(176, 180, 188))
        flash = next((1 - seg(t, x, x + 0.09) for x in impacts if 0 <= t - x < 0.09), 0.0)
        if flash and fall <= 0 and done:
            d = ImageDraw.Draw(im, "RGBA")
            kx = ox0 + edge[done - 1]
            d.line([(kx, oy0 + oh * 0.06), (kx, oy1)], fill=(255, 255, 255, int(170 * flash)), width=max(2, int(W * 0.0035)))
        d = ImageDraw.Draw(im, "RGBA")
        pop = 1.0 + 0.12 * flash
        s = fit(d, f"{done}/{n}", int(counter_size * pop), W * 0.46)
        text(d, (W / 2, H * 0.138), f"{done}/{n}", s, (250, 248, 246))
        text(d, (W / 2, H * 0.188), name.upper(), label_size, (250, 248, 246, 140), spacing=W * 0.004)
        if mark:
            text(d, (W / 2, H * 0.905), mark, int(H * 0.016), (255, 255, 255, 86), bold=False)

    return seconds, draw, ((13, 12, 14), (w, h)), impacts
