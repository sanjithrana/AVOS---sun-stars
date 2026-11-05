"""The Pen: every shape the renderer draws goes through it, and the engine decides how it looks
(clean vector, watercolor wash with boiling ink, waxy crayon, paper with shadows, cel shading, whiteboard marker
that draws itself on, or hard pixels)."""
from __future__ import annotations

import math
import random

import skia

from .color import mix, shade, skc


def _scale(canvas: skia.Canvas) -> float:
    m = canvas.getTotalMatrix()
    return math.sqrt(abs(m.getScaleX() * m.getScaleY() - m.getSkewX() * m.getSkewY())) or 1.0


class Pen:
    def __init__(self, canvas: skia.Canvas, lk: dict, frame: int, aa: bool = True, line_color: str = "#1E1E24", reveal: float = 1.0):
        self.c = canvas
        self.lk = lk
        self.mode = lk["fill"]
        self.boil = frame // max(1, int(lk.get("step", 1)))
        self.aa = aa
        self.line_color = line_color
        self.n = 0
        self.reveal = reveal if lk.get("reveal") else 1.0
        self.ops: list[tuple] = []          # whiteboard: recorded ops, drawn by flush()
        self.tip: tuple[float, float] | None = None

    # ---------- helpers ----------
    def _seed(self) -> int:
        self.n += 1
        return (self.n * 7919 + self.boil * 104729) & 0x7FFFFFFF

    def _jitter(self, w: float) -> skia.PathEffect | None:
        j = float(self.lk.get("jitter") or 0)
        if j <= 0:
            return None
        return skia.DiscretePathEffect.Make(max(2.0, w * 4.5), w * 0.45 * j, self._seed())

    def _paint(self, color: str, alpha: float = 1.0, stroke: float | None = None) -> skia.Paint:
        p = skia.Paint(AntiAlias=self.aa, Color=skc(color, alpha))
        if stroke is not None:
            p.setStyle(skia.Paint.kStroke_Style)
            p.setStrokeWidth(stroke)
            p.setStrokeCap(skia.Paint.kRound_Cap)
            p.setStrokeJoin(skia.Paint.kRound_Join)
        return p

    def _record(self, kind: str, path: skia.Path, paint: skia.Paint) -> None:
        self.ops.append((kind, skia.Path(path), skia.Paint(paint), self.c.getTotalMatrix()))

    def _draw(self, kind: str, path: skia.Path, paint: skia.Paint) -> None:
        if self.lk.get("reveal") and self.reveal < 1.0:
            self._record(kind, path, paint)
        else:
            self.c.drawPath(path, paint)

    # ---------- public API ----------
    def outline(self, path: skia.Path, w: float, color: str | None = None, alpha: float = 1.0) -> None:
        """Silhouette outline: a stroke twice as wide, half of it covered by the fills drawn next."""
        if not self.lk.get("line") or w <= 0:
            if self.mode == "paper":
                self._paper_shadow(path)
            return
        col = color or self.line_color
        if self.mode == "line_only":
            col = "#232327"
        width = 2 * w * float(self.lk.get("lw", 1.0))
        p = self._paint(col, alpha * (0.9 if self.mode == "wash" else 1.0), width)
        if (pe := self._jitter(w)):
            p.setPathEffect(pe)
        self._draw("outline", path, p)
        if self.mode == "crayon":
            p2 = self._paint(col, alpha * 0.55, width * 0.8)
            p2.setPathEffect(self._jitter(w * 1.3))
            self._draw("line", path, p2)

    def fill(self, path: skia.Path, color: str, alpha: float = 1.0, flat: bool = False) -> None:
        mode = self.mode
        if flat and mode not in ("line_only",):
            self._draw("fill", path, self._paint(color, alpha))
            return
        b = path.computeTightBounds()
        if mode == "line_only":
            self._draw("fill", path, self._paint(mix(color, "#FFFFFF", 0.5), alpha * 0.9))
            return
        if mode == "wash":
            p = self._paint(color, alpha * 0.9)
            p.setPathEffect(skia.DiscretePathEffect.Make(6.0, max(0.6, b.width() * 0.006), self._seed()))
            p.setMaskFilter(skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, 0.5 / _scale(self.c)))
            self._draw("fill", path, p)
            e = self._paint(shade(color, -0.18, 0.05), alpha * 0.32, max(1.0, b.width() * 0.025))
            e.setMaskFilter(skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, max(0.6, 1.4 / _scale(self.c))))
            self.c.save()
            self.c.clipPath(path, doAntiAlias=True)
            self._draw("fill", path, e)
            self.c.restore()
            return
        if mode == "crayon":
            p = self._paint(color, alpha * 0.93)
            p.setPathEffect(skia.DiscretePathEffect.Make(5.0, max(0.5, b.width() * 0.008), self._seed()))
            self._draw("fill", path, p)
            return
        if mode == "paper":
            self._paper_shadow(path)
            ang = (random.Random(self._seed()).random() - 0.5) * 1.6
            cx, cy = b.centerX(), b.centerY()
            self.c.save()
            self.c.rotate(ang, cx, cy)
            self._draw("fill", path, self._paint(color, alpha))
            self.c.restore()
            return
        if mode == "cel":
            d = max(b.width(), b.height()) * 0.09
            self.c.save()
            self.c.clipPath(path, doAntiAlias=self.aa)
            self._draw("fill", path, self._paint(shade(color, -0.13, 0.04), alpha))
            self.c.translate(-d * 0.55, -d)
            self._draw("fill", path, self._paint(color, alpha))
            self.c.restore()
            return
        # vector / pixel: flat with a soft top light
        p = self._paint(color, alpha)
        if self.lk["look"] == "vector" and not flat and b.height() > 0:
            p.setShader(skia.GradientShader.MakeLinear(
                [skia.Point(b.centerX(), b.top()), skia.Point(b.centerX(), b.bottom())],
                [skc(mix(color, "#FFFFFF", 0.12), alpha), skc(color, alpha)]))
        self._draw("fill", path, p)

    def shape(self, path: skia.Path, color: str, w: float, alpha: float = 1.0, line: bool = True, flat: bool = False) -> None:
        if self.lk.get("reveal") and self.reveal < 1.0:
            self.fill(path, color, alpha, flat)
            if line and self.lk.get("line"):
                self.outline(path, w * 0.5 * 2, alpha=alpha)
            return
        self.fill(path, color, alpha, flat)
        if line and self.lk.get("line"):
            width = w * float(self.lk.get("lw", 1.0))
            col = "#232327" if self.mode == "line_only" else self.line_color
            p = self._paint(col, alpha * (0.85 if self.mode == "wash" else 1.0), width)
            if (pe := self._jitter(w * 0.6)):
                p.setPathEffect(pe)
            self._draw("line", path, p)
        elif self.mode == "paper":
            pass

    def line(self, path: skia.Path, color: str, w: float, alpha: float = 1.0) -> None:
        """Open strokes (mouths, brows, motion marks)."""
        col = "#232327" if self.mode == "line_only" and color == self.line_color else color
        p = self._paint(col, alpha, w * max(0.8, float(self.lk.get("lw", 1.0)) if self.lk.get("line") else 0.9))
        if (pe := self._jitter(w * 0.5)):
            p.setPathEffect(pe)
        self._draw("line", path, p)

    def raw(self, path: skia.Path, paint: skia.Paint) -> None:
        self._draw("fill", path, paint)

    def _paper_shadow(self, path: skia.Path) -> None:
        s = _scale(self.c)
        p = self._paint("#000000", 0.28)
        p.setMaskFilter(skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, 2.4 / s))
        self.c.save()
        self.c.translate(1.6 / s, 2.6 / s)
        self._draw("fill", path, p)
        self.c.restore()

    # ---------- whiteboard: draw recorded ops progressively ----------
    def flush(self) -> tuple[float, float] | None:
        """Draw what the marker has drawn so far. Strokes are traced in drawing order; a shape's colour fades in once its
        outline is finished. While drawing, a silhouette outline (normally a double-width stroke half covered by the
        fill) is drawn at half width ON TOP of the fill: the visible line weight matches the finished frame."""
        if not self.ops:
            return None
        lens = []
        for kind, path, paint, m in self.ops:
            if kind in ("line", "outline"):
                meas = skia.PathMeasure(path, False)
                total = 0.0
                while True:
                    total += meas.getLength()
                    if not meas.nextContour():
                        break
                lens.append(total * math.sqrt(abs(m.getScaleX() * m.getScaleY())))
            else:
                lens.append(0.0)
        total_len = sum(lens) or 1.0
        budget = total_len * self.reveal
        fade = total_len * 0.08
        used = 0.0
        tip = None
        items: list[tuple[float, int, str, skia.Path, skia.Paint, skia.Matrix]] = []
        n = len(self.ops)
        stop = False
        for i, ((kind, path, paint, m), ln) in enumerate(zip(self.ops, lens)):
            if stop:
                break
            if kind == "fill":
                a = (budget - used) / fade if fade else 1.0
                if a > 0:
                    p2 = skia.Paint(paint)
                    p2.setAlphaf(paint.getAlphaf() * min(1.0, a))
                    items.append((float(i), i, kind, path, p2, m))
                continue
            sort_key = float(i)
            if kind == "outline":   # after the fills that belong to it
                j = i + 1
                while j < n and self.ops[j][0] == "fill":
                    j += 1
                sort_key = j - 0.5
            p2 = skia.Paint(paint)
            if kind == "outline":
                p2.setStrokeWidth(paint.getStrokeWidth() * 0.5)
            if used + ln <= budget:
                items.append((sort_key, i, kind, path, p2, m))
                used += ln
                continue
            part = budget - used
            if part > 0 and ln > 0:
                local = part / max(1e-6, math.sqrt(abs(m.getScaleX() * m.getScaleY())))
                p2.setPathEffect(skia.DashPathEffect.Make([max(0.01, local), 1e6], 0))
                items.append((sort_key, i, kind, path, p2, m))
                meas = skia.PathMeasure(path, False)
                res = meas.getPosTan(min(local, meas.getLength()))
                if res:
                    pos = res[0]
                    pt = m.mapXY(pos.x(), pos.y())
                    tip = (pt.x(), pt.y())
            used += max(0.0, part)
            stop = True
        self.c.save()
        for _, _, _, path, paint, m in sorted(items, key=lambda x: (x[0], x[1])):
            self.c.setMatrix(m)
            self.c.drawPath(path, paint)
        self.c.restore()
        self.ops.clear()
        self.tip = tip
        return tip
