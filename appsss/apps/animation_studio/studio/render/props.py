"""Props: simple vector objects drawn through the Pen (so every engine styles them). Local size ≈ 100 units."""
from __future__ import annotations

import math
import re

import skia

from .color import mix, shade
from .rig import _heart, _limb, _oval, _star

PROP_WORDS = {
    "heart": r"\bhearts?\b|愛心|心", "star": r"\bstars?\b|starry|星", "cloud": r"\bclouds?\b|cloudy|雲|云", "sun": r"\bsun\b|太陽|太阳|sunshine|陽光",
    "moon": r"\bmoon|月亮|月", "tree": r"\btrees?\b|樹|树", "house": r"\bhouse\b|房子", "phone": r"\bphones?\b|手機|手机|smartphone",
    "laptop": r"\blaptop|computer|電腦|电脑", "cup": r"\bcups?\b|coffee|\btea\b|\bmug\b|咖啡|茶|杯", "book": r"\bbooks?\b|novel|書|书",
    "gift": r"\bgifts?\b|\bpresents?\b|禮物|礼物", "car": r"\bcars?\b|汽車|車子|车", "ball": r"\bballs?\b|球", "balloon": r"balloon|氣球|气球",
    "flower": r"flower|花", "umbrella": r"umbrella|傘|伞", "cake": r"\bcake|蛋糕|birthday|生日", "note": r"\bmusic|\bsong|\bmusical note|音樂|音符|歌",
    "bulb": r"\bidea|light ?bulb|燈泡|灯泡|點子", "coin": r"\bcoins?\b|\bmoney\b|\bcash\b|錢|钱|金幣", "bag": r"\bbags?\b|shopping|購物|袋",
    "chair": r"\bchairs?\b|椅", "table": r"\btables?\b|\bdesks?\b|桌", "sofa": r"\bsofa|\bcouch|沙發", "bed": r"\bbed\b|床",
    "tv": r"\btv\b|television|電視|电视", "window": r"\bwindows?\b|窗", "door": r"\bdoors?\b|門|门", "lamp": r"\blamps?\b|燈|灯",
    "plant": r"\bplants?\b|盆栽|植物", "rocket": r"\brockets?\b|火箭|spaceship", "clock": r"\bclocks?\b|alarm|時鐘|时钟",
    "camera": r"\bcamera|\bphoto|相機|拍照", "guitar": r"guitar|吉他", "mic": r"\bmic\b|microphone|麥克風|唱", "pizza": r"pizza|披薩",
    "icecream": r"ice ?cream|冰淇淋", "game": r"\bvideo ?games?\b|controller|遊戲|游戏|打電動", "letter": r"\bletters?\b|\bmail\b|信",
    "bike": r"\bbikes?\b|bicycle|腳踏車|自行车", "dog": r"\bdogs?\b|puppy|小狗", "bird": r"\bbirds?\b|鳥|鸟", "fish": r"\bfish|魚|鱼", "cat": r"\bcats?\b|kitten|小貓",
}
KINDS = tuple(PROP_WORDS)


def guess_props(text: str, limit: int = 3) -> list[str]:
    low = (text or "").lower()
    hits = []
    for k, pat in PROP_WORDS.items():
        m = re.search(pat, low)
        if m:
            hits.append((m.start(), k))
    return [k for _, k in sorted(hits)][:limit]


SKY_PROPS = {"moon", "sun", "star", "cloud", "balloon", "rocket", "bird"}
WALL_PROPS = {"window", "clock", "lamp", "tv", "door"}


def place_props(kinds: list[str]) -> list[dict]:
    """Sky things up high, wall things at head height, the rest on the ground at the sides (characters stand mid-frame)."""
    out, sides = [], [0.84, 0.16, 0.7, 0.3]
    for j, k in enumerate(kinds):
        x = sides[j % len(sides)]
        if k in SKY_PROPS:
            out.append({"kind": k, "x": x, "y": 0.17, "scale": 0.15, "anim": "float"})
        elif k in WALL_PROPS:
            out.append({"kind": k, "x": x, "y": 0.4, "scale": 0.16, "anim": "none"})
        else:
            out.append({"kind": k, "x": x, "y": 0.66, "scale": 0.12, "anim": "none"})
    return out


def _rr(l: float, t: float, r: float, b: float, rad: float) -> skia.Path:
    p = skia.Path()
    p.addRRect(skia.RRect.MakeRectXY(skia.Rect.MakeLTRB(l, t, r, b), rad, rad))
    return p


def _poly(pts: list[tuple[float, float]]) -> skia.Path:
    p = skia.Path()
    p.moveTo(*pts[0])
    for q in pts[1:]:
        p.lineTo(*q)
    p.close()
    return p


def draw_prop(pen, kind: str, color: str, t: float = 0.0, pal: dict | None = None) -> skia.Rect:
    """Draw a prop centred on (0,0), ~100 units tall. Returns local bounds."""
    w = 3.0
    acc = color
    pal = pal or {}
    k = kind if kind in KINDS else "star"
    parts: list[skia.Path] = []

    def sh(p: skia.Path, c: str, line: bool = True, flat: bool = False) -> None:
        pen.shape(p, c, w, line=line, flat=flat)
        parts.append(p)
    if k == "heart":
        sh(_heart(0, -5, 42), acc or "#E5484D")
    elif k == "star":
        sh(_star(0, 0, 50, 22), acc or "#FFD54F")
    elif k == "cloud":
        c = acc if acc and acc != "#888888" else "#FFFFFF"
        from .rig import _union
        sh(_union([_oval(-28, 6, 26, 20), _oval(0, -8, 32, 28), _oval(30, 6, 24, 19), _rr(-50, 0, 52, 26, 13)]), c)
    elif k == "sun":
        for i in range(10):
            a = i * math.pi / 5 + t * 0.6
            ray = _poly([(math.cos(a - 0.12) * 40, math.sin(a - 0.12) * 40), (math.cos(a) * 58, math.sin(a) * 58), (math.cos(a + 0.12) * 40, math.sin(a + 0.12) * 40)])
            sh(ray, "#FFB300")
        sh(_oval(0, 0, 36, 36), "#FFD54F")
    elif k == "moon":
        moon = skia.Op(_oval(0, 0, 44, 44), _oval(22, -14, 38, 38), skia.PathOp.kDifference_PathOp) or _oval(0, 0, 40, 40)
        sh(moon, "#FFE9A8")
    elif k == "tree":
        sh(_rr(-9, 0, 9, 50, 4), "#8D5A3B")
        from .rig import _union
        sh(_union([_oval(0, -22, 34, 30), _oval(-22, -2, 24, 20), _oval(22, -2, 24, 20)]), acc if acc and acc != "#888888" else "#5DBB63")
    elif k == "house":
        sh(_rr(-40, -10, 40, 50, 3), acc or "#FFCC80")
        sh(_poly([(-50, -8), (0, -52), (50, -8)]), "#E5484D")
        sh(_rr(-10, 18, 10, 50, 2), "#8D5A3B")
        sh(_rr(16, 2, 32, 18, 2), "#BFE3FF")
    elif k == "phone":
        sh(_rr(-24, -46, 24, 46, 8), "#2B2B30")
        sh(_rr(-19, -38, 19, 34, 3), mix(acc or "#4A7BF7", "#FFFFFF", 0.4), line=False)
    elif k == "laptop":
        sh(_rr(-44, -34, 44, 22, 4), "#3A3F47")
        sh(_rr(-38, -28, 38, 16, 2), mix(acc or "#4A7BF7", "#FFFFFF", 0.45), line=False)
        sh(_poly([(-52, 22), (52, 22), (58, 32), (-58, 32)]), "#9AA0A6")
    elif k == "cup":
        sh(_rr(-24, -20, 24, 36, 6), acc or "#FFFFFF")
        handle = _limb([(22, -8), (36, 0), (22, 18)], 7)
        sh(handle, acc or "#FFFFFF")
        for i in (-10, 6):
            st = skia.Path()
            st.moveTo(i, -26)
            st.cubicTo(i - 6, -36 - 4 * math.sin(t * 3), i + 6, -42, i, -52)
            pen.line(st, "#C8C8C8", 2.0, 0.7)
    elif k == "book":
        sh(_rr(-40, -30, 40, 30, 3), acc or "#4A7BF7")
        sh(_rr(-34, -24, 34, 24, 2), "#FFF8E7", line=False)
        ln = skia.Path()
        ln.moveTo(0, -24)
        ln.lineTo(0, 24)
        pen.line(ln, shade(acc or "#4A7BF7", -0.2), 2)
    elif k == "gift":
        sh(_rr(-36, -12, 36, 40, 3), acc or "#E5484D")
        sh(_rr(-40, -24, 40, -8, 3), shade(acc or "#E5484D", 0.08))
        sh(_rr(-6, -24, 6, 40, 1), "#FFD54F", line=False)
        sh(_heart(0, -32, 10), "#FFD54F")
    elif k == "car":
        sh(_rr(-55, -10, 55, 22, 10), acc or "#E5484D")
        sh(_poly([(-30, -10), (-18, -34), (22, -34), (34, -10)]), shade(acc or "#E5484D", 0.05))
        sh(_rr(-14, -28, 0, -12, 2), "#BFE3FF", line=False)
        sh(_rr(6, -28, 24, -12, 2), "#BFE3FF", line=False)
        for x in (-32, 32):
            pen.shape(_oval(x, 24, 13, 13), "#2B2B30", w)
            pen.shape(_oval(x, 24, 5, 5), "#C7CCD1", w * 0.5)
    elif k == "ball":
        sh(_oval(0, 0, 40, 40), acc or "#FF8A3D")
        ln = skia.Path()
        ln.addArc(skia.Rect.MakeLTRB(-40, -60, 40, 20), 30, 120)
        pen.line(ln, shade(acc or "#FF8A3D", -0.3), 2.5)
    elif k == "balloon":
        s = skia.Path()
        s.moveTo(0, 28)
        s.cubicTo(-8, 48, 8, 60, 0, 80)
        pen.line(s, "#888888", 1.5)
        sh(_oval(0, -10, 32, 38), acc or "#E5484D")
        sh(_poly([(-5, 30), (5, 30), (0, 24)]), acc or "#E5484D")
    elif k == "flower":
        st = skia.Path()
        st.moveTo(0, 0)
        st.lineTo(0, 50)
        pen.line(st, "#4CAF50", 4)
        for i in range(6):
            a = i * math.pi / 3 + t * 0.4
            sh(_oval(math.cos(a) * 16, -10 + math.sin(a) * 16, 12, 12), acc or "#F48FB1")
        sh(_oval(0, -10, 10, 10), "#FFD54F")
    elif k == "umbrella":
        st = skia.Path()
        st.moveTo(0, -30)
        st.lineTo(0, 40)
        st.quadTo(0, 50, -10, 48)
        pen.line(st, "#5D4037", 4)
        canopy = skia.Path()
        canopy.moveTo(-55, -20)
        canopy.cubicTo(-50, -70, 50, -70, 55, -20)
        for i in range(4):
            x0 = 55 - i * 27.5
            canopy.quadTo(x0 - 13.75, -30, x0 - 27.5, -20)
        canopy.close()
        sh(canopy, acc or "#4A7BF7")
    elif k == "cake":
        sh(_rr(-40, -6, 40, 36, 6), "#FFF3D6")
        sh(_rr(-40, -16, 40, 2, 6), acc or "#F48FB1")
        for x in (-18, 0, 18):
            sh(_rr(x - 3, -36, x + 3, -16, 1), "#4A7BF7")
            sh(_oval(x, -41 + math.sin(t * 9 + x) * 0.8, 3.2, 5), "#FFB300", line=False)
    elif k == "note":
        sh(_oval(-14, 26, 13, 10), acc or "#2A2430")
        sh(_oval(22, 18, 13, 10), acc or "#2A2430")
        sh(_poly([(-4, 26), (-4, -36), (32, -44), (32, 18), (28, 18), (28, -30), (0, -24), (0, 26)]), acc or "#2A2430")
    elif k == "bulb":
        glow = 0.25 + 0.15 * math.sin(t * 5)
        pen.fill(_oval(0, -10, 52, 52), "#FFF59D", glow, flat=True)
        sh(_oval(0, -14, 30, 30), "#FFE066")
        sh(_rr(-12, 14, 12, 30, 3), "#9AA0A6")
    elif k == "coin":
        sh(_oval(0, 0, 38, 38), "#F4B400")
        sh(_oval(0, 0, 28, 28), "#FFD54F")
    elif k == "bag":
        h = _limb([(-16, -20), (-14, -40), (14, -40), (16, -20)], 5)
        sh(h, shade(acc or "#E5484D", -0.15))
        sh(_poly([(-34, -20), (34, -20), (40, 40), (-40, 40)]), acc or "#E5484D")
    elif k == "chair":
        sh(_rr(-30, -60, -20, 40, 3), "#8D5A3B")
        sh(_rr(-30, -2, 30, 8, 3), "#A1887F")
        sh(_rr(22, 4, 30, 40, 2), "#8D5A3B")
    elif k == "table":
        sh(_rr(-55, -10, 55, 0, 3), acc or "#A1887F")
        sh(_rr(-48, 0, -40, 40, 2), shade(acc or "#A1887F", -0.15))
        sh(_rr(40, 0, 48, 40, 2), shade(acc or "#A1887F", -0.15))
    elif k == "sofa":
        sh(_rr(-60, -24, 60, 30, 14), acc or "#7E57C2")
        sh(_rr(-50, -6, 50, 22, 8), shade(acc or "#7E57C2", 0.08))
    elif k == "bed":
        sh(_rr(-60, -6, 60, 30, 6), acc or "#90CAF9")
        sh(_rr(-60, -30, -46, 36, 4), "#8D5A3B")
        sh(_rr(-44, -16, -16, -2, 6), "#FFFFFF")
    elif k == "tv":
        sh(_rr(-50, -36, 50, 26, 5), "#2B2B30")
        sh(_rr(-44, -30, 44, 20, 2), mix(acc or "#4A7BF7", "#FFFFFF", 0.25 + 0.15 * math.sin(t * 8)), line=False)
        sh(_poly([(-16, 26), (16, 26), (22, 38), (-22, 38)]), "#2B2B30")
    elif k == "window":
        sh(_rr(-40, -48, 40, 48, 4), "#BFE3FF")
        for (a, b, c, d) in ((-2, -48, 2, 48), (-40, -2, 40, 2)):
            sh(_rr(a, b, c, d, 0), "#FFFFFF", line=False)
    elif k == "door":
        sh(_rr(-28, -55, 28, 55, 4), acc or "#8D5A3B")
        sh(_oval(16, 4, 4, 4), "#FFD54F")
    elif k == "lamp":
        sh(_rr(-3, -20, 3, 44, 1), "#5D4037")
        sh(_poly([(-26, -20), (26, -20), (16, -50), (-16, -50)]), acc or "#FFE066")
        sh(_rr(-18, 44, 18, 50, 2), "#5D4037")
    elif k == "plant":
        sh(_poly([(-20, 10), (20, 10), (16, 44), (-16, 44)]), "#C0754B")
        for a in (-40, 0, 40):
            leaf = _oval(0, -18, 9, 26)
            leaf.transform(skia.Matrix.RotateDeg(a + 5 * math.sin(t * 2), skia.Point(0, 10)))
            sh(leaf, "#4CAF50")
    elif k == "rocket":
        sh(_poly([(-14, 20), (-26, 44), (-12, 38)]), "#E5484D")
        sh(_poly([(14, 20), (26, 44), (12, 38)]), "#E5484D")
        body = skia.Path()
        body.moveTo(0, -55)
        body.cubicTo(24, -30, 18, 20, 14, 40)
        body.lineTo(-14, 40)
        body.cubicTo(-18, 20, -24, -30, 0, -55)
        sh(body, "#F5F5F5")
        sh(_oval(0, -14, 8, 8), "#4DD0E1")
        flame = _poly([(-9, 42), (0, 62 + 6 * math.sin(t * 20)), (9, 42)])
        sh(flame, "#FFB300", line=False)
    elif k == "clock":
        sh(_oval(0, 0, 42, 42), acc or "#FFFFFF")
        hands = skia.Path()
        hands.moveTo(0, -30)
        hands.lineTo(0, 0)
        hands.lineTo(18 * math.cos(t), 18 * math.sin(t))
        pen.line(hands, "#2A2430", 3.2)
    elif k == "camera":
        sh(_rr(-44, -24, 44, 30, 8), "#3A3F47")
        sh(_rr(-18, -34, 6, -22, 3), "#3A3F47")
        sh(_oval(0, 4, 18, 18), "#90CAF9")
    elif k == "guitar":
        sh(_rr(-4, -60, 4, 0, 2), "#5D4037")
        from .rig import _union
        sh(_union([_oval(0, 18, 26, 24), _oval(0, -6, 18, 16)]), acc or "#FF8A3D")
        sh(_oval(0, 10, 7, 7), "#2B2B30")
    elif k == "mic":
        sh(_rr(-6, 0, 6, 46, 3), "#3A3F47")
        sh(_oval(0, -10, 16, 18), "#9AA0A6")
    elif k == "pizza":
        sh(_poly([(0, 45), (-38, -30), (38, -30)]), "#FFD54F")
        sh(_rr(-40, -38, 40, -26, 6), "#E0A35A")
        for x, y in ((-8, -12), (10, -4), (0, 14)):
            sh(_oval(x, y, 6, 6), "#E5484D", line=False)
    elif k == "icecream":
        sh(_poly([(-20, 0), (20, 0), (0, 50)]), "#E0A35A")
        sh(_oval(0, -10, 22, 20), acc or "#F48FB1")
    elif k == "game":
        sh(_rr(-46, -20, 46, 20, 18), acc or "#3A3F47")
        sh(_rr(-32, -4, -16, 4, 2), "#FFFFFF", line=False)
        sh(_rr(-28, -8, -20, 8, 2), "#FFFFFF", line=False)
        sh(_oval(22, -4, 5, 5), "#E5484D", line=False)
        sh(_oval(32, 4, 5, 5), "#4CAF50", line=False)
    elif k == "letter":
        sh(_rr(-44, -28, 44, 28, 3), "#FFF8E7")
        v = skia.Path()
        v.moveTo(-44, -28)
        v.lineTo(0, 6)
        v.lineTo(44, -28)
        pen.line(v, "#C8B89A", 2.5)
        sh(_heart(0, 10, 9), "#E5484D")
    elif k == "bike":
        for x in (-34, 34):
            pen.shape(_oval(x, 20, 20, 20), "#2B2B30", w)
            pen.fill(_oval(x, 20, 14, 14), "#FFFFFF", 0.0, flat=True)
        fr = skia.Path()
        fr.moveTo(-34, 20)
        fr.lineTo(-6, 20)
        fr.lineTo(10, -10)
        fr.lineTo(-20, -10)
        fr.close()
        fr.moveTo(10, -10)
        fr.lineTo(34, 20)
        pen.line(fr, acc or "#E5484D", 5)
    elif k in ("dog", "bird", "fish", "cat"):
        if k == "fish":
            sh(_poly([(26, 0), (46, -16), (46, 16)]), acc or "#4DD0E1")
            sh(_oval(0, 0, 32, 20), acc or "#4DD0E1")
            pen.fill(_oval(-16, -4, 3.5, 3.5), "#2A2430", flat=True)
        elif k == "bird":
            sh(_oval(0, 0, 26, 22), acc or "#FFD54F")
            wing = _oval(6, 2, 14, 9)
            wing.transform(skia.Matrix.RotateDeg(-20 + 25 * math.sin(t * 14), skia.Point(0, 0)))
            sh(wing, shade(acc or "#FFD54F", -0.1))
            sh(_poly([(-24, -4), (-36, 0), (-24, 4)]), "#FF8A3D")
            pen.fill(_oval(-12, -6, 3, 3), "#2A2430", flat=True)
        else:
            col = acc if acc and acc != "#888888" else ("#C08A5B" if k == "dog" else "#9AA0A6")
            from .rig import _union
            body = _union([_oval(0, 10, 34, 20), _oval(-30, -12, 20, 18)] + [_rr(x - 5, 20, x + 5, 40, 4) for x in (-22, -8, 12, 24)])
            sh(body, col)
            if k == "cat":
                sh(_poly([(-44, -22), (-40, -42), (-32, -28)]), col)
                sh(_poly([(-24, -28), (-18, -42), (-14, -22)]), col)
            else:
                sh(_oval(-44, -10, 7, 13), shade(col, -0.15))
            tail = _limb([(32, 6), (44, -6 + 6 * math.sin(t * 8)), (48, -20)], 6)
            sh(tail, col)
            pen.fill(_oval(-34, -14, 3, 3), "#2A2430", flat=True)
            pen.fill(_oval(-24, -14, 3, 3), "#2A2430", flat=True)
    b = skia.Rect.MakeLTRB(-55, -60, 55, 60)
    return b
