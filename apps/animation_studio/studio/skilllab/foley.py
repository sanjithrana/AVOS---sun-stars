"""ASMR kitchen foley, synthesised here in code.

A cooking video lives on its sound, and the free path has no sound at all: a video model with native audio costs credit, and there is
no sound library in the box. So each shot's sound is built from noise and envelopes instead - a sizzle is band-passed noise with a
slow flutter and random pops, a chop is a hard transient with a wooden ring, a pour is filtered noise swelling and falling. It is
not a recording of a real kitchen, but it lands on the action and it is free.

`wav(cue, seconds)` picks the sound from the shot's own ASMR line ("loud oil sizzle tsssss" -> sizzle) and returns WAV bytes.
"""
from __future__ import annotations

import io
import re
import wave

import numpy as np

SR = 48000
RNG = np.random.default_rng


def _noise(n: int, seed: int) -> np.ndarray:
    return RNG(seed).normal(0, 1, n).astype(np.float32)


def _lowpass(x: np.ndarray, cut: float) -> np.ndarray:
    """One-pole low pass: enough colour for foley, and fast."""
    a = float(np.exp(-2 * np.pi * cut / SR))
    out = np.empty_like(x)
    acc = 0.0
    for i in range(x.size):                       # vectorising this costs more memory than it saves at these lengths
        acc = a * acc + (1 - a) * float(x[i])
        out[i] = acc
    return out


def _band(x: np.ndarray, lo: float, hi: float) -> np.ndarray:
    return _lowpass(x, hi) - _lowpass(x, lo)


def _env(n: int, attack: float, decay: float) -> np.ndarray:
    a = max(1, int(attack * SR))
    e = np.ones(n, dtype=np.float32)
    e[:a] = np.linspace(0, 1, a, dtype=np.float32)
    t = np.arange(n, dtype=np.float32) / SR
    return e * np.exp(-t / max(1e-3, decay)).astype(np.float32)


def _hits(secs: float, times: list[float], make) -> np.ndarray:
    out = np.zeros(int(secs * SR) + SR, dtype=np.float32)
    for i, t in enumerate(times):
        h = make(i)
        a = int(t * SR)
        out[a:a + h.size] += h[: max(0, out.size - a)]
    return out[: int(secs * SR)]


# ---------------------------------------------------------------- the cues
def sizzle(secs: float, seed: int = 1) -> np.ndarray:
    """Oil in a hot pan: bright band-passed hiss that swells, with scattered pops."""
    n = int(secs * SR)
    base = _band(_noise(n, seed), 900, 7000) * 0.55
    t = np.arange(n, dtype=np.float32) / SR
    swell = np.clip(t / max(0.25, secs * 0.18), 0, 1) * (1 - 0.25 * np.clip((t - secs * 0.8) / (secs * 0.2), 0, 1))
    flutter = 1 + 0.18 * np.sin(2 * np.pi * 3.1 * t) + 0.12 * np.sin(2 * np.pi * 7.7 * t + 1.1)
    r = RNG(seed + 5)
    pops = _hits(secs, sorted(r.uniform(0.05, secs, int(secs * 7))),
                 lambda i: _band(_noise(int(0.05 * SR), seed + 20 + i), 1500, 9000) * _env(int(0.05 * SR), 0.0005, 0.012) * 1.4)
    return base * swell * flutter + pops


def crunch(secs: float, seed: int = 2) -> np.ndarray:
    """A dry bite or a crisp break: a handful of short, bright bursts."""
    r = RNG(seed)
    times = sorted(r.uniform(0.05, max(0.2, secs - 0.3), max(2, int(secs * 1.6))))
    def one(i: int) -> np.ndarray:
        m = int(0.16 * SR)
        return _band(_noise(m, seed + i), 700, 8000) * _env(m, 0.001, 0.045) * 1.5
    return _hits(secs, times, one)


def chop(secs: float, seed: int = 3) -> np.ndarray:
    """Knife through a vegetable onto a board: a wet split, then the wooden knock under it."""
    times = [0.25 + i * max(0.42, secs / max(2, int(secs / 0.55))) for i in range(max(2, int(secs / 0.55)))]
    times = [t for t in times if t < secs - 0.2]
    def one(i: int) -> np.ndarray:
        m = int(0.22 * SR)
        split = _band(_noise(m, seed + i), 400, 6500) * _env(m, 0.0004, 0.03)
        t = np.arange(m, dtype=np.float32) / SR
        knock = np.sin(2 * np.pi * 180 * t).astype(np.float32) * _env(m, 0.0003, 0.05) * 0.5
        return (split + knock) * 1.4
    return _hits(secs, times, one)


def pour(secs: float, seed: int = 4) -> np.ndarray:
    """A liquid poured: filtered noise swelling and falling, with a few bubbles."""
    n = int(secs * SR)
    t = np.arange(n, dtype=np.float32) / SR
    body = _band(_noise(n, seed), 250, 3500) * 0.6
    shape = np.clip(t / (secs * 0.25), 0, 1) * np.clip((secs - t) / (secs * 0.3), 0, 1)
    r = RNG(seed + 3)
    drops = _hits(secs, sorted(r.uniform(0.1, secs, max(2, int(secs * 2)))),
                  lambda i: (np.sin(2 * np.pi * np.linspace(600, 220, int(0.08 * SR), dtype=np.float32) *
                                    np.arange(int(0.08 * SR), dtype=np.float32) / SR).astype(np.float32)
                             * _env(int(0.08 * SR), 0.001, 0.03) * 0.5))
    return body * shape + drops


def boil(secs: float, seed: int = 5) -> np.ndarray:
    """A low rolling simmer: warm rumble with bubbles breaking."""
    n = int(secs * SR)
    rumble = _lowpass(_noise(n, seed), 300) * 1.2
    r = RNG(seed + 7)
    bubbles = _hits(secs, sorted(r.uniform(0.05, secs, int(secs * 5))),
                    lambda i: (np.sin(2 * np.pi * np.linspace(float(RNG(seed + i).uniform(180, 420)), 90, int(0.09 * SR), dtype=np.float32)
                                      * np.arange(int(0.09 * SR), dtype=np.float32) / SR).astype(np.float32)
                               * _env(int(0.09 * SR), 0.001, 0.035) * 0.6))
    return rumble + bubbles


def stir(secs: float, seed: int = 6) -> np.ndarray:
    """A spoon through a thick mix: soft scrapes that come and go."""
    n = int(secs * SR)
    t = np.arange(n, dtype=np.float32) / SR
    body = _band(_noise(n, seed), 200, 2600) * 0.5
    return body * (0.45 + 0.55 * np.abs(np.sin(2 * np.pi * 1.1 * t)).astype(np.float32))


def knock(secs: float, seed: int = 7) -> np.ndarray:
    """Something set down on the board: one or two dull thuds."""
    times = [0.18, 0.62] if secs > 1.2 else [0.15]
    def one(i: int) -> np.ndarray:
        m = int(0.3 * SR)
        t = np.arange(m, dtype=np.float32) / SR
        return ((np.sin(2 * np.pi * 120 * t) + 0.5 * np.sin(2 * np.pi * 70 * t)).astype(np.float32) * _env(m, 0.0008, 0.07)
                + _lowpass(_noise(m, seed + i), 900) * _env(m, 0.0005, 0.02)) * 0.9
    return _hits(secs, [t for t in times if t < secs], one)


CUES = {"sizzle": sizzle, "crunch": crunch, "chop": chop, "pour": pour, "boil": boil, "stir": stir, "knock": knock}
WORDS = (
    ("sizzle", r"sizzl|fry|frying|tsss|sear|oil|splatter|pan[- ]?hot|grill"),
    ("boil", r"boil|simmer|bubbl|steam|stew"),
    ("pour", r"pour|drizzl|splash|liquid|water|milk|sauce|batter|glug"),
    ("chop", r"chop|slice|slicing|dice|dicing|cut|knife|mince|julienne"),
    ("crunch", r"crunch|crack|snap|bite|shatter|grate|grating|peel|brittle"),
    ("stir", r"stir|mix|mixing|fold|whisk|knead|toss|coat|rub|spread"),
    ("knock", r"knock|tap|thud|place|set down|plate|clink|drop"),
)


def cue_for(text: str) -> str:
    """Which sound a shot's ASMR line asks for. An ASMR line names its sounds in the order they happen ("a dry brittle crack then a
    soft splash"), so the one that comes FIRST in the line wins, not whichever rule happens to be listed first here."""
    t = (text or "").lower()
    best, at = "", len(t) + 1
    for name, rx in WORDS:
        m = re.search(rx, t)
        if m and m.start() < at:
            best, at = name, m.start()
    return best or "stir"


def _wav_bytes(x: np.ndarray) -> bytes:
    peak = float(np.abs(x).max()) or 1.0
    x = (x / peak) * 0.82
    m = min(2048, x.size)
    if m:                                          # no clicks at the joins
        x[:m] *= np.linspace(0, 1, m, dtype=np.float32)
        x[-m:] *= np.linspace(1, 0, m, dtype=np.float32)
    pcm = (np.clip(x, -1, 1) * 32767).astype("<i2")
    b = io.BytesIO()
    with wave.open(b, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    return b.getvalue()


def wav(cue_text: str, seconds: float, seed: int = 0) -> bytes:
    """The shot's ASMR sound as WAV bytes, chosen from its own ASMR line."""
    secs = max(0.4, min(30.0, float(seconds)))
    name = cue_for(cue_text)
    room = _lowpass(_noise(int(secs * SR), seed + 99), 220) * 0.06      # a little kitchen air under everything
    return _wav_bytes(CUES[name](secs, seed + 1) * 0.9 + room)
