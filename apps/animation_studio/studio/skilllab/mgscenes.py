"""The four motion-graphics scenes. Each returns (seconds, draw) for mgfx.frames_of.

Ported from the three.js/GSAP originals in github.com/artemnovitckii/claude-animation-skills (MIT, Artem Novitckii):
same shots and timing, drawn with Pillow instead. The 3D ones become isometric, which reads better at reels size anyway.
"""
from __future__ import annotations

import math
from typing import Any, Callable

from PIL import Image, ImageDraw, ImageFilter

from .mgfx import (ACCENT, INK, PAPER, SAFE_BOTTOM, SAFE_TOP, SS, along, card, ease, ease_out, fit, font, iso, number,
                   seg, smooth, spring, text, wrap)

Scene = tuple[float, Callable[[float, ImageDraw.ImageDraw, Image.Image], None], Any]


# ---------------------------------------------------------------- 1. graph
def graph(spec: dict, w: int, h: int) -> Scene:
    """A smooth line draws itself while one big number counts up with its tip, then lands."""
    W, H = w * SS, h * SS
    vals = [float(x) for x in spec["values"]]
    dark = bool(spec.get("dark"))
    bg, ink = (INK, PAPER) if dark else (PAPER, INK)
    lo, hi = min(min(vals), 0.0), max(vals)
    span = (hi - lo) or 1.0
    x0, x1 = W * 0.13, W * 0.87
    y0, y1 = H * 0.34, H * 0.66
    pts = [(x0 + (x1 - x0) * (i / max(1, len(vals) - 1)), y1 - (y1 - y0) * ((v - lo) / span)) for i, v in enumerate(vals)]
    path = smooth(pts)
    final = float(spec.get("final") or vals[-1])
    DRAW, HOLD = 2.6, 1.6
    gr = int(H * 0.045)                                   # the tip's glow, drawn once and pasted
    glow = Image.new("RGBA", (gr * 2, gr * 2), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse([gr * 0.45, gr * 0.45, gr * 1.55, gr * 1.55], fill=(*ACCENT, 80))
    glow = glow.filter(ImageFilter.GaussianBlur(gr * 0.30))

    def d_(t: float, d: ImageDraw.ImageDraw, im: Image.Image) -> None:
        k = ease(seg(t, 0.25, 0.25 + DRAW))
        d.line([(x0, y1 + H * 0.012), (x1, y1 + H * 0.012)], fill=(*ink, 38), width=max(2, int(H * 0.0018)))
        if spec.get("label"):
            s = fit(d, spec["label"], int(H * 0.030), (x1 - x0))
            text(d, (W / 2, H * SAFE_TOP + H * 0.045), spec["label"], s, (*ink, 150), spacing=H * 0.004)
        if k > 0:
            part = along(path, k)
            if len(part) > 1:
                d.line(part, fill=ink, width=max(3, int(H * 0.0055)), joint="curve")
            tip = part[-1]
            im.paste(glow, (int(tip[0] - gr), int(tip[1] - gr)), glow)
            r = H * 0.0075
            d.ellipse([tip[0] - r, tip[1] - r, tip[0] + r, tip[1] + r], fill=ACCENT)
            shown = lo + (final - lo) * k if k < 1 else final
            land = spring(seg(t, 0.25 + DRAW, 0.25 + DRAW + 0.5)) if k >= 1 else 0.0
            size = int(H * (0.105 + 0.012 * land))
            s = number(shown, int(spec.get("decimals") or 0), spec.get("prefix") or "", spec.get("suffix") or "")
            size = fit(d, s, size, W * 0.8)
            text(d, (W / 2, y1 + H * 0.115), s, size, ink)
        for i, lab in enumerate((spec.get("labels") or [])[: len(pts)]):
            if seg(t, 0.25 + DRAW * (i / max(1, len(pts) - 1)), 0.25 + DRAW * (i / max(1, len(pts) - 1)) + 0.3) > 0:
                text(d, (pts[i][0], y1 + H * 0.038), str(lab), int(H * 0.020), (*ink, 130))

    return 0.25 + DRAW + HOLD, d_, (bg, (w, h))


# ---------------------------------------------------------------- 2. line art
def lineart(spec: dict, w: int, h: int) -> Scene:
    """Hairline steps rise, a dot hops up them, an orbit draws at the top, one quiet line of text."""
    W, H = w * SS, h * SS
    n = max(3, min(7, int(spec.get("steps") or 5)))
    line = str(spec.get("line") or "")
    second = str(spec.get("second") or "")
    bw, bh = W * 0.112, H * 0.034
    base_y, base_x = H * 0.68, W / 2 - (n * bw) / 2
    steps = [(base_x + i * bw, base_y - (i + 1) * bh) for i in range(n)]
    RISE, HOP = 1.5, 2.2

    def d_(t: float, d: ImageDraw.ImageDraw, im: Image.Image) -> None:
        lw = max(2, int(H * 0.0024))
        for i, (sx, sy) in enumerate(steps):
            a = ease_out(seg(t, 0.15 + i * (RISE / n), 0.15 + i * (RISE / n) + 0.45))
            if a <= 0:
                continue
            drop = (1 - a) * H * 0.045
            top, right = sy + drop, sx + bw
            d.line([(sx, top), (right, top)], fill=(255, 255, 255, int(210 * a)), width=lw)          # the tread
            if i < n - 1:
                d.line([(right, top), (right, top - bh)], fill=(255, 255, 255, int(150 * a)), width=lw)  # the riser up to the next tread
            if i == 0:
                d.line([(sx, top), (sx, base_y + bh * 0.2)], fill=(255, 255, 255, int(90 * a)), width=lw)
        d.line([(base_x, base_y + bh * 0.2), (base_x + n * bw, base_y + bh * 0.2)], fill=(255, 255, 255, 60), width=lw)
        hp = seg(t, 0.15 + RISE * 0.55, 0.15 + RISE * 0.55 + HOP)
        if hp > 0:
            f = hp * (n - 1)
            i = min(n - 2, int(f)) if n > 1 else 0
            u = f - i if n > 1 else 1.0
            u = min(1.0, max(0.0, u))
            a, b = steps[i], steps[min(n - 1, i + 1)]
            x = a[0] + (b[0] - a[0]) * u + bw / 2
            y = a[1] + (b[1] - a[1]) * ease(u) - math.sin(min(1.0, u) * math.pi) * H * 0.05 - H * 0.012
            r = H * 0.011
            d.ellipse([x - r, y - r, x + r, y + r], fill=(255, 255, 255, 255))
            o = seg(t, 0.15 + RISE * 0.55 + HOP, 0.15 + RISE * 0.55 + HOP + 0.8)
            if o > 0:
                rr = H * 0.055
                d.arc([x - rr, y - rr * 0.62, x + rr, y + rr * 0.62], -90, -90 + 360 * ease_out(o),
                      fill=(255, 255, 255, 170), width=lw)
        swap = 0.15 + RISE * 0.55 + HOP + 0.45
        which = line if t < swap or not second else second
        fade = min(1.0, seg(t, 0.4, 1.0) if which == line else seg(t, swap, swap + 0.4))
        if fade > 0 and which:
            size = int(H * 0.030)
            rows = wrap(d, which.lower(), size, W * 0.74, bold=False)
            for j, row in enumerate(rows[:2]):
                text(d, (W / 2, H * 0.825 + j * size * 1.35), row, size, (255, 255, 255, int(205 * fade)), bold=False)

    return 0.15 + RISE * 0.55 + HOP + 1.5, d_, ((8, 8, 10), (w, h))


# ---------------------------------------------------------------- 3. map route
def route(spec: dict, w: int, h: int) -> Scene:
    """A white isometric city, a route that draws itself, a pin that drops, an ETA that counts down."""
    W, H = w * SS, h * SS
    frm, to = str(spec.get("from") or "Start"), str(spec.get("to") or "Destination")
    km, mins = float(spec.get("km") or 0), int(spec.get("minutes") or 0)
    rng = __import__("random").Random(len(frm) * 31 + len(to) * 17 + int(km * 10))
    scale, ox, oy = W * 0.055, W * 0.5, H * 0.46
    blocks = []
    for gx in range(-5, 6):
        for gy in range(-5, 6):
            if abs(gx) + abs(gy) > 8 or (gx % 3 == 0 and gy % 3 == 0):
                continue
            blocks.append((gx, gy, rng.uniform(0.25, 1.5), rng.random() < 0.14))
    blocks.sort(key=lambda b: b[0] + b[1])
    way = [(-4.4, 4.0), (-3.6, 1.6), (-1.4, 0.9), (-0.2, -1.4), (1.9, -2.0), (2.6, -4.2)]
    path = smooth([iso(x, y, 0.06, ox, oy, scale) for x, y in way], per=18)
    DRAW = 3.2

    def d_(t: float, d: ImageDraw.ImageDraw, im: Image.Image) -> None:
        for gx, gy, hgt, park in blocks:
            top = [iso(gx + dx, gy + dy, hgt, ox, oy, scale) for dx, dy in ((0, 0), (1, 0), (1, 1), (0, 1))]
            if park:
                d.polygon([iso(gx + dx, gy + dy, 0.04, ox, oy, scale) for dx, dy in ((0, 0), (1, 0), (1, 1), (0, 1))], fill=(214, 229, 212))
                continue
            d.polygon([iso(gx + dx, gy + dy, 0, ox, oy, scale) for dx, dy in ((0, 0), (1, 0), (1, 1), (0, 1))], fill=(226, 226, 228))
            d.polygon([top[0], top[1], iso(gx + 1, gy, 0, ox, oy, scale), iso(gx, gy, 0, ox, oy, scale)], fill=(236, 236, 238))
            d.polygon([top[1], top[2], iso(gx + 1, gy + 1, 0, ox, oy, scale), iso(gx + 1, gy, 0, ox, oy, scale)], fill=(214, 214, 217))
            d.polygon(top, fill=(249, 249, 250), outline=(228, 228, 231))
        k = ease(seg(t, 0.5, 0.5 + DRAW))
        if k > 0:
            part = along(path, k)
            if len(part) > 1:
                d.line(part, fill=(*ACCENT, 90), width=max(8, int(H * 0.012)), joint="curve")
                d.line(part, fill=ACCENT, width=max(4, int(H * 0.0055)), joint="curve")
            sx, sy = path[0]
            d.ellipse([sx - H * 0.009, sy - H * 0.009, sx + H * 0.009, sy + H * 0.009], fill=INK)
        p = spring(seg(t, 0.5 + DRAW * 0.9, 0.5 + DRAW * 0.9 + 0.7))
        if p > 0:
            px, py = path[-1]
            py -= (1 - min(1.0, p)) * H * 0.18
            r = H * 0.019
            d.ellipse([px - r, py - r * 2.3, px + r, py - r * 0.3], fill=ACCENT)
            d.polygon([(px - r * 0.62, py - r * 0.75), (px + r * 0.62, py - r * 0.75), (px, py + r * 0.5)], fill=ACCENT)
            d.ellipse([px - r * 0.3, py - r * 1.55, px + r * 0.3, py - r * 0.95], fill=PAPER)
        if mins:
            done = ease(seg(t, 0.5, 0.5 + DRAW)) >= 1
            left = max(1, round(mins * (1 - ease(seg(t, 0.5, 0.5 + DRAW)))))
            label = "Arrived" if done else (f"{left} min   ·   {km:g} km" if km else f"{left} min")
            box = [W * 0.30, H * SAFE_TOP + H * 0.02, W * 0.70, H * SAFE_TOP + H * 0.085]
            card(d, box, int(H * 0.016), PAPER, shadow=int(H * 0.004))
            text(d, (W / 2, (box[1] + box[3]) / 2), label, int(H * 0.026), INK)
        a = ease_out(seg(t, 0.5 + DRAW, 0.5 + DRAW + 0.6))
        if a > 0:
            box = [W * 0.14, H * 0.76, W * 0.86, H * 0.76 + H * 0.085]
            card(d, [box[0], box[1] + (1 - a) * H * 0.05, box[2], box[3] + (1 - a) * H * 0.05], int(H * 0.016), INK)
            s = fit(d, to.upper(), int(H * 0.028), (box[2] - box[0]) * 0.86)
            text(d, (W / 2, (box[1] + box[3]) / 2 + (1 - a) * H * 0.05), to.upper(), s, PAPER, spacing=H * 0.003)
        if t < 1.0:
            s = fit(d, frm.upper(), int(H * 0.024), W * 0.6)
            text(d, (W / 2, H * 0.72), frm.upper(), s, (*INK, int(160 * (1 - seg(t, 0.6, 1.0)))), spacing=H * 0.003)

    return 0.5 + DRAW + 1.8, d_, ((243, 243, 245), (w, h))


# ---------------------------------------------------------------- 4. breakdown
def breakdown(spec: dict, w: int, h: int) -> Scene:
    """A device floats on a dark studio backdrop and comes apart layer by layer, each part labelled."""
    W, H = w * SS, h * SS
    parts = [p for p in (spec.get("parts") or []) if str(p.get("name") or "").strip()][:6] or [{"name": "Body"}]
    title = str(spec.get("title") or "")
    n = len(parts)
    cx, cy = W * 0.40, H * 0.50
    bw, bh = W * 0.28, H * 0.055
    gap = H * 0.098
    SPREAD = 2.6
    g = Image.new("L", (W, H), 0)
    ImageDraw.Draw(g).ellipse([W * 0.02, H * 0.20, W * 0.98, H * 0.84], fill=120)
    BACK = Image.composite(Image.new("RGB", (W, H), (34, 36, 44)), Image.new("RGB", (W, H), (10, 11, 14)),
                           g.filter(ImageFilter.GaussianBlur(H * 0.06)))

    def d_(t: float, d: ImageDraw.ImageDraw, im: Image.Image) -> None:
        im.paste(BACK, (0, 0))
        d = ImageDraw.Draw(im, "RGBA")
        if title:
            s = fit(d, title.upper(), int(H * 0.026), W * 0.8)
            text(d, (W / 2, H * SAFE_TOP + H * 0.035), title.upper(), s, (235, 235, 240, 170), spacing=H * 0.004)
        spin = ease(seg(t, 0.6, 0.6 + SPREAD))
        for i, p in enumerate(parts):
            at = 0.6 + i * (SPREAD / n) * 0.8
            k = ease_out(seg(t, at, at + 0.8))
            y = cy + (i - (n - 1) / 2) * gap * k
            lift = (1 - k) * H * 0.012 * (i - (n - 1) / 2)
            box = [cx - bw / 2, y - bh / 2 + lift, cx + bw / 2, y + bh / 2 + lift]
            shade = 70 + i * 22
            d.rounded_rectangle([box[0] + H * 0.004, box[1] + H * 0.006, box[2] + H * 0.004, box[3] + H * 0.006], int(H * 0.012), fill=(0, 0, 0, 90))
            d.rounded_rectangle(box, int(H * 0.012), fill=(shade, shade + 4, shade + 10), outline=(255, 255, 255, 40), width=max(1, int(H * 0.0012)))
            d.rounded_rectangle([box[0] + bw * 0.06, box[1] + bh * 0.16, box[2] - bw * 0.06, box[1] + bh * 0.42], int(H * 0.004),
                                fill=(255, 255, 255, 18))
            la = ease_out(seg(t, at + 0.35, at + 1.0))
            if la > 0 and spin >= 0:
                lx = box[2] + W * 0.03
                ex = lx + (W * 0.17) * la
                d.line([(box[2], y + lift), (lx, y + lift), (ex, y + lift)], fill=(255, 255, 255, int(120 * la)), width=max(1, int(H * 0.0012)))
                d.ellipse([box[2] - H * 0.004, y + lift - H * 0.004, box[2] + H * 0.004, y + lift + H * 0.004], fill=(255, 255, 255, int(200 * la)))
                s = fit(d, str(p["name"]), int(H * 0.021), W * 0.30)
                text(d, (ex + W * 0.01, y + lift), str(p["name"]), s, (240, 240, 245, int(230 * la)), anchor="lm", bold=False)

    return 0.6 + SPREAD + 1.6, d_, ((10, 11, 14), (w, h))


SCENES = {"graph": graph, "lineart": lineart, "route": route, "breakdown": breakdown}
