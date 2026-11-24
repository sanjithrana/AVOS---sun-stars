"""Finding the hype: where the video gets loud, fast, excited or busy, and cutting a clip around exactly that.

A "hype curve" has one number between 0 and 1 per second. It mixes
  loudness      how loud this second is compared with the rest of the video (rank, so one scream doesn't flatten everything else)
  rise          how much louder it just got (the build-up, the reaction, the drop)
  speech pace   words per second
  excitement    words like "wow", "no way", "let's go", "clutch", exclamation marks, shouting in capitals
  motion        how much the picture changes (fights, chases, goals; optional, short videos only)
A moment is a peak in that curve plus the build-up before it and the aftermath after it. Quiet stretches never become clips."""
from __future__ import annotations

import re
import subprocess
from typing import Any

from .. import config

EXCITED = set("""wow omg whoa no way crazy insane unreal unbelievable what the hell lets go let's go yes yeah boom clutch ace goal scored win won winner
dead died kill killed killing shot headshot fire fired fast incredible amazing huge massive never believe look watch sick damn bro bhai pagal gajab
mast kamaal zabardast arre oye chal""".split())
LEVELS = {"strict": 0.62, "balanced": 0.5, "more": 0.38}
YDIF = re.compile(r"lavfi\.signalstats\.YDIF=([\d.]+)")


def _rank(vals: list[float]) -> list[float]:
    """Each value as its rank in 0..1 (0 = lowest second, 1 = highest)."""
    n = len(vals)
    if n < 2:
        return [0.5] * n
    order = sorted(range(n), key=lambda i: vals[i])
    out = [0.0] * n
    for r, i in enumerate(order):
        out[i] = r / (n - 1)
    return out


def _smooth(v: list[float], k: int) -> list[float]:
    return [sum(v[max(0, i - k): i + k + 1]) / len(v[max(0, i - k): i + k + 1]) for i in range(len(v))]


def motion(path: str, start: float, end: float | None, max_minutes: int = 45) -> list[float] | None:
    """Picture change per second (0..1 by rank) from a tiny 4 fps copy of the video. None when it is too long to be worth it or fails."""
    if end is not None and (end - start) > max_minutes * 60:
        return None
    cmd = [config.ffmpeg(), "-v", "error", "-nostdin"]
    if start:
        cmd += ["-ss", f"{start:.2f}"]
    cmd += ["-i", path]
    if end:
        cmd += ["-t", f"{max(1.0, end - start):.2f}"]
    cmd += ["-an", "-vf", "fps=4,scale=64:-2,signalstats,metadata=print:key=lavfi.signalstats.YDIF:file=-", "-f", "null", "-"]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
    except Exception:  # noqa: BLE001
        return None
    vals = [float(m.group(1)) for m in YDIF.finditer(r.stdout)]
    if len(vals) < 8:
        return None
    sec = [max(vals[i: i + 4]) for i in range(0, len(vals) - 3, 4)]
    srt = sorted(sec)
    med, p95 = srt[len(srt) // 2], srt[int(len(srt) * 0.95)]
    span = max(p95 - med, 1.0)                  # a video that barely changes has no motion hype
    return [max(0.0, min(1.0, (v - med) / span)) for v in sec]


def curve(levels: list[float], words: list[dict] | None = None, offset: float = 0.0, mot: list[float] | None = None) -> list[float]:
    """levels = RMS dB per second (index 0 = `offset` in the source). Returns hype 0..1 per second, same length."""
    n = len(levels)
    sl = _smooth(levels, 1)
    srt = sorted(sl)
    med, p95 = srt[n // 2], srt[min(n - 1, int(n * 0.95))]
    span = max(6.0, p95 - med)                  # judged against this video's own level, but a flat video (all one loudness) stays at ~0
    loud = [max(0.0, min(1.0, (v - med) / span)) for v in sl]
    rise = [max(0.0, min(1.0, (levels[i] - (sum(levels[max(0, i - 4): i]) / max(1, len(levels[max(0, i - 4): i])) if i else levels[0])) / 10.0)) for i in range(n)]
    csum = [0.0]
    for x in sl:
        csum.append(csum[-1] + x)
    jump = []                                   # how far this second sits above the previous two minutes: a boom or shout stands out even in a loud video
    for i in range(n):
        lo, hi = max(0, i - 123), max(0, i - 3)
        base = (csum[hi] - csum[lo]) / (hi - lo) if hi > lo else sl[0]
        jump.append(max(0.0, min(1.0, (sl[i] - base) / 9.0)))
    pace, lex = [0.0] * n, [0.0] * n
    for w in words or []:
        i = int(w["s"] - offset)
        if 0 <= i < n:
            pace[i] += 1
            tok = re.sub(r"[^a-z']", "", w["w"].lower())
            if tok in EXCITED or w["w"].endswith("!") or (len(w["w"]) > 2 and w["w"].isupper()):
                lex[i] += 1
    pace = [min(1.0, p / 4.5) for p in pace]
    lex = [min(1.0, 0.6 * l) for l in lex]
    speech = bool(words)
    if mot is not None:
        mot = (mot + [mot[-1]] * n)[:n] if mot else [0.0] * n
    wts = {"loud": 0.28 if speech else 0.34, "rise": 0.16 if speech else 0.16, "jump": 0.18 if speech else 0.3, "pace": 0.12 if speech else 0.0, "lex": 0.12 if speech else 0.0, "mot": 0.18 if mot is not None else 0.0}
    tot = sum(wts.values())
    h = [(wts["loud"] * loud[i] + wts["rise"] * rise[i] + wts["jump"] * jump[i] + wts["pace"] * pace[i] + wts["lex"] * lex[i] + (wts["mot"] * mot[i] if mot is not None else 0)) / tot for i in range(n)]
    return _smooth(h, 1)


def moments(h: list[float], count: int, min_s: int, max_s: int, cues: list[dict] | None = None, offset: float = 0.0, level: str = "balanced", snap: Any = None, lead: int = 2) -> list[dict]:
    """Up to `count` clips, each built around one peak of the hype curve. Fewer than `count` when the video doesn't have that many hype moments."""
    n = len(h)
    sm = _smooth(h, 2)
    if level == "relative":                      # last resort: this video's own best moments, however calm the video is overall
        srt = sorted(sm)
        thr = max(0.03, srt[min(n - 1, int(n * 0.985))]) if n else 0.03
    else:
        thr = LEVELS.get(level, LEVELS["balanced"])
    peaks = [i for i in range(n) if sm[i] >= thr and sm[i] >= max(sm[max(0, i - 3): i + 4]) - 1e-9]
    peaks.sort(key=lambda i: -sm[i])
    taken: list[tuple[int, int]] = []
    out: list[dict] = []
    for p in peaks:
        # build-up: back while the curve stays above 45% of the way up, aftermath: forward the same way
        lo = 0.45 * sm[p]
        s = p
        while s > 0 and sm[s - 1] >= lo and p - s < max_s * 0.45:
            s -= 1
        e = p
        while e < n - 1 and sm[e + 1] >= lo and e - p < max_s * 0.5:
            e += 1
        s, e = max(0, s - lead), min(n, e + 3)                               # a beat of lead-in and a tail
        length = e - s
        if length < min_s:                                                # too short: add context, a little more before than after
            need = min_s - length
            s, e = max(0, s - int(need * 0.45)), min(n, e + need - int(need * 0.45))
            if e - s < min_s:
                s = max(0, e - min_s)
                e = min(n, s + min_s)
        if e - s > max_s:
            s = max(s, p - int(max_s * 0.45))
            e = min(n, s + max_s)
        if e - s < min_s or any(not (e + 2 <= a or s >= b + 2) for a, b in taken):
            continue
        taken.append((s, e))
        a, b = (snap(s + offset, e + offset, cues or [], min_s, max_s) if snap else (s + offset, e + offset))
        seg = h[s:e]
        out.append({"start": round(a, 2), "end": round(b, 2), "score": round(10 * sum(seg) / max(1, len(seg)), 2), "hype": round(sm[p], 2), "peak": round(p + offset, 1)})
        if len(out) >= count:
            break
    out.sort(key=lambda m: m["start"])
    return out


def peaks_in(h: list[float], offset: float, start: float, end: float, level: str = "balanced", limit: int = 3, gap: float = 6.0) -> list[float]:
    """Times (seconds from the clip's start) of the hype peaks inside a clip, for the flash / shake / glitch effects."""
    thr = max(LEVELS.get(level, 0.5), 0.45)
    sm = _smooth(h, 2)
    cand = [i for i in range(len(sm)) if offset + i >= start + 1.0 and offset + i <= end - 1.0 and sm[i] >= thr and sm[i] >= max(sm[max(0, i - 3): i + 4]) - 1e-9]
    cand.sort(key=lambda i: -sm[i])
    out: list[float] = []
    for i in cand:
        t = offset + i - start
        if all(abs(t - x) >= gap for x in out):
            out.append(round(t + 0.3, 2))
        if len(out) >= limit:
            break
    return sorted(out)


def dead_zones(total: float, words: list[dict] | None, talk: bool, start: float = 0.0, end: float | None = None) -> list[tuple[float, float]]:
    """Stretches no clip may come from: the intro (first 20 s) and the outro / end credits (last 4%, at least 45 s) of a video longer than
    5 minutes, and, in a video of people talking, any 30 s stretch where nobody says anything (music, credits, a title card, dead air)."""
    end = total if end is None else end
    z: list[tuple[float, float]] = []
    if total >= 300:
        z.append((0.0, 20.0))
        z.append((max(0.0, total - max(45.0, 0.04 * total)), total + 1))
    ws = [w for w in (words or []) if start <= w["s"] <= end and w.get("w") and w["w"][0] not in "[(♪♫" and any(ch.isalnum() for ch in w["w"])]
    span = max(1.0, end - start)
    if talk and len(ws) / span >= 0.5:                     # the video does have speech: quiet-of-words stretches are not moments
        t = start
        while t < end:
            n = sum(1 for w in ws if t <= w["s"] < t + 30)
            if n < 12:                                     # under 0.4 words a second
                z.append((t, t + 30))
            t += 10
    return z


def mask(vals: list[float], offset: float, zones: list[tuple[float, float]], floor: float = 0.0) -> list[float]:
    """The curve (one value a second from `offset`) with the dead zones flattened, so nothing there can be picked."""
    out = list(vals)
    for a, b in zones:
        for i in range(max(0, int(a - offset)), min(len(out), int(b - offset) + 1)):
            out[i] = floor
    return out


def speech_rate(words: list[dict] | None, a: float, b: float) -> float:
    n = sum(1 for w in (words or []) if a <= w["s"] < b and w.get("w") and w["w"][0] not in "[(♪♫" and any(ch.isalnum() for ch in w["w"]))
    return n / max(1.0, b - a)
