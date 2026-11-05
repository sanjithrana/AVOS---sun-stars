"""Procedural settings (rooms, streets, parks, beaches, night skies, stages, abstract motion-graphics fields).

Drawn in layers with parallax: the caller sets the camera for each layer. World units are pixels of the base frame.
"""
from __future__ import annotations

import math
import random
import re
import zlib

import skia

from .color import mix, shade, skc
from .rig import _oval, _star

SETTINGS = ("room", "bedroom", "kitchen", "office", "classroom", "cafe", "street", "city", "park", "forest", "mountains",
            "beach", "sky", "space", "stage", "abstract", "plain")
SETTING_WORDS = {
    "bedroom": r"bedroom|臥室|卧室|房間|房间|bed\b", "kitchen": r"kitchen|廚房|厨房|cook", "office": r"office|work|辦公|办公|公司|desk",
    "classroom": r"class|school|學校|学校|教室|teacher|老師", "cafe": r"cafe|café|coffee shop|咖啡店|咖啡廳|restaurant|餐廳",
    "street": r"street|road|sidewalk|街|路上|馬路|town|小鎮|outside|outdoors|出門|門外", "city": r"city|downtown|城市|都市|skyline|building",
    "park": r"park|garden|公園|花園|picnic|grass|草地", "forest": r"forest|woods|森林|樹林|jungle", "mountains": r"mountain|hill|山|hike|登山",
    "beach": r"beach|sea|ocean|海|沙灘|wave|island", "sky": r"sky|fly|flying|天空|飛|cloud", "space": r"space|planet|galaxy|宇宙|太空|星球|astronaut",
    "stage": r"stage|concert|show|舞台|演唱|spotlight|perform", "room": r"room|home|house|屋|家裡|家里|indoor|living",
    "abstract": r"abstract|logo|title card|字卡|intro|outro|motion graphic|product|app|feature",
}


def guess_setting(text: str, default: str = "room") -> str:
    low = (text or "").lower()
    best = None
    for k, pat in SETTING_WORDS.items():
        m = re.search(pat, low)
        if m and (best is None or m.start() < best[0]):
            best = (m.start(), k)
    return best[1] if best else default


def guess_time(text: str) -> str:
    low = (text or "").lower()
    if re.search(r"night|midnight|evening|dark|夜|晚上|深夜|星空", low):
        return "night"
    if re.search(r"sunset|dusk|golden hour|黃昏|夕陽|傍晚", low):
        return "sunset"
    return "day"


def _rect(c: skia.Canvas, l, t, r, b, color, alpha=1.0, aa=True):
    c.drawRect(skia.Rect.MakeLTRB(l, t, r, b), skia.Paint(AntiAlias=aa, Color=skc(color, alpha)))


def _grad(c: skia.Canvas, l, t, r, b, top, bot):
    p = skia.Paint(AntiAlias=True)
    p.setShader(skia.GradientShader.MakeLinear([skia.Point(0, t), skia.Point(0, b)], [skc(top), skc(bot)]))
    c.drawRect(skia.Rect.MakeLTRB(l, t, r, b), p)


def sky_colors(roles: dict, time: str, look: str) -> tuple[str, str]:
    if time == "night":
        return "#141A3A", "#2B2F5E"
    if time == "sunset":
        return "#FF9E7A", "#FFD39B"
    return mix("#8FD3FF", roles["sky_top"], 0.35), mix("#E8F7FF", roles["sky_bot"], 0.35)


class Background:
    """Draws one setting. `draw(layer, ...)` is called with the camera already applied for that layer."""

    LAYERS = (("back", 0.15), ("far", 0.45), ("mid", 0.8), ("ground", 1.0))

    def __init__(self, setting: str, roles: dict, time: str, W: int, H: int, lk: dict, seed: int = 1, details: list[str] | None = None,
                 no_sky: set | None = None):
        self.s = setting if setting in SETTINGS else "room"
        self.roles, self.time, self.W, self.H, self.lk = roles, time, W, H, lk
        self.rng = random.Random(seed)
        self.seed = seed
        self.ground_y = H * 0.86
        self.white = lk["look"] == "whiteboard"
        self.details = details or []
        self.no_sky = set(no_sky or [])     # the shot has its own moon/sun prop: don't draw a second one

    # ---------- helpers ----------
    def _x0(self) -> float:
        return -self.W * 0.8

    def _x1(self) -> float:
        return self.W * 1.8

    def draw(self, layer: str, c: skia.Canvas, pen, t: float) -> None:
        fn = getattr(self, f"_{self._family()}_{layer}", None)
        if fn:
            rng_state = random.Random(self.seed * 31 + zlib.crc32(layer.encode()) % 997)
            fn(c, pen, t, rng_state)

    def _family(self) -> str:
        s = self.s
        if s in ("room", "bedroom", "kitchen", "office", "classroom", "cafe"):
            return "interior"
        if s in ("street", "city"):
            return "city"
        if s in ("park", "forest", "mountains"):
            return "nature"
        return s

    # ---------- interior ----------
    def _interior_back(self, c, pen, t, rng):
        H, W, r = self.H, self.W, self.roles
        wall = "#FFFFFF" if self.white else (mix(r["wall"], "#1B1E3A", 0.45) if self.time == "night" else r["wall"])
        _rect(c, self._x0(), -H, self._x1(), self.ground_y, wall)
        if not self.white:
            p = skia.Paint(AntiAlias=True, Color=skc(shade(wall, -0.04), 0.6))
            for i in range(-6, 14):
                x = i * W * 0.11
                c.drawRect(skia.Rect.MakeLTRB(x, -H, x + W * 0.04, self.ground_y), p)
        # window with the outside world
        wx, wy, ww, wh = W * 0.62, H * 0.16, W * 0.24, H * 0.36
        top, bot = sky_colors(r, self.time, self.lk["look"])
        win = skia.Path()
        win.addRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(wx, wy, ww, wh), 6, 6))
        if self.white:
            pen.shape(win, "#FFFFFF", 3)
        else:
            c.save()
            c.clipPath(win, doAntiAlias=True)
            _grad(c, wx, wy, wx + ww, wy + wh, top, bot)
            if self.time == "night":
                for i in range(12):
                    c.drawCircle(wx + rng.random() * ww, wy + rng.random() * wh * 0.7, 1.4, skia.Paint(AntiAlias=True, Color=skc("#FFFFFF", 0.8)))
                c.drawCircle(wx + ww * 0.72, wy + wh * 0.25, ww * 0.09, skia.Paint(AntiAlias=True, Color=skc("#FFE9A8")))
            else:
                c.drawCircle(wx + ww * 0.75, wy + wh * 0.28, ww * 0.1, skia.Paint(AntiAlias=True, Color=skc("#FFE066" if self.time == "day" else "#FF8A5B")))
                for k in range(2):
                    cx = wx + ((t * 8 + k * ww * 0.6) % (ww + 80)) - 40
                    for dx, dy, rr in ((0, 0, 16), (16, -6, 20), (34, 0, 15)):
                        c.drawCircle(cx + dx, wy + wh * (0.55 + 0.15 * k) + dy, rr, skia.Paint(AntiAlias=True, Color=skc("#FFFFFF", 0.9)))
            c.restore()
            pen.outline(win, 2.6)
            fr = skia.Path()
            fr.moveTo(wx + ww / 2, wy)
            fr.lineTo(wx + ww / 2, wy + wh)
            fr.moveTo(wx, wy + wh / 2)
            fr.lineTo(wx + ww, wy + wh / 2)
            pen.line(fr, "#FFFFFF", 6)
            # curtains
            for side in (-1, 1):
                cur = skia.Path()
                x = wx - 10 if side < 0 else wx + ww + 10
                sway = 3 * math.sin(t * 1.2 + side)
                cur.moveTo(x, wy - 14)
                cur.lineTo(x - side * ww * 0.18, wy - 14)
                cur.cubicTo(x - side * ww * 0.12 + sway, wy + wh * 0.4, x - side * ww * 0.2 + sway, wy + wh * 0.8, x - side * ww * 0.1 + sway, wy + wh + 18)
                cur.lineTo(x + side * 6, wy + wh + 18)
                cur.close()
                pen.shape(cur, r["accent2"], 2.4)
        # wall decoration by room type
        s = self.s
        if s == "classroom":
            bb = skia.Path()
            bb.addRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(W * 0.08, H * 0.14, W * 0.4, H * 0.3), 4, 4))
            pen.shape(bb, "#2F5D4A" if not self.white else "#FFFFFF", 3)
            ln = skia.Path()
            ln.moveTo(W * 0.12, H * 0.22)
            ln.cubicTo(W * 0.2, H * 0.18, W * 0.26, H * 0.28, W * 0.34, H * 0.22)
            pen.line(ln, "#FFFFFF" if not self.white else "#232327", 2.5, 0.8)
        elif s in ("room", "bedroom", "office", "cafe"):
            fr = skia.Path()
            fr.addRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(W * 0.2, H * 0.18, W * 0.13, H * 0.17), 3, 3))
            pen.shape(fr, r["accent"] if not self.white else "#FFFFFF", 3)
            inner = skia.Path()
            inner.addRect(skia.Rect.MakeXYWH(W * 0.215, H * 0.2, W * 0.1, H * 0.13))
            pen.fill(inner, mix(r["light"], r["accent2"], 0.4))
            hill = skia.Path()
            hill.moveTo(W * 0.215, H * 0.33)
            hill.quadTo(W * 0.26, H * 0.24, W * 0.315, H * 0.33)
            hill.close()
            pen.fill(hill, r["accent2"])
        if s in ("cafe", "kitchen"):
            for i in range(3):
                x = W * (0.12 + 0.28 * i)
                cord = skia.Path()
                cord.moveTo(x, -H * 0.2)
                cord.lineTo(x, H * 0.12)
                pen.line(cord, "#3A3F47", 2)
                shade_p = skia.Path()
                shade_p.moveTo(x - 26, H * 0.17)
                shade_p.lineTo(x + 26, H * 0.17)
                shade_p.lineTo(x + 12, H * 0.12)
                shade_p.lineTo(x - 12, H * 0.12)
                shade_p.close()
                pen.shape(shade_p, r["accent"], 2.4)
                pen.fill(_oval(x, H * 0.19, 34, 10), "#FFF59D", 0.35 + 0.1 * math.sin(t * 2 + i), flat=True)

    def _interior_mid(self, c, pen, t, rng):
        H, W, r = self.H, self.W, self.roles
        s = self.s
        gy = self.ground_y
        from .props import draw_prop
        items = {"bedroom": [("bed", 0.18, 1.25), ("lamp", 0.92, 0.9)], "kitchen": [("table", 0.2, 1.2), ("plant", 0.9, 0.8)],
                 "office": [("table", 0.15, 1.2), ("laptop", 0.15, 0.55), ("plant", 0.92, 0.9)], "classroom": [("table", 0.75, 1.0), ("book", 0.75, 0.45)],
                 "cafe": [("table", 0.12, 1.0), ("cup", 0.1, 0.4), ("table", 0.9, 1.0), ("cup", 0.9, 0.4)],
                 "room": [("sofa", 0.14, 1.25), ("plant", 0.92, 0.9), ("lamp", 0.32, 0.95)]}.get(s, [])
        for kind, fx, sc in items:
            sz = H * 0.2 * sc
            c.save()
            yoff = {"laptop": 0.2, "cup": 0.21, "book": 0.2}.get(kind, 0.0)
            c.translate(W * fx, gy - sz * 0.42 - H * yoff * sc * 1.1)
            c.scale(sz / 100, sz / 100)
            draw_prop(pen, kind, r["accent2"] if kind in ("sofa", "bed") else "", t, r)
            c.restore()

    def _interior_ground(self, c, pen, t, rng):
        H, r = self.H, self.roles
        floor = "#FFFFFF" if self.white else (mix(r["ground"], "#2A2C52", 0.4) if self.time == "night" else mix(r["ground"], "#FFFFFF", 0.35))
        _rect(c, self._x0(), self.ground_y - 2, self._x1(), H * 2, floor)
        base = skia.Path()
        base.moveTo(self._x0(), self.ground_y)
        base.lineTo(self._x1(), self.ground_y)
        pen.line(base, shade(floor, -0.3) if not self.white else "#232327", 3)
        if not self.white:
            p = skia.Paint(AntiAlias=True, Color=skc(shade(floor, -0.06), 0.7), Style=skia.Paint.kStroke_Style, StrokeWidth=2)
            for i in range(-8, 22):
                x = i * self.W * 0.09
                c.drawLine(x, self.ground_y, x - self.W * 0.06, H * 1.2, p)
            rug = _oval(self.W * 0.5, self.ground_y + H * 0.07, self.W * 0.28, H * 0.045)
            pen.fill(rug, mix(r["accent"], "#FFFFFF", 0.35), 0.9)

    # ---------- city ----------
    def _city_back(self, c, pen, t, rng):
        top, bot = sky_colors(self.roles, self.time, self.lk["look"])
        if self.white:
            _rect(c, self._x0(), -self.H, self._x1(), self.H * 2, "#FFFFFF")
            return
        _grad(c, self._x0(), -self.H * 0.5, self._x1(), self.ground_y, top, bot)
        self._celestial(c, pen, t, rng)

    def _celestial(self, c, pen, t, rng):
        W, H = self.W, self.H
        from .props import draw_prop
        if self.time == "night":
            for i in range(70):
                x, y = self._x0() + rng.random() * (self._x1() - self._x0()), -H * 0.3 + rng.random() * H * 0.7
                a = 0.4 + 0.6 * abs(math.sin(t * (1 + rng.random() * 2) + i))
                c.drawCircle(x, y, 1.2 + rng.random() * 1.4, skia.Paint(AntiAlias=True, Color=skc("#FFFFFF", a)))
            if "moon" not in self.no_sky:
                c.save()
                c.translate(W * 0.8, H * 0.16)
                c.scale(H * 0.0013, H * 0.0013)
                draw_prop(pen, "moon", "", t)
                c.restore()
        elif "sun" not in self.no_sky:
            c.save()
            c.translate(W * 0.82, H * 0.15)
            c.scale(H * 0.0015, H * 0.0015)
            draw_prop(pen, "sun", "", t)
            c.restore()
        for k in range(4):
            cx = self._x0() + ((t * (10 + 4 * k) + k * W * 0.7) % (self._x1() - self._x0()))
            c.save()
            c.translate(cx, H * (0.1 + 0.07 * (k % 3)))
            s = H * (0.0012 + 0.0004 * (k % 2))
            c.scale(s, s)
            draw_prop(pen, "cloud", "#FFFFFF" if self.time != "night" else "#5A6290", t)
            c.restore()

    def _city_far(self, c, pen, t, rng):
        H = self.H
        col = mix(self.roles["dark"], "#7A86B8", 0.5) if self.time != "night" else "#2E3566"
        x = self._x0()
        while x < self._x1():
            w = self.W * (0.05 + rng.random() * 0.06)
            h = H * (0.18 + rng.random() * 0.3)
            p = skia.Path()
            p.addRect(skia.Rect.MakeLTRB(x, self.ground_y - h - H * 0.08, x + w, self.ground_y))
            pen.fill(p, mix(col, "#FFFFFF", 0.15 if not self.white else 0.9), 0.85)
            x += w + 2

    def _city_mid(self, c, pen, t, rng):
        H, W, r = self.H, self.W, self.roles
        x = self._x0()
        cols = [r["accent"], r["accent2"], r["mid"], r["light"]]
        i = 0
        while x < self._x1():
            w = W * (0.12 + rng.random() * 0.08)
            h = H * (0.32 + rng.random() * 0.22)
            b = skia.Path()
            b.addRRect(skia.RRect.MakeRectXY(skia.Rect.MakeLTRB(x, self.ground_y - h, x + w, self.ground_y), 4, 4))
            col = mix(cols[i % len(cols)], "#FFFFFF", 0.25)
            if self.time == "night":
                col = mix(col, "#1B1E3A", 0.55)
            pen.shape(b, col, 2.6)
            for wy in range(3):
                for wx in range(2):
                    lit = self.time == "night" and rng.random() < 0.6
                    win = skia.Path()
                    win.addRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(x + w * (0.18 + 0.42 * wx), self.ground_y - h + h * (0.12 + 0.24 * wy), w * 0.24, h * 0.13), 2, 2))
                    pen.shape(win, "#FFE58A" if lit else mix("#BFE3FF", col, 0.3), 1.6)
            x += w + W * 0.03
            i += 1

    def _city_ground(self, c, pen, t, rng):
        H, W = self.H, self.W
        walk = "#FFFFFF" if self.white else ("#9EA3B5" if self.time != "night" else "#4A4F6A")
        _rect(c, self._x0(), self.ground_y - 2, self._x1(), H * 2, walk)
        road = "#FFFFFF" if self.white else ("#5C6070" if self.time != "night" else "#2D3042")
        _rect(c, self._x0(), self.ground_y + H * 0.09, self._x1(), H * 2, road)
        ln = skia.Path()
        ln.moveTo(self._x0(), self.ground_y)
        ln.lineTo(self._x1(), self.ground_y)
        pen.line(ln, "#232327" if self.white else shade(walk, -0.3), 3)
        p = skia.Paint(AntiAlias=True, Color=skc("#FFFFFF", 0.8))
        x = self._x0()
        while x < self._x1():
            c.drawRect(skia.Rect.MakeXYWH(x, self.ground_y + H * 0.16, W * 0.06, H * 0.012), p)
            x += W * 0.12
        for lx in (W * 0.05, W * 0.95):
            post = skia.Path()
            post.addRect(skia.Rect.MakeLTRB(lx - 4, self.ground_y - H * 0.42, lx + 4, self.ground_y))
            pen.shape(post, "#3A3F47", 2)
            pen.shape(_oval(lx, self.ground_y - H * 0.44, 14, 10), "#FFE58A" if self.time == "night" else "#F5F5F5", 2)

    # ---------- nature ----------
    _nature_back = _city_back

    def _nature_far(self, c, pen, t, rng):
        H = self.H
        g = self.roles["accent2"]
        col = mix(g, "#7FB77E", 0.6) if self.time == "day" else mix(g, "#2D4A5A", 0.6) if self.time == "night" else mix(g, "#C77B6B", 0.5)
        for k, (amp, base) in enumerate(((0.16, 0.62), (0.1, 0.7))):
            p = skia.Path()
            p.moveTo(self._x0(), self.ground_y)
            x = self._x0()
            step = self.W * 0.05
            while x <= self._x1():
                y = H * base - amp * H * (0.5 + 0.5 * math.sin(x / self.W * 3.1 + k * 2 + self.seed))
                if self.s == "mountains" and k == 0:
                    y = H * 0.32 + H * 0.22 * abs(math.sin(x / self.W * 4.2 + self.seed))
                p.lineTo(x, y)
                x += step
            p.lineTo(self._x1(), self.ground_y)
            p.close()
            pen.shape(p, mix(col, "#FFFFFF", 0.25 - 0.15 * k), 2.2)

    def _nature_mid(self, c, pen, t, rng):
        H, W = self.H, self.W
        from .props import draw_prop
        n = 9 if self.s == "forest" else 4
        for i in range(n):
            x = self._x0() + (i + 0.5) * (self._x1() - self._x0()) / n + rng.uniform(-40, 40)
            if abs(x - W * 0.5) < W * 0.12 and self.s != "forest":
                continue
            s = H * (0.0042 if self.s == "forest" else 0.0034) * rng.uniform(0.8, 1.15)
            c.save()
            c.translate(x, self.ground_y - 50 * s)
            c.scale(s, s)
            draw_prop(pen, "tree", mix("#5DBB63", self.roles["accent2"], 0.35) if self.time != "night" else "#2F5E4E", t)
            c.restore()

    def _nature_ground(self, c, pen, t, rng):
        H, W = self.H, self.W
        g = "#FFFFFF" if self.white else (mix("#8BD17C", self.roles["accent2"], 0.3) if self.time != "night" else "#2E4D44")
        p = skia.Path()
        p.moveTo(self._x0(), self.ground_y)
        x = self._x0()
        while x <= self._x1():
            p.lineTo(x, self.ground_y - 6 * math.sin(x / W * 9))
            x += W * 0.04
        p.lineTo(self._x1(), H * 2)
        p.lineTo(self._x0(), H * 2)
        p.close()
        pen.shape(p, g, 2.6)
        if not self.white:
            for i in range(26):
                fx = self._x0() + rng.random() * (self._x1() - self._x0())
                fy = self.ground_y + rng.random() * H * 0.12
                pen.fill(_oval(fx, fy, 4, 4), rng.choice(["#FFFFFF", "#FFD54F", "#F48FB1"]), 0.9, flat=True)

    # ---------- beach ----------
    _beach_back = _city_back

    def _beach_far(self, c, pen, t, rng):
        H = self.H
        sea = "#4FC3F7" if self.time == "day" else "#2C3E70" if self.time == "night" else "#E08E79"
        _rect(c, self._x0(), H * 0.58, self._x1(), self.ground_y, sea if not self.white else "#FFFFFF")
        for k in range(3):
            w = skia.Path()
            y = H * (0.62 + 0.07 * k)
            x = self._x0()
            w.moveTo(x, y)
            while x < self._x1():
                w.quadTo(x + 30, y - 6 * math.sin(t * 2 + k), x + 60, y)
                x += 60
            pen.line(w, "#FFFFFF", 2.2, 0.7)

    def _beach_ground(self, c, pen, t, rng):
        sand = "#FFFFFF" if self.white else ("#F6D8A8" if self.time != "night" else "#6B6080")
        p = skia.Path()
        p.moveTo(self._x0(), self.ground_y - 8)
        p.cubicTo(self.W * 0.3, self.ground_y - 20, self.W * 0.7, self.ground_y + 6, self._x1(), self.ground_y - 10)
        p.lineTo(self._x1(), self.H * 2)
        p.lineTo(self._x0(), self.H * 2)
        p.close()
        pen.shape(p, sand, 2.6)

    # ---------- sky / space / stage / abstract / plain ----------
    def _sky_back(self, c, pen, t, rng):
        self._city_back(c, pen, t, rng)

    def _sky_mid(self, c, pen, t, rng):
        from .props import draw_prop
        for k in range(5):
            cx = self._x0() + ((t * 30 * (1 + k % 2) + k * self.W * 0.5) % (self._x1() - self._x0()))
            c.save()
            c.translate(cx, self.H * (0.25 + 0.15 * (k % 4)))
            s = self.H * 0.0024
            c.scale(s, s)
            draw_prop(pen, "cloud", "#FFFFFF", t)
            c.restore()

    def _space_back(self, c, pen, t, rng):
        if self.white:
            _rect(c, self._x0(), -self.H, self._x1(), self.H * 2, "#FFFFFF")
        else:
            _grad(c, self._x0(), -self.H * 0.5, self._x1(), self.H * 1.5, "#0B0E2A", "#2A1B4A")
        for i in range(120):
            x, y = self._x0() + rng.random() * (self._x1() - self._x0()), -self.H * 0.5 + rng.random() * self.H * 2
            a = 0.3 + 0.7 * abs(math.sin(t * (0.5 + rng.random() * 2) + i))
            c.drawCircle(x, y, 0.8 + rng.random() * 1.8, skia.Paint(AntiAlias=True, Color=skc("#FFFFFF" if not self.white else "#232327", a)))

    def _space_far(self, c, pen, t, rng):
        for (fx, fy, rr, col) in ((0.15, 0.25, 0.09, self.roles["accent"]), (0.85, 0.7, 0.14, self.roles["accent2"])):
            pl = _oval(self.W * fx, self.H * fy, self.H * rr, self.H * rr)
            pen.shape(pl, col, 3)
            ring = skia.Path()
            ring.addOval(skia.Rect.MakeXYWH(self.W * fx - self.H * rr * 1.7, self.H * fy - self.H * rr * 0.35, self.H * rr * 3.4, self.H * rr * 0.7))
            pen.line(ring, mix(col, "#FFFFFF", 0.5), 3, 0.9)

    def _stage_back(self, c, pen, t, rng):
        H, W, r = self.H, self.W, self.roles
        _rect(c, self._x0(), -H, self._x1(), H * 2, "#FFFFFF" if self.white else "#1E1630")
        for side in (-1, 1):
            cur = skia.Path()
            x = W * 0.5 + side * W * 0.62
            cur.moveTo(x, -H * 0.1)
            cur.lineTo(x - side * W * 0.22, -H * 0.1)
            cur.cubicTo(x - side * W * 0.12, H * 0.3, x - side * W * 0.2, H * 0.6, x - side * W * 0.08, self.ground_y)
            cur.lineTo(x + side * W * 0.2, self.ground_y)
            cur.close()
            pen.shape(cur, "#B3263E" if not self.white else "#FFFFFF", 3)

    def _stage_mid(self, c, pen, t, rng):
        if self.white:
            return
        for i, fx in enumerate((0.3, 0.5, 0.7)):
            sway = math.sin(t * 0.8 + i * 2) * self.W * 0.06
            cone = skia.Path()
            cone.moveTo(self.W * fx - 12, -self.H * 0.1)
            cone.lineTo(self.W * fx + 12, -self.H * 0.1)
            cone.lineTo(self.W * fx + sway + self.W * 0.11, self.ground_y)
            cone.lineTo(self.W * fx + sway - self.W * 0.11, self.ground_y)
            cone.close()
            p = skia.Paint(AntiAlias=True, Color=skc("#FFF6C8", 0.18))
            c.drawPath(cone, p)

    def _stage_ground(self, c, pen, t, rng):
        _rect(c, self._x0(), self.ground_y - 2, self._x1(), self.H * 2, "#FFFFFF" if self.white else "#3A2A20")
        ln = skia.Path()
        ln.moveTo(self._x0(), self.ground_y)
        ln.lineTo(self._x1(), self.ground_y)
        pen.line(ln, "#232327", 3)

    def _abstract_back(self, c, pen, t, rng):
        r = self.roles
        if self.white:
            _rect(c, self._x0(), -self.H, self._x1(), self.H * 2, "#FFFFFF")
        else:
            _grad(c, self._x0(), -self.H * 0.5, self._x1(), self.H * 1.5, mix(r["accent"], r["dark"], 0.15), mix(r["accent2"], r["dark"], 0.35))
        for i in range(6):
            a = t * (0.15 + 0.05 * i) + i
            x = self.W * (0.5 + 0.42 * math.cos(a + i * 1.7))
            y = self.H * (0.5 + 0.38 * math.sin(a * 1.3 + i))
            rr = self.H * (0.12 + 0.05 * (i % 3))
            col = r["all"][i % len(r["all"])]
            if i % 2:
                pen.fill(_oval(x, y, rr, rr), mix(col, "#FFFFFF", 0.2), 0.35)
            else:
                s = skia.Path()
                s.addRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(x - rr, y - rr, rr * 2, rr * 2), rr * 0.35, rr * 0.35))
                s.transform(skia.Matrix.RotateDeg(t * 20 + i * 30, skia.Point(x, y)))
                pen.fill(s, mix(col, "#FFFFFF", 0.3), 0.3)

    def _plain_back(self, c, pen, t, rng):
        r = self.roles
        _rect(c, self._x0(), -self.H, self._x1(), self.H * 2, "#FFFFFF" if self.white else mix(r["light"], r["accent2"], 0.15))

    def _plain_ground(self, c, pen, t, rng):
        if self.white:
            return
        pen.fill(_oval(self.W * 0.5, self.ground_y + 6, self.W * 0.3, self.H * 0.03), shade(mix(self.roles["light"], self.roles["accent2"], 0.15), -0.08), 0.8)

    def has_ground(self) -> bool:
        return self.s not in ("sky", "space", "abstract")


def draw_starfield_bg(c: skia.Canvas, W: int, H: int) -> None:
    _grad(c, 0, 0, W, H, "#0B0E2A", "#2A1B4A")


__all__ = ["Background", "SETTINGS", "guess_setting", "guess_time", "sky_colors", "_star"]
