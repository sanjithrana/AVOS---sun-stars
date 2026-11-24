"""Which seconds of a video are worth clipping: every signal there is, weighted, on one timeline.

Signal       | what it measures                                              | weight
------------ | ------------------------------------------------------------- | ------
visual       | gameplay events: motion, hard cuts, flashes, camera shake      | 0.35
audio        | loudness, sudden jumps, build-ups (and talking pace)           | 0.25
reaction     | the streamer's cam moving (leaning in, jumping, laughing)      | 0.20
chat         | live-chat bursts from the replay (Twitch, Kick, YouTube live)  | 0.15
replay       | YouTube's "most replayed" graph                                | 0.15
comments     | timestamps viewers wrote in the comments ("4:32 💀")           | 0.10
voice        | a quiet streamer suddenly talking fast (reacting to something) | 0.12
words        | excited words in the captions ("no way", "bro", "!")           | 0.08

The weights are a starting point, not a measured result. A signal that is missing for a video (no chat, no comments, not
downloaded so no picture) is left out and the others share its weight; it never counts as zero. Seconds where several signals
agree score higher than any one alone. Every clip keeps a breakdown of what picked it ("why")."""
from __future__ import annotations

import json
import math
import re
import subprocess
from pathlib import Path
from typing import Callable

WEIGHTS = {"visual": 0.35, "audio": 0.25, "reaction": 0.20, "chat": 0.15, "replay": 0.15, "comments": 0.10, "voice": 0.12, "words": 0.08}
NAMES = {"visual": "Visual action", "audio": "Audio excitement", "reaction": "Streamer reaction", "chat": "Live chat", "replay": "Replay graph",
         "comments": "Comment timestamps",
         "voice": "Voice comes back", "words": "Excited words"}


def combine(sig: dict[str, list[float]], n: int) -> tuple[list[float], list[str]]:
    """One 0..1 score a second from the signals present. Returns (curve, names of the signals used)."""
    have = {k: v for k, v in sig.items() if k in WEIGHTS and v and max(v) > 0}
    if not have:
        return [0.0] * n, []
    tot = sum(WEIGHTS[k] for k in have)
    g = lambda a, i: a[i] if i < len(a) else 0.0  # noqa: E731
    out = []
    for i in range(n):
        vals = {k: max(0.0, min(1.0, g(v, i))) for k, v in have.items()}
        base = sum(WEIGHTS[k] * x for k, x in vals.items()) / tot
        agree = sum(1 for x in vals.values() if x >= 0.6)
        bonus = 0.12 * max(0, agree - 1) if len(have) > 1 else 0.0          # two or more signals peaking together: a real moment
        out.append(min(1.0, base + bonus))
    return out, list(have)


def why(sig: dict[str, list[float]], offset: float, a: float, b: float) -> dict[str, float]:
    """How strongly each signal fired inside [a, b] (its best second, 0..1), strongest first: the reason a clip was chosen."""
    out = {}
    i0, i1 = max(0, int(a - offset)), max(0, int(b - offset))
    for k, v in sig.items():
        if v and i1 > i0:
            seg = v[i0: i1 + 1]
            if seg:
                out[k] = round(max(seg), 2)
    return dict(sorted(out.items(), key=lambda kv: -kv[1]))


def save(d: Path, sig: dict[str, list[float]], offset: float) -> None:
    (d / "signals.json").write_text(json.dumps({"offset": offset, "signals": {k: [round(x, 3) for x in v] for k, v in sig.items() if v}}), "utf-8")


def load(d: Path) -> tuple[dict[str, list[float]], float]:
    try:
        j = json.loads((d / "signals.json").read_text("utf-8"))
        return j["signals"], float(j["offset"])
    except Exception:  # noqa: BLE001
        return {}, 0.0


# ---------- comment timestamps ----------
TS = re.compile(r"(?<![\d:])(?:(\d{1,2}):)?([0-5]?\d):([0-5]\d)(?![\d:])")


def times_in(text: str) -> list[int]:
    out = []
    for m in TS.finditer(text or ""):
        h, mi, s = int(m.group(1) or 0), int(m.group(2)), int(m.group(3))
        out.append(h * 3600 + mi * 60 + s)
    return out


def comments_curve(comments: list[dict], duration: float) -> list[float]:
    """Each timestamp a viewer wrote ("4:32"), weighted by its likes, spread over the moment it points at (a little before, more after)."""
    n = int(duration) + 1
    v = [0.0] * n
    hits = 0
    for c in comments:
        w = 1.0 + math.log10(1 + max(0, int(c.get("like_count") or 0)))
        for t in times_in(c.get("text") or ""):
            if 0 <= t < duration:
                hits += 1
                for dt in range(-4, 13):
                    i = t + dt
                    if 0 <= i < n:
                        v[i] += w * math.exp(-((dt - 3) ** 2) / 40.0)
    if hits < 2:                                             # one stray timestamp is not a signal
        return []
    top = max(v) or 1.0
    return [x / top for x in v]


def comments(url: str, dest: Path, cancel: Callable[[], None] | None = None, limit: int = 400) -> list[dict]:
    """The top comments of a YouTube video (text and likes), read with yt-dlp. Empty when there are none or it fails."""
    if "youtu" not in (url or ""):
        return []
    from .intake import ytdlp_base
    try:
        r = subprocess.run(ytdlp_base() + ["--no-warnings", "--skip-download", "--write-comments", "--dump-single-json",
                                           "--extractor-args", f"youtube:max_comments={limit},all,0;comment_sort=top", url],
                           capture_output=True, text=True, timeout=240)
        if cancel:
            cancel()
        data = json.loads(r.stdout) if r.returncode == 0 and r.stdout.strip() else {}
    except Exception:  # noqa: BLE001
        return []
    out = [{"text": c.get("text") or "", "like_count": c.get("like_count") or 0} for c in data.get("comments") or []]
    try:
        (dest / "comments.json").write_text(json.dumps(out[:limit]), "utf-8")
    except OSError:
        pass
    return out


def cam_region(src: str, start: float, end: float, folder: Path) -> tuple[float, float, float, float] | None:
    """Where the streamer's cam is (x, y, w, h as shares of the frame), from ~40 frames spread over the video; None when there is none."""
    try:
        from . import reframe
        sw, sh, _ = reframe.probe(src)
        dur = max(1.0, end - start)
        files = reframe.sample_frames(src, start, dur, folder, fps=min(1.0, 40.0 / dur))
        cam = reframe.stream_cam(reframe.look(files), sw, sh)
    except Exception:  # noqa: BLE001
        return None
    if not cam:
        return None
    cx, cy, fw = cam
    w = min(0.45, fw * 4.0)
    h = min(0.6, w * sw / sh * 0.75)
    return (max(0.0, cx - w / 2), max(0.0, cy - h * 0.45), w, h)
