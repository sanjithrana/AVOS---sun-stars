"""Where a clip starts and ends, to the second. The cut decides the views more than the topic does.

Ported from AutoClip by zhouxiaoka (github.com/zhouxiaoka/autoclip, backend/services/studio/boundaries.py and
game_highlights.py, MIT licence, Copyright (c) 2024 AutoClip Team) and adapted to our word timings.

1. Never end on the host's next question: a question in the last 20 s followed by under 12 s of answer is cut off,
   the clip ends where the sentence before it ends.
2. Start on the moment: when the strongest second (a reaction, a hit, a shout) is just after the start, move the start to
   the sentence edge just before it so it shows inside the first 1.5 s, instead of a slow lead-in.
3. Hold the reaction: when the signals are still high at the end, keep up to 2.5 s more so the laugh or "NO WAY" lands.
4. The voice coming back: in a game, a streamer who goes quiet and then suddenly talks fast is reacting to something
   that just happened. Those seconds are a signal of their own ("voice")."""
from __future__ import annotations

from .craft import sentences

TRAILING_QUESTION_SEC = 20.0
ANSWER_STUB_SEC = 12.0
PEAK_WINDOW = 6.0          # look this far after the start for the moment
PEAK_LEAD = 1.5            # the moment shows this soon after the start
HOLD_MAX = 2.5


def drop_trailing_question(m: dict, words: list[dict], min_s: float) -> dict:
    a, b = float(m["start"]), float(m["end"])
    ss = [x for x in sentences([w for w in words if a - 0.05 <= w["s"] < b])]
    if len(ss) < 2:
        return m
    texts = []
    for x in ss:
        texts.append(" ".join(w["w"] for w in words if x["s"] - 0.01 <= w["s"] <= x["e"] + 0.01))
    for k in range(len(ss) - 1, 0, -1):
        x = ss[k]
        if x["e"] < b - TRAILING_QUESTION_SEC:
            break
        if texts[k].rstrip().endswith(("?", "？")) and b - x["e"] <= ANSWER_STUB_SEC:
            end = ss[k - 1]["e"] + 0.15
            if end - a >= min_s - 3:                   # only when the clip stays about as long as asked
                n = dict(m)
                n["end"] = round(end, 2)
                n["cut_question"] = True
                return n
            break
    return m


def _at(curve: list[float], offset: float, t: float) -> float:
    i = int(t - offset)
    return curve[i] if 0 <= i < len(curve) else 0.0


def start_on_peak(m: dict, curve: list[float] | None, offset: float, words: list[dict] | None, min_s: float) -> dict:
    """Move the start forward so the strongest second near it shows within PEAK_LEAD s (only to a sentence or pause edge)."""
    if not curve:
        return m
    a, b = float(m["start"]), float(m["end"])
    span = [(_at(curve, offset, a + k), a + k) for k in range(int(PEAK_WINDOW) + 1)]
    best, t = max(span)
    base = _at(curve, offset, a)
    if best < 0.55 or best < base + 0.15 or t - a <= PEAK_LEAD:
        return m
    want = t - PEAK_LEAD
    if words:
        edges = [x["s"] for x in sentences(words) if a < x["s"] <= want + 0.4]
        if not edges:
            return m                                      # no sentence starts there: cutting would chop a word
        want = max(edges)
    if b - want < min_s - 3:
        return m
    n = dict(m)
    n["start"] = round(want, 2)
    return n


def hold_reaction(m: dict, curve: list[float] | None, offset: float, total: float | None = None) -> dict:
    if not curve:
        return m
    b = float(m["end"])
    extra = 0.0
    while extra < HOLD_MAX and _at(curve, offset, b + extra) >= 0.6:
        extra += 0.5
    if not extra:
        return m
    n = dict(m)
    n["end"] = round(min(b + extra, total or b + extra), 2)
    return n


def voice_return(words: list[dict] | None, n: int, offset: float = 0.0, quiet: float = 2.5, burst: int = 4, within: float = 2.0) -> list[float]:
    """0..1 a second: high right after a silence of `quiet` s that ends in `burst` words inside `within` s (the streamer reacting)."""
    if not words or n <= 0:
        return []
    v = [0.0] * n
    ws = sorted(words, key=lambda w: w["s"])
    hits = 0
    for i in range(1, len(ws)):
        gap = ws[i]["s"] - ws[i - 1]["e"]
        if gap < quiet:
            continue
        j = i
        while j < len(ws) and ws[j]["s"] - ws[i]["s"] <= within:
            j += 1
        if j - i < burst:
            continue
        hits += 1
        t0 = ws[i]["s"] - offset
        strength = min(1.0, 0.5 + (j - i) / 12 + min(gap, 10) / 20)
        for dt in range(-3, 4):                           # the cause is a moment before the voice
            k = int(t0) + dt
            if 0 <= k < n:
                v[k] = max(v[k], strength * (1.0 - abs(dt + 1) / 4))
    return v if hits >= 1 else []


def no_dead_open(m: dict, words: list[dict] | None, min_s: float) -> dict:
    """The first word is heard within half a second (Virality skill, checklist point 6): cut away silent lead-in."""
    if not words:
        return m
    a, b = float(m["start"]), float(m["end"])
    first = next((w for w in words if a - 0.05 <= w["s"] < min(b, a + 4.0)), None)
    if not first or first["s"] - a <= 0.5:
        return m
    start = round(first["s"] - 0.2, 2)
    if b - start < min_s - 3:
        return m
    n = dict(m)
    n["start"] = start
    return n


def refine(moments: list[dict], words: list[dict] | None, curve: list[float] | None, offset: float, min_s: float, total: float | None = None) -> list[dict]:
    out = []
    for m in moments:
        if words:
            m = drop_trailing_question(m, words, min_s)
        m = start_on_peak(m, curve, offset, words, min_s)
        m = no_dead_open(m, words, min_s)
        if not m.get("cut_question"):
            m = hold_reaction(m, curve, offset, total)
        out.append(m)
    return out
