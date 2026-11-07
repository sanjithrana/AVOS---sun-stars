"""Colour helpers: hex parsing, HSL tweaks, palette roles and named colours (English + Chinese)."""
from __future__ import annotations

import colorsys
import re

import skia

NAMED = {
    "red": "#E5484D", "crimson": "#C2185B", "pink": "#F48FB1", "rose": "#F06292", "orange": "#FF8A3D", "peach": "#FFB38A",
    "yellow": "#FFD54F", "gold": "#F4B400", "cream": "#FFF3D6", "beige": "#E9D8B4", "brown": "#8D5A3B", "tan": "#C69C6D",
    "green": "#4CAF50", "lime": "#A5D65B", "mint": "#9FE2BF", "teal": "#26A69A", "cyan": "#4DD0E1", "turquoise": "#40C4C4",
    "blue": "#4A7BF7", "navy": "#24325F", "sky": "#87CEEB", "purple": "#8E5CC4", "violet": "#7E57C2", "lavender": "#B9A7E8",
    "magenta": "#D63AAF", "white": "#FAFAFA", "black": "#1E1E24", "gray": "#9AA0A6", "grey": "#9AA0A6", "silver": "#C7CCD1",
    "charcoal": "#36393F", "olive": "#8A9A3B", "maroon": "#7B2D3B", "coral": "#FF7F6E",
    "紅": "#E5484D", "粉": "#F48FB1", "橘": "#FF8A3D", "橙": "#FF8A3D", "黃": "#FFD54F", "黄": "#FFD54F", "金": "#F4B400",
    "米": "#E9D8B4", "棕": "#8D5A3B", "咖啡": "#8D5A3B", "綠": "#4CAF50", "绿": "#4CAF50", "青綠": "#26A69A", "青": "#26A69A",
    "藍": "#4A7BF7", "蓝": "#4A7BF7", "天藍": "#87CEEB", "深藍": "#24325F", "紫": "#8E5CC4", "灰紫": "#9C8FB5", "白": "#FAFAFA",
    "黑": "#1E1E24", "灰": "#9AA0A6", "銀": "#C7CCD1",
}
HEX = re.compile(r"#?([0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b")


def parse(c, default: str = "#888888") -> tuple[float, float, float]:
    """'#RRGGBB' / '#RGB' / a colour name → (r, g, b) in 0..1."""
    if isinstance(c, (tuple, list)) and len(c) >= 3:
        return tuple(float(x) / (255 if max(c) > 1 else 1) for x in c[:3])  # type: ignore[return-value]
    s = str(c or "").strip()
    m = HEX.fullmatch(s) or HEX.fullmatch("#" + s.lstrip("#"))
    if not m:
        named = NAMED.get(s.lower()) or next((v for k, v in NAMED.items() if k in s.lower()), None)
        m = HEX.fullmatch(named) if named else HEX.fullmatch(default)
    h = m.group(1)  # type: ignore[union-attr]
    if len(h) == 3:
        h = "".join(ch * 2 for ch in h)
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))  # type: ignore[return-value]


def hexs(rgb) -> str:
    r, g, b = (max(0, min(255, round(x * 255))) for x in rgb)
    return f"#{r:02X}{g:02X}{b:02X}"


def norm(c, default: str = "#888888") -> str:
    return hexs(parse(c, default))


def find_color(text: str) -> str | None:
    """The first colour mentioned in a description ('green hoodie', '青綠連帽T', '#12AB34')."""
    if not text:
        return None
    m = HEX.search(text)
    if m:
        return norm("#" + m.group(1))
    low = text.lower()
    best = None
    for k, v in NAMED.items():
        i = low.find(k)
        if i >= 0 and (best is None or i < best[0] or (i == best[0] and len(k) > best[2])):
            best = (i, v, len(k))
    return best[1] if best else None


def colors_near(text: str, words: list[str]) -> str | None:
    """Colour named right before (or else right after) one of `words`: 'green' in 'a green hoodie', '青綠' in '青綠連帽T'."""
    low = (text or "").lower()
    for w in words:
        i = low.find(w)
        if i < 0:
            continue
        before = low[max(0, i - 16): i]
        cut = max(before.rfind(","), before.rfind("，"), before.rfind("、"), before.rfind(";"), before.rfind(" and "))
        if cut >= 0:
            before = before[cut + 1:]
        hits = []
        for k, v in NAMED.items():
            j = before.rfind(k)
            if j >= 0:
                hits.append((j + len(k), len(k), v))
        m = HEX.search(before)
        if m:
            hits.append((m.end(), 7, norm("#" + m.group(1))))
        if hits:
            return max(hits)[2]
        after = low[i + len(w): i + len(w) + 10]
        c = find_color(re.split(r"[,，、;]", after)[0])
        if c:
            return c
    return None


def hls(c) -> tuple[float, float, float]:
    r, g, b = parse(c)
    return colorsys.rgb_to_hls(r, g, b)


def from_hls(h: float, l: float, s: float) -> str:
    return hexs(colorsys.hls_to_rgb(h % 1.0, max(0, min(1, l)), max(0, min(1, s))))


def shade(c, dl: float = -0.15, ds: float = 0.0) -> str:
    h, l, s = hls(c)
    return from_hls(h, l + dl, s + ds)


def mix(a, b, t: float) -> str:
    pa, pb = parse(a), parse(b)
    return hexs(tuple(x + (y - x) * t for x, y in zip(pa, pb)))


def luma(c) -> float:
    r, g, b = parse(c)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def hue_dist(a, b) -> float:
    ha, _, sa = hls(a)
    hb, _, sb = hls(b)
    d = abs(ha - hb)
    return min(d, 1 - d) * min(sa, sb) * 2


def skc(c, alpha: float = 1.0) -> int:
    r, g, b = parse(c)
    return skia.Color(round(r * 255), round(g * 255), round(b * 255), max(0, min(255, round(alpha * 255))))


def palette_roles(palette: list[str] | None, night: bool = False) -> dict:
    """Map a plan palette (2–8 colours) to drawing roles."""
    pal = [norm(c) for c in (palette or []) if c] or ["#2A2C52", "#FFD66B", "#FF8FA3", "#7FD1C7", "#F6F1E7"]
    by_l = sorted(pal, key=luma)
    dark, light = by_l[0], by_l[-1]
    sat = sorted(pal, key=lambda c: -hls(c)[2])
    accent = sat[0]
    accent2 = sat[1] if len(sat) > 1 else shade(accent, 0.1, -0.1)
    mid = by_l[len(by_l) // 2]
    sky_top = mix(dark, "#0B1030", 0.4) if night else mix(light, accent2, 0.35)
    sky_bot = mix(dark, accent, 0.25) if night else mix(light, "#FFFFFF", 0.3)
    return {"dark": dark, "light": light, "accent": accent, "accent2": accent2, "mid": mid, "all": pal,
            "sky_top": sky_top, "sky_bot": sky_bot, "ground": mix(mid, dark, 0.25), "wall": mix(light, mid, 0.25),
            "line": mix(dark, "#000000", 0.35)}
