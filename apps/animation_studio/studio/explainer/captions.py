"""Word-by-word captions (2 words at a time, big and bold, bottom third) burned into the video with ffmpeg's ASS filter."""
from __future__ import annotations

import re


def _t(sec: float) -> str:
    cs = int(round(sec * 100))
    return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"


def chunks(text: str, start: float, end: float, per: int = 2) -> list[tuple[float, float, str]]:
    """Spread the words over [start, end] by letter count (the real timing is not known for every voice)."""
    words = [w for w in re.split(r"\s+", (text or "").strip()) if w]
    if not words or end <= start:
        return []
    groups = [words[i:i + per] for i in range(0, len(words), per)]
    weights = [max(1, sum(len(w) for w in g) + len(g)) for g in groups]
    total, at, out = float(sum(weights)), start, []
    for g, wt in zip(groups, weights):
        d = (end - start) * wt / total
        out.append((round(at, 3), round(at + d, 3), " ".join(g)))
        at += d
    return out


def ass(rows: list[tuple[float, float, str]], w: int, h: int, font: str = "Arial") -> str:
    size = max(36, int(h * 0.05))
    head = (f"[Script Info]\nScriptType: v4.00+\nPlayResX: {w}\nPlayResY: {h}\nWrapStyle: 2\n\n[V4+ Styles]\n"
            "Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,"
            "ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding\n"
            f"Style: Default,{font},{size},&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,{max(3, size // 9)},2,2,40,40,{int(h * 0.14)},1\n\n"
            "[Events]\nFormat: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text\n")
    body = "".join(f"Dialogue: 0,{_t(a)},{_t(b)},Default,,0,0,0,,{t.upper().replace(chr(10), ' ')}\n" for a, b, t in rows if t)
    return head + body
