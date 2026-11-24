"""Words with times: an SRT you give it, or faster-whisper when it is installed (pip install faster-whisper). No transcript is fine:
clips are then picked by loudness and cut without captions, and the page says so."""
from __future__ import annotations

import re
from typing import Any

TS = re.compile(r"(\d+):(\d\d):(\d\d)[,.](\d{1,3})\s*-->\s*(\d+):(\d\d):(\d\d)[,.](\d{1,3})")


def _sec(h: str, m: str, s: str, ms: str) -> float:
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms.ljust(3, "0")) / 1000


def parse_srt(text: str) -> list[dict]:
    cues: list[dict] = []
    for block in re.split(r"\n\s*\n", text.replace("\r\n", "\n").strip()):
        lines = [ln for ln in block.split("\n") if ln.strip()]
        for i, ln in enumerate(lines):
            m = TS.search(ln)
            if m:
                body = re.sub(r"<[^>]+>", "", " ".join(lines[i + 1:])).strip()
                if body:
                    cues.append({"start": _sec(*m.groups()[:4]), "end": _sec(*m.groups()[4:]), "text": body})
                break
    return cues


JUNK = re.compile(r"^[>\[\]()_\-–—♪♫*#~|]+$")


def clean_words(words: list[dict]) -> list[dict]:
    """Drop what YouTube's own captions put in that nobody said: '>>' speaker marks, '[ __ ]' bleeps, [Music] / [Applause] tags, note signs.
    A '[' starts a skipped run that ends at the next ']' (or after 4 words)."""
    out: list[dict] = []
    skip = 0
    for w in words:
        t = str(w.get("w") or "").strip()
        if skip:
            skip -= 1
            if "]" in t:
                skip = 0
            continue
        if t.startswith("[") or t.startswith("("):
            if not (t.endswith("]") or t.endswith(")")):
                skip = 4
            continue
        t = t.lstrip(">").strip()
        if not t or JUNK.match(t):
            continue
        out.append({**w, "w": t})
    return out


def words_of(cues: list[dict]) -> list[dict]:
    """Per-word times. Whisper gives them; an SRT only has a cue, so each cue's time is shared by its words in proportion to their length."""
    out: list[dict] = []
    for c in cues:
        if c.get("words"):
            out += clean_words(c["words"])
            continue
        ws = c["text"].split()
        if not ws:
            continue
        total = sum(len(w) + 1 for w in ws)
        t = c["start"]
        for w in ws:
            d = (c["end"] - c["start"]) * (len(w) + 1) / total
            out.append({"w": w, "s": round(t, 3), "e": round(t + d, 3)})
            t += d
    return clean_words(out) if any(x["w"].startswith((">", "[", "(")) or JUNK.match(x["w"]) for x in out) else out


def available() -> bool:
    """True when faster-whisper is installed (the clip captions can then be written from the clip's own audio)."""
    import importlib.util
    return importlib.util.find_spec("faster_whisper") is not None


_MODELS: dict[str, Any] = {}


def _model(name: str) -> Any:
    """One loaded model per size, kept for the next clip (loading takes longer than transcribing a 40-second clip)."""
    from faster_whisper import WhisperModel  # type: ignore
    if name not in _MODELS:
        _MODELS.clear()                                   # only one in memory at a time
        _MODELS[name] = WhisperModel(name, device="cpu", compute_type="int8")
    return _MODELS[name]


def whisper(path: str, log: Any = None, model: str = "base", prompt: str | None = None, task: str = "transcribe") -> list[dict] | None:
    """Cues with word times from faster-whisper, or None when it isn't installed or fails (the run goes on without captions)."""
    try:
        from faster_whisper import WhisperModel  # type: ignore
    except Exception:  # noqa: BLE001
        return None
    try:
        m = _model(model)
        segs, _ = m.transcribe(path, word_timestamps=True, vad_filter=True, beam_size=1, initial_prompt=(prompt or None), task=("translate" if task == "translate" else "transcribe"))
        cues = []
        for s in segs:
            cues.append({"start": float(s.start), "end": float(s.end), "text": s.text.strip(),
                         "words": [{"w": w.word.strip(), "s": float(w.start), "e": float(w.end)} for w in (s.words or []) if w.word.strip()]})
        return cues
    except Exception as e:  # noqa: BLE001
        if log:
            log(f"Transcribing failed ({str(e)[:120]}); picking by loudness and cutting without captions.")
        return None


def whisper_window(path: str, t0: float, t1: float, log: Any = None, model: str = "small", prompt: str | None = None, task: str = "transcribe") -> list[dict] | None:
    """Cues (with word times on the SOURCE's clock) for just [t0, t1] of a long video: a few seconds of audio, so it takes about a minute, not hours."""
    import subprocess
    import tempfile
    from pathlib import Path
    from .. import config
    tmp = Path(tempfile.mkdtemp()) / "w.wav"
    try:
        r = subprocess.run([config.ffmpeg(), "-v", "error", "-y", "-nostdin", "-ss", f"{max(0.0, t0):.2f}", "-t", f"{max(1.0, t1 - t0):.2f}", "-i", path, "-vn", "-ac", "1", "-ar", "16000", str(tmp)],
                           capture_output=True, text=True, timeout=1800)
        if r.returncode != 0 or not tmp.is_file():
            return None
        cues = whisper(str(tmp), log, model, prompt, task)
    finally:
        tmp.unlink(missing_ok=True)
        try:
            tmp.parent.rmdir()
        except OSError:
            pass
    if not cues:
        return None
    for c in cues:
        c["start"], c["end"] = c["start"] + t0, c["end"] + t0
        for w in c.get("words") or []:
            w["s"], w["e"] = w["s"] + t0, w["e"] + t0
    return cues


def text_between(cues: list[dict], a: float, b: float) -> str:
    return " ".join(c["text"] for c in cues if c["end"] > a and c["start"] < b).strip()
