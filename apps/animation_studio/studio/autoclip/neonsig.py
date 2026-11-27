"""The NeonClipping engine's moment finders, inside Auto Clip.

Adapted from NeonClipping by Ajay K Meena and contributors (github.com/iamajmeena/neonclipping, commit c0edf73, MIT License,
Copyright (c) 2026 Ajay K Meena and NeonClipping contributors): highlights.py (audio and optical-flow signals), excite.py
(what is said), curation.py (filler, hooks, varied selection) and scene_edges.py (cut on a scene change). Their parts
adapted from PeakCut are MIT too. Rewritten for Auto Clip's per-second signal timeline (signals.combine).

  loud   a sudden boom or shout against the last two minutes (local z-score), so a constantly loud stream does not win
  shout  energy in the 2-4 kHz band (raised voices, screams, impacts), weighted by loudness
  bang   gunfire (several sharp onsets in a second) and explosions or crashes (a jump of 25-200 Hz energy)
  flow   optical flow at 160x90, 3 frames a second (fast objects, impacts, camera whips); hard cuts counted apart
  excite exclamations and game events in the transcript: English, Hinglish and Hindi ("oh my god", "bhaago", "wasted")"""
from __future__ import annotations

import os
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor

SR = 8000
FPS, FW, FH, CUT = 3, 160, 90, 38.0


def _ff() -> str:
    try:
        from .. import config
        return config.ffmpeg()
    except Exception:  # noqa: BLE001
        return "ffmpeg"


def z(x, n: int, win: int = 120):
    """Local z-score against a rolling baseline of `win` seconds, 0..1 (z of 3.5 = 1)."""
    import numpy as np
    out = np.zeros(n)
    if x is None or not len(x):
        return out
    y = np.zeros(n)
    y[:min(n, len(x))] = np.asarray(x[:n], dtype=float)
    win = max(1, min(win, n))
    k = np.ones(win) / win
    mu = np.convolve(y, k, "same")
    sd = np.sqrt(np.maximum(np.convolve(y * y, k, "same") - mu * mu, 0)) + 1e-6
    return np.clip((y - mu) / sd / 3.5, 0, 1)


def game_sounds(x, sr: int = SR):
    """(bursts, booms) a second: sharp onsets (gunfire) and low-frequency jumps (explosions, crashes)."""
    import numpy as np
    hop = sr // 25
    n = len(x) // sr
    if n == 0:
        return np.zeros(0), np.zeros(0)
    onsets, booms = np.zeros(n), np.zeros(n)
    win = np.hanning(hop)
    for a in range(0, n, 600):
        b = min(n, a + 600)
        fr = x[a * sr:b * sr].reshape(-1, hop)
        spec = np.abs(np.fft.rfft(fr * win, axis=1)) ** 2
        total = np.log1p(spec.sum(1) * 1e3)
        low = np.log1p(spec[:, 1:9].sum(1) * 1e3)
        flux = np.maximum(0, np.diff(total, prepend=total[:1]))
        jump = np.maximum(0, np.diff(low, prepend=low[:1]))
        med = np.median(flux)
        mad = np.median(np.abs(flux - med)) + 1e-6
        onsets[a:b] = (flux > med + 6 * mad).reshape(-1, 25).sum(1)
        booms[a:b] = jump.reshape(-1, 25).max(1)
    return onsets, booms


def audio(src: str, start: float = 0.0, end: float | None = None) -> dict[str, list[float]]:
    """{"loud", "shout", "bang"} 0..1 a second from `start`. Empty dict when there is no sound."""
    import numpy as np
    cmd = [_ff(), "-nostdin", "-v", "error", "-ss", f"{start:.3f}"] + (["-t", f"{end - start:.3f}"] if end else []) + \
          ["-i", str(src), "-vn", "-ac", "1", "-ar", str(SR), "-f", "s16le", "pipe:1"]
    try:
        raw = subprocess.run(cmd, capture_output=True, stdin=subprocess.DEVNULL, timeout=4 * 3600).stdout
    except Exception:  # noqa: BLE001
        return {}
    x = np.frombuffer(raw[:len(raw) // 2 * 2], np.int16).astype(np.float32) / 32768
    n = len(x) // SR
    if n < 3:
        return {}
    bursts, booms = game_sounds(x[:n * SR])
    x = x[:n * SR].reshape(n, SR)
    rms = np.sqrt((x ** 2).mean(1))
    hf = np.empty(n)
    win = np.hanning(SR)
    for i in range(0, n, 300):                      # 5 minutes at a time keeps memory small
        spec = np.abs(np.fft.rfft(x[i:i + 300] * win, axis=1)) ** 2
        hf[i:i + 300] = spec[:, 2000:4000].sum(1) / (spec.sum(1) + 1e-9)
    loud = z(rms, n)
    shout = np.clip(z(hf * rms, n), 0, 1)
    bang = np.maximum(z(bursts, n, 300), z(booms, n, 300))
    return {"loud": [round(float(v), 3) for v in loud], "shout": [round(float(v), 3) for v in shout], "bang": [round(float(v), 3) for v in bang]}


def audio_curve(a: dict[str, list[float]]) -> list[float]:
    """NeonClipping's audio mix: 0.45 loud + 0.35 shout + 0.20 bang."""
    if not a:
        return []
    return [round(min(1.0, 0.45 * lo + 0.35 * sh + 0.20 * ba), 3) for lo, sh, ba in zip(a["loud"], a["shout"], a["bang"])]


def _flow_chunk(src: str, start: float, length: float):
    import cv2
    import numpy as np
    cmd = [_ff(), "-v", "error", "-ss", f"{start}", "-t", f"{length}", "-i", str(src), "-an", "-vf", f"fps={FPS},scale={FW}:{FH}",
           "-pix_fmt", "gray", "-f", "rawvideo", "pipe:1"]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=FW * FH * 64)
    flow, cuts, prev = [], [], None
    try:
        while True:
            raw = p.stdout.read(FW * FH)
            if len(raw) != FW * FH:
                break
            cur = np.frombuffer(raw, np.uint8).reshape(FH, FW)
            if prev is None:
                flow.append(0.0)
                cuts.append(0.0)
            elif float(np.mean(cv2.absdiff(cur, prev))) > CUT:
                flow.append(0.0)
                cuts.append(1.0)
            else:
                f = cv2.calcOpticalFlowFarneback(prev, cur, None, 0.5, 2, 9, 2, 5, 1.1, 0)
                flow.append(float(np.percentile(np.hypot(f[..., 0], f[..., 1]), 90)))
                cuts.append(0.0)
            prev = cur
        p.wait()
    finally:
        if p.poll() is None:
            p.kill()
            p.wait()
        p.stdout.close()
    k = len(flow) // FPS * FPS
    return (np.array(flow[:k]).reshape(-1, FPS).mean(1) if k else np.zeros(0), np.array(cuts[:k]).reshape(-1, FPS).sum(1) if k else np.zeros(0))


def motion(src: str, start: float, end: float) -> list[float]:
    """0..1 a second: 0.6 optical flow + 0.4 cut density, both against the local baseline. Empty without OpenCV."""
    try:
        import cv2  # noqa: F401
        import numpy as np
    except Exception:  # noqa: BLE001
        return []
    dur = max(0.0, end - start)
    if dur < 3:
        return []
    workers = max(2, min(8, (os.cpu_count() or 4) - 2))
    size = max(60, int(-(-dur // workers // 60) * 60))
    starts = [start + s for s in range(0, int(dur), size)]
    try:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            parts = list(pool.map(lambda s: _flow_chunk(src, s, min(size, end - s)), starts))
    except Exception:  # noqa: BLE001
        return []
    f = np.concatenate([p[0] for p in parts]) if parts else np.zeros(0)
    c = np.concatenate([p[1] for p in parts]) if parts else np.zeros(0)
    n = int(dur)
    if len(f) < 3:
        return []
    return [round(float(v), 3) for v in np.clip(0.6 * z(f, n) + 0.4 * z(c, n), 0, 1)]


# ---------- what is said ----------
_LEX = [
    (r"oh my (god|gosh)|omg|oh shit|holy (shit|crap|fuck|hell)?|no way|what the (fuck|f|hell)|wtf|oh no+|nooo+|oh fuck|oh god", 3),
    (r"let'?s go+|lets go+|insane|crazy|bruh|yooo+|yoo+|ayo|bro+\b|dude|sheesh|goat|clip (it|that)", 2),
    (r"run|run run|go go|get out|watch out|behind you|help|police|cops?|chase|chasing|wanted|swat|shoot|shot|shooting|gun|kill|killed|dead|die|dying|dies", 2),
    (r"boom|explo\w*|blast|blow|crash\w*|fire|burn\w*|bomb|grenade|rocket|jump|flip\w*|fall\w*|drop\w*|ahh+|aaa+h*|scream\w*", 2),
    (r"are+ yaar|arre+|are bhai|oye+|abe+|bhaag\w*|bhago|bachao|pulis|police wale|maar\w*|gaya|goli\w*|dhamaka|uff+|oh teri|kya baat|zabardast|pagal|mast|jhakaas|hat\s*teri", 2),
    (r"अरे+|भागो|भाग|बचाओ|पुलिस|मार|मर गया|गोली|धमाका|ब्लास्ट|पागल|उफ़|ओए|यार", 2),
    (r"wasted|busted|mission (passed|failed|complete)|wanted level|(five|5|six|6) stars?|cops? (are )?coming|heist|bank robbery|getaway", 3),
    (r"headshot|head shot|one tap|ace|clutch|(1|one) (v|vs) (\d|one|two|three|four)|squad wipe|wiped|knocked|eliminated|victory royale|chicken dinner|booyah|winner winner", 3),
    (r"double kill|triple kill|quadra kill|penta kill|multi kill|killstreak|kill streak|last (one|man|zone)|final circle|zone", 2),
    (r"वांटेड|बस्टेड|वेस्टेड|मिशन|हेडशॉट|बूयाह|क्लच", 3),
]
_RX = [(re.compile(p, re.I), w) for p, w in _LEX]
_WEAK = {"oh", "ooh", "whoa", "woah", "wow", "yo", "holy", "damn", "dang", "ugh", "aah", "ahh", "ah", "bro", "brother", "nah", "what", "no", "wait",
         "stop", "yes", "yeah", "arre", "are", "abe", "oye", "uff", "अरे", "ओए", "उफ़", "वाह", "नहीं"}


def word_weight(text: str) -> float:
    t = text.strip().lower()
    if not t:
        return 0.0
    w = 0.0
    for rx, wt in _RX:
        m = rx.search(t)
        if rx.fullmatch(t) or (len(t) > 3 and m and m.group(0) == t):
            w = max(w, wt)
    if w == 0 and t.strip(",.!?") in _WEAK:
        w = 0.7
    if t.endswith("!"):
        w += 1.0
    return w


def _phrase(words: list[dict], i: int) -> float:
    best = 0.0
    for n in (3, 2):
        if i + n <= len(words):
            joined = " ".join(str(w["w"]).strip(",.!?").lower() for w in words[i:i + n])
            for rx, wt in _RX:
                m = rx.search(joined)
                if m and len(m.group(0)) >= len(joined) - 1:
                    best = max(best, wt)
    return best


def excite(words: list[dict] | None, n: int, offset: float = 0.0) -> list[float]:
    """0..1 a second (smoothed over 5 s) from exclamations and game events; `words` are {w, s, e} on the video's clock."""
    import numpy as np
    if not words or n <= 0:
        return []
    sig = np.zeros(n)
    ws = sorted(words, key=lambda w: w["s"])
    for i, w in enumerate(ws):
        wt = max(word_weight(str(w["w"])), _phrase(ws, i))
        k = int(w["s"] - offset)
        if wt and 0 <= k < n:
            sig[k] += wt
    if not sig.any():
        return []
    sig = np.minimum(sig, 6)
    sm = np.convolve(sig, np.ones(5) / 5, "same")
    peak = max(float(np.percentile(sm[sm > 0], 95)), 1.0)
    return [round(float(v), 3) for v in np.clip(sm / peak, 0, 1)]


GAME_EVENT = re.compile("|".join(p for p, _ in _LEX[6:]), re.I)


def game_events(text: str) -> list[str]:
    return sorted({m.group(0).lower() for m in GAME_EVENT.finditer(text or "")})[:5]


# ---------- choosing and wording ----------
_FILLER = ("like and subscribe", "hit the bell", "follow me", "we will start soon", "give me a minute", "welcome back everyone", "thanks for watching")


def filler(text: str) -> bool:
    """Two or more promo lines in a stretch: an intro or an outro, not a moment."""
    low = (text or "").casefold()
    return sum(p in low for p in _FILLER) >= 2


_CHAT = r"(?:ar+e+|arey+|arre+|abe+|uh+|um+|hmm+|oh+|yo+|hey+)"


def extract_hook(text: str) -> str:
    """The clip's own strongest line, at most nine words, for the opening heading when no AI wrote one."""
    text = re.sub(r"(?<!\w)" + _CHAT + r"(?:[\s,]+(?:" + _CHAT + r"))+(?!\w)", " ", text or "", flags=re.I).strip(" ,")
    sentences = [s.strip() for s in re.split(r"[.!?।\n]+", text) if len(s.split()) >= 3]
    if not sentences:
        return " ".join(text.split()[:9])[:80]
    cues = ("but", "instead", "wrong", "stuck", "finally", "silence", "impact", "whole time", "mistake", "lekin", "isliye", "galti", "actually", "police", "car", "gaadi", "keys")

    def merit(s: str) -> float:
        low = s.casefold()
        ws = re.findall(r"\w+", low)
        cue = sum(2 if c in ("stuck", "whole time", "silence", "impact", "lekin", "isliye") else 1 for c in cues if re.search(r"(?<!\w)" + re.escape(c) + r"(?!\w)", low))
        return cue - 0.8 * len(re.findall(r"(?<!\w)" + _CHAT + r"(?!\w)", low)) - 0.25 * (len(ws) - len(set(ws))) - max(0, len(ws) - 12) * 0.05
    toks = max(sentences, key=merit).split()
    if len(toks) > 9:
        center = next((i for i, t in enumerate(toks) if re.search(r"(?i)\b(but|instead|actually|lekin|isliye|galti|police|gaadi|keys|stuck)\b", t)), 2)
        a = max(0, min(center - 2, len(toks) - 9))
        toks = toks[a:a + 9]
    hook = " ".join(toks)
    if len(toks) <= 6 and not hook.endswith(("?", "!")):
        hook = ("Wait for it: ", "This is the part: ", "Listen to this: ")[sum(map(ord, hook)) % 3] + hook
    return hook[:80]


def hook_supported(hook: str, text: str) -> bool:
    """A hook may only name things really in the clip (at least a quarter of its words, and one or more)."""
    if len((hook or "").split()) < 4:
        return False
    stop = {"the", "a", "an", "is", "in", "of", "to", "and", "with", "this", "that", "for", "on", "it", "his", "her", "he", "she", "they", "their", "my", "me",
            "i", "you", "your", "was", "are", "how", "why", "what", "when", "reveals", "revealed", "unexpected", "surprising"}

    def stems(v: str) -> set[str]:
        out = set()
        for t in re.findall(r"\w+", v.casefold()):
            if t in stop:
                continue
            for e in ("ing", "ed", "es", "s"):
                if t.endswith(e) and len(t) > len(e) + 3:
                    t = t[:-len(e)]
                    break
            out.add(t)
        return out
    p, s = stems(hook), stems(text)
    shared = len(p & s)
    return shared >= 1 and shared / max(1, len(p)) >= 0.25


def varied(moments: list[dict], text_of, count: int) -> list[dict]:
    """Best first, but a moment that repeats one already chosen (same words, overlapping time) loses to a different one."""
    rest = sorted(moments, key=lambda m: -float(m.get("score") or 0))
    top = max((float(m.get("score") or 0) for m in rest), default=1.0) or 1.0
    toks = {id(m): set(re.findall(r"\w+", (text_of(m) or "").casefold())) for m in rest}
    chosen: list[dict] = []

    def overlap(a: dict, b: dict) -> float:
        return max(0.0, min(a["end"], b["end"]) - max(a["start"], b["start"])) / max(0.001, min(a["end"] - a["start"], b["end"] - b["start"]))
    while rest and len(chosen) < count:
        cand = [m for m in rest if not any(overlap(m, o) > 0.35 for o in chosen)]
        if not cand:
            break

        def merit(m: dict) -> float:
            w = toks[id(m)]
            sim = max((len(w & toks[id(o)]) / max(1, len(w | toks[id(o)])) for o in chosen), default=0.0)
            return float(m.get("score") or 0) / top - 0.20 * sim
        win = max(cand, key=merit)
        chosen.append(win)
        rest.remove(win)
    return sorted(chosen, key=lambda m: m["start"])


SCENE = re.compile(r"pts_time:(\d+(?:\.\d+)?)")


def hard_cuts(src: str, start: float, end: float) -> list[float]:
    origin = max(0.0, start - 0.18)
    if end <= start:
        return []
    try:
        r = subprocess.run([_ff(), "-nostdin", "-hide_banner", "-ss", f"{origin:.3f}", "-t", f"{end - origin:.3f}", "-i", str(src), "-an",
                            "-vf", "scale=160:90,select='gt(scene,0.43)',showinfo", "-f", "null", "-"], capture_output=True, text=True, timeout=8)
    except (OSError, subprocess.TimeoutExpired):
        return []
    if r.returncode:
        return []
    return [v for v in (origin + float(m.group(1)) for m in SCENE.finditer(r.stderr)) if start <= v <= end]


def on_scene_cut(src: str, m: dict, words: list[dict] | None, minimum: float) -> dict:
    """Move the start forward to a hard scene cut in the first 1.2 s and the end back to one in the last 1.2 s, never into speech."""
    a, b = float(m["start"]), float(m["end"])
    inside = [w for w in words or [] if a <= w["s"] < b]
    if not inside or b - a <= minimum:
        return m
    first, last = min(w["s"] for w in inside), max(w["e"] for w in inside)
    head_end = min(first - 0.045, a + 1.2, b - minimum)
    tail_start = max(last + 0.045, b - 1.2, a + minimum)
    lead = hard_cuts(src, a + 0.08, head_end) if head_end > a + 0.15 else []
    tail = hard_cuts(src, tail_start, b - 0.08) if tail_start < b - 0.15 else []
    n = dict(m)
    if lead:
        n["start"] = round(max(lead), 3)
    if tail:
        n["end"] = round(min((c for c in tail if c - n["start"] >= minimum), default=b), 3)
    return n
