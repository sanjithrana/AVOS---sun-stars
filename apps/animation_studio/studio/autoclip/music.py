"""The music shelf. Three kinds of track:

  built-in     six original loops this program writes itself (no samples, no copyright): chill, upbeat, epic, tense, happy, dreamy
  yours        files you upload, with a tick that you have the right to use them
  trending     not possible: popular songs belong to their owners and platforms do not give an API for their sound libraries. Use tracks you have a
               licence for (YouTube Audio Library, Pixabay Music, FreePD and similar are free) and upload them here.

Auto picks a mood from what the clip is about, then a track of that mood."""
from __future__ import annotations

import hashlib
import json
import random
import wave
from pathlib import Path

from . import store

MOODS = {"chill": "Chill", "upbeat": "Upbeat", "epic": "Epic", "tense": "Tense", "happy": "Happy", "dreamy": "Dreamy"}
BUILTIN = {f"builtin-{m}": {"id": f"builtin-{m}", "name": f"{MOODS[m]} (built-in)", "mood": m, "builtin": True} for m in MOODS}
LABEL_MOOD = [("funny|lol|laugh|joke|fail|meme", "happy"), ("win|clutch|epic|champion|insane|crazy|goat|best", "epic"), ("danger|scary|crash|fight|chase|horror|kill", "tense"),
              ("learn|tip|story|calm|relax|study|how", "chill"), ("dream|night|sad|emotional|love", "dreamy")]
SR = 32000
LOOP = 32          # seconds


def root() -> Path:
    return store.ROOT / "music"


def _synth(mood: str) -> bytes:
    """Procedural loop: a pad (detuned saws through a slow filter), a bass line, a soft kick and hat. numpy only. Deterministic per mood."""
    import numpy as np
    bpm = {"chill": 84, "upbeat": 118, "epic": 96, "tense": 100, "happy": 112, "dreamy": 70}[mood]
    scale = {"chill": [0, 3, 7, 10], "upbeat": [0, 4, 7, 11], "epic": [0, 3, 7, 12], "tense": [0, 1, 5, 8], "happy": [0, 4, 7, 9], "dreamy": [0, 2, 7, 9]}[mood]
    root_hz = {"chill": 110.0, "upbeat": 130.8, "epic": 98.0, "tense": 82.4, "happy": 146.8, "dreamy": 123.5}[mood]
    n = SR * LOOP
    t = np.arange(n) / SR
    beat = 60.0 / bpm
    out = np.zeros(n)
    rng = np.random.default_rng(int(hashlib.md5(mood.encode()).hexdigest()[:8], 16))
    prog = [0, 5, 3, 7] if mood != "tense" else [0, 1, 0, 6]
    bar = beat * 4
    for i in range(int(LOOP / bar) + 1):
        a, b = int(i * bar * SR), min(n, int((i + 1) * bar * SR))
        if a >= n:
            break
        seg = t[a:b] - t[a]
        base = root_hz * 2 ** (prog[i % 4] / 12)
        env = np.minimum(1, seg / 0.4) * np.minimum(1, (bar - seg) / 0.4)
        pad = np.zeros_like(seg)
        for k, st in enumerate(scale):
            f = base * 2 ** (st / 12) * (2 if k > 1 else 1)
            for det in (-0.004, 0.0, 0.004):
                ph = (seg * f * (1 + det)) % 1.0
                pad += (2 * ph - 1) * 0.5 + np.sin(2 * np.pi * seg * f * (1 + det)) * 0.5
        out[a:b] += pad / (len(scale) * 3) * env * 0.55
        bass = np.sin(2 * np.pi * seg * base / 2) * (0.6 + 0.4 * np.sin(2 * np.pi * seg / beat))
        out[a:b] += bass * env * 0.35
    ticks = np.arange(0, LOOP, beat)
    for k, tk in enumerate(ticks):
        a = int(tk * SR)
        m = min(n - a, int(0.18 * SR))
        if m <= 0:
            continue
        s = np.arange(m) / SR
        out[a:a + m] += np.sin(2 * np.pi * (110 * np.exp(-s * 18) + 40) * s) * np.exp(-s * 14) * (0.55 if mood not in ("dreamy",) else 0.25)       # kick
        h = int(tk * SR + beat / 2 * SR)
        mm = min(n - h, int(0.05 * SR))
        if mm > 0 and mood not in ("dreamy", "tense"):
            out[h:h + mm] += rng.standard_normal(mm) * np.exp(-np.arange(mm) / SR * 90) * 0.08                                                       # hat
    out = np.convolve(out, np.ones(24) / 24, mode="same")            # tame the top
    fade = int(0.05 * SR)
    out[:fade] *= np.linspace(0, 1, fade)
    out[-fade:] *= np.linspace(1, 0, fade)
    out = out / (np.max(np.abs(out)) or 1) * 0.8
    return (out * 32767).astype("<i2").tobytes()


def file_for(tid: str) -> str | None:
    if tid in BUILTIN:
        p = root() / "built-in" / f"{tid}.wav"
        if not p.is_file():
            p.parent.mkdir(parents=True, exist_ok=True)
            tmp = p.with_suffix(".tmp")
            with wave.open(str(tmp), "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(SR)
                wf.writeframes(_synth(BUILTIN[tid]["mood"]))
            tmp.replace(p)
        return str(p)
    rec = store._read(root() / f"{Path(tid).name}.json", None)
    f = root() / f"{Path(tid).name}{(rec or {}).get('ext', '')}"
    return str(f) if rec and f.is_file() else None


def tracks() -> list[dict]:
    mine = []
    d = root()
    for m in sorted(d.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True) if d.is_dir() else []:
        r = store._read(m, None)
        if r and (d / f"{r['id']}{r.get('ext', '')}").is_file():
            mine.append({k: r[k] for k in ("id", "name", "mood", "duration") if k in r} | {"builtin": False})
    return list(BUILTIN.values()) + mine


def add(name: str, data_path: Path, ext: str, mood: str, ack: bool) -> dict:
    """Save an uploaded track. Needs the tick that you may use it."""
    from .. import config
    import subprocess
    if not ack:
        raise ValueError("Tick that you have the right to use this track.")
    if ext.lower() not in (".mp3", ".wav", ".m4a", ".ogg", ".flac", ".aac"):
        raise ValueError("Upload an audio file (mp3, wav, m4a, ogg, flac).")
    tid = store.new_id()
    d = root()
    d.mkdir(parents=True, exist_ok=True)
    dst = d / f"{tid}{ext.lower()}"
    data_path.replace(dst)
    r = subprocess.run([config.ffmpeg(), "-hide_banner", "-i", str(dst)], capture_output=True, text=True, timeout=60)
    import re
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.?\d*)", r.stderr)
    if not m or "Audio:" not in r.stderr:
        dst.unlink(missing_ok=True)
        raise ValueError("That file doesn't look like audio.")
    dur = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    if dur < 8:
        dst.unlink(missing_ok=True)
        raise ValueError("That track is shorter than 8 seconds.")
    rec = {"id": tid, "name": " ".join(name.split())[:60] or "My track", "mood": mood if mood in MOODS else "upbeat", "ext": ext.lower(), "duration": round(dur, 1), "created": store.now()}
    store._write(d / f"{tid}.json", rec)
    return rec | {"builtin": False}


def remove(tid: str) -> bool:
    tid = Path(tid).name
    d = root()
    r = store._read(d / f"{tid}.json", None)
    if not r:
        return False
    for p in (d / f"{tid}{r.get('ext', '')}", d / f"{tid}.json"):
        p.unlink(missing_ok=True)
    return True


def mood_for(label: str) -> str:
    import re
    for rx, m in LABEL_MOOD:
        if re.search(rx, (label or "").lower()):
            return m
    return "upbeat"


def pick(choice: str, label: str = "", seed: int = 0) -> dict | None:
    """choice: a track id, a mood name, or "auto"."""
    allt = {t["id"]: t for t in tracks()}
    if choice in allt:
        return allt[choice]
    mood = choice if choice in MOODS else mood_for(label)
    pool = [t for t in allt.values() if t["mood"] == mood]
    users = [t for t in pool if not t.get("builtin")]
    pool = users or pool
    return random.Random(seed).choice(pool) if pool else None


def offset_for(tr: dict, dur: float, seed: int = 0) -> float:
    """Where in the track to start: a different place per clip, so two clips from one video don't have the same intro."""
    total = float(tr.get("duration") or LOOP)
    room = max(0.0, total - dur - 1.0)
    return round(random.Random(seed + 7).uniform(0, room), 1) if room > 1 else 0.0


# ---------- sound effects: written here, nothing to download or license ----------
def sfx_file(kind: str) -> str:
    """kind: pop (a callout appears), hit (a hype peak). A short mono WAV, written once."""
    p = root() / "built-in" / f"sfx-{kind}.wav"
    if p.is_file():
        return str(p)
    import numpy as np
    p.parent.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(7)
    if kind == "hit":
        n = int(0.6 * SR)
        t = np.arange(n) / SR
        y = np.sin(2 * np.pi * (48 + 90 * np.exp(-t * 14)) * t) * np.exp(-t * 6.5) + rng.standard_normal(n) * np.exp(-t * 28) * 0.35
        y = np.convolve(y, np.ones(6) / 6, mode="same")
    else:                                                      # pop: a quick rising "bloop" with a puff of air
        n = int(0.22 * SR)
        t = np.arange(n) / SR
        y = np.sin(2 * np.pi * (380 + 900 * t / 0.22) * t) * np.exp(-t * 18) + rng.standard_normal(n) * np.exp(-t * 60) * 0.12
    y = y / (np.max(np.abs(y)) or 1) * 0.85
    tmp = p.with_suffix(".tmp")
    with wave.open(str(tmp), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes((y * 32767).astype("<i2").tobytes())
    tmp.replace(p)
    return str(p)
