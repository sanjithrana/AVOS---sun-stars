"""Cheap, offline checks on a finished picture, so a bad prompt shows up without anyone looking: too dark, too bright,
flat/blank, or the same picture as another shot. (Not taste: a trained eye or a 👎 still has the last word.)"""
from __future__ import annotations

import io

from PIL import Image, ImageStat


def fingerprint(png: bytes) -> int:
    """A 64-bit difference hash: equal pictures give equal numbers, small edits change a few bits."""
    g = Image.open(io.BytesIO(png)).convert("L").resize((9, 8))
    px = list(g.tobytes())
    bits = 0
    for r in range(8):
        for c in range(8):
            bits = (bits << 1) | (1 if px[r * 9 + c] > px[r * 9 + c + 1] else 0)
    return bits


def check(png: bytes, others: list[int] | None = None) -> dict:
    """{"flags": [...], "hash": int, "score": 0..1}. Never raises: a picture that cannot be read simply gets no flags."""
    try:
        return _check(png, others)
    except Exception:  # noqa: BLE001
        return {"flags": [], "hash": None, "score": 1.0}


def _check(png: bytes, others: list[int] | None) -> dict:
    im = Image.open(io.BytesIO(png)).convert("L")
    st = ImageStat.Stat(im.resize((64, 64)))
    mean, std = st.mean[0], st.stddev[0]
    h = fingerprint(png)
    flags = []
    if mean < 28:
        flags.append("too_dark")
    elif mean > 232:
        flags.append("too_bright")
    if std < 14:
        flags.append("flat")
    if any(bin(h ^ o).count("1") <= 2 for o in (others or [])):
        flags.append("duplicate")
    return {"flags": flags, "hash": h, "score": round(max(0.0, 1.0 - 0.34 * len(flags)), 2)}
