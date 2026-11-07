"""Fonts and text: ReelMimic's caption fonts (woff2 → ttf cache) with per-character fallback for CJK."""
from __future__ import annotations

import functools
import os
import tempfile
from pathlib import Path

import skia

from .. import config
from .color import skc

_CACHE = Path(os.environ.get("STUDIO_FONT_CACHE") or (Path(tempfile.gettempdir()) / "avos-studio-fonts"))
FONT_FILES = {
    "baloo-2": "baloo-2-latin-700-normal.woff2", "anton": "anton-latin-400-normal.woff2", "bangers": "bangers-latin-400-normal.woff2",
    "caveat": "caveat-latin-700-normal.woff2", "chakra-petch": "chakra-petch-latin-700-normal.woff2",
    "permanent-marker": "permanent-marker-latin-400-normal.woff2", "press-start-2p": "press-start-2p-latin-400-normal.woff2",
    "fredoka": "fredoka-latin-700-normal.woff2", "inter": "inter-latin-800-normal.woff2", "vt323": "vt323-latin-400-normal.woff2",
}
_MGR = skia.FontMgr()
CJK_PREF = ["Microsoft JhengHei", "Microsoft YaHei", "PingFang TC", "Noto Sans CJK TC", "Noto Sans TC", "Noto Sans CJK SC",
            "Source Han Sans TC", "WenQuanYi Zen Hei"]


@functools.lru_cache(maxsize=None)
def typeface(name: str) -> skia.Typeface:
    f = FONT_FILES.get(name)
    if f:
        src = config.FONTS_DIR / f
        dst = _CACHE / (Path(f).stem + ".ttf")
        try:
            if not dst.exists() and src.exists():
                from fontTools.ttLib import TTFont
                _CACHE.mkdir(parents=True, exist_ok=True)
                tt = TTFont(str(src))
                tt.flavor = None
                tt.save(str(dst))
            if dst.exists():
                tf = skia.Typeface.MakeFromFile(str(dst))
                if tf:
                    return tf
        except Exception:
            pass
    for fam in ("DejaVu Sans", "Arial", "Segoe UI", "Helvetica", ""):
        tf = _MGR.matchFamilyStyle(fam, skia.FontStyle.Bold()) if fam else None
        if tf:
            return tf
    return skia.Typeface.MakeDefault()


@functools.lru_cache(maxsize=4096)
def _fallback_for(ch: str) -> skia.Typeface | None:
    for fam in CJK_PREF:
        tf = _MGR.matchFamilyStyle(fam, skia.FontStyle.Bold())
        if tf and tf.unicharToGlyph(ord(ch)):
            return tf
    return _MGR.matchFamilyStyleCharacter("", skia.FontStyle.Bold(), ["zh-TW", "zh-CN", "ja"], ord(ch))


def runs(text: str, tf: skia.Typeface) -> list[tuple[str, skia.Typeface]]:
    out: list[tuple[str, skia.Typeface]] = []
    for ch in text:
        use = tf if (ch.isspace() or tf.unicharToGlyph(ord(ch))) else (_fallback_for(ch) or tf)
        if out and out[-1][1] is use:
            out[-1] = (out[-1][0] + ch, use)
        else:
            out.append((ch, use))
    return out


def measure(text: str, tf: skia.Typeface, size: float) -> float:
    return sum(skia.Font(t, size).measureText(s) for s, t in runs(text, tf))


def wrap(text: str, tf: skia.Typeface, size: float, max_w: float) -> list[str]:
    lines: list[str] = []
    for para in str(text).split("\n"):
        cjk = any(ord(c) > 0x2E80 for c in para)
        tokens = list(para) if cjk else para.split(" ")
        cur = ""
        for tok in tokens:
            cand = cur + tok if cjk else (cur + " " + tok if cur else tok)
            if cur and measure(cand, tf, size) > max_w:
                lines.append(cur)
                cur = tok
            else:
                cur = cand
        lines.append(cur)
    return [ln for ln in lines if ln.strip()] or [""]


def draw_line(canvas: skia.Canvas, text: str, x: float, y: float, tf: skia.Typeface, size: float, fill: str,
              stroke: str | None = None, stroke_w: float = 0.0, alpha: float = 1.0, aa: bool = True) -> float:
    """Draw one line with its baseline at y, starting at x. Returns the width."""
    w = 0.0
    for s, t in runs(text, tf):
        font = skia.Font(t, size)
        font.setEdging(skia.Font.Edging.kAntiAlias if aa else skia.Font.Edging.kAlias)
        blob = skia.TextBlob.MakeFromString(s, font)
        if blob is None:
            continue
        if stroke and stroke_w > 0:
            p = skia.Paint(AntiAlias=aa, Color=skc(stroke, alpha), Style=skia.Paint.kStroke_Style, StrokeWidth=stroke_w,
                           StrokeJoin=skia.Paint.kRound_Join)
            canvas.drawTextBlob(blob, x + w, y, p)
        canvas.drawTextBlob(blob, x + w, y, skia.Paint(AntiAlias=aa, Color=skc(fill, alpha)))
        w += font.measureText(s)
    return w
