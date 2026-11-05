"""Lyric timing: ReelMimic's align_lyrics.py (faster-whisper as a ruler) when it is installed, otherwise lines are
spread over the music section on the beat grid (marked match 0 → 'interpolated' in the UI, check by ear)."""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from . import config


def _dur(audio: Path) -> float:
    try:
        r = subprocess.run([config.ffprobe(), "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(audio)],
                           capture_output=True, text=True, timeout=30)
        return float(r.stdout.strip())
    except Exception:
        return 30.0


def _fmt(t: float) -> str:
    return f"{int(t // 60):02d}:{t % 60:05.2f}"


def align(audio: Path, lyrics: Path, out_lrc: Path, start: float | None, end: float | None) -> tuple[bool, str]:
    text = lyrics.read_text("utf-8")
    lang = "zh" if re.search(r"[一-鿿]", text) else "en"
    cmd = [config.PY, str(config.SCRIPTS / "align_lyrics.py"), str(audio), str(lyrics), "--out", str(out_lrc), "--lang", lang,
           "--model", __import__("os").environ.get("WHISPER_MODEL", "small")]
    if start is not None:
        cmd += ["--start", str(start)]
        if end is not None:
            cmd += ["--end", str(end)]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(config.WORK_DIR), timeout=1800)
        if r.returncode == 0 and out_lrc.with_suffix(".json").exists():
            first = next((ln for ln in r.stdout.splitlines() if ln.startswith("lines")), "aligned")
            return True, first
        err = (r.stderr or r.stdout)[-300:]
    except Exception as e:
        err = str(e)
    # fallback: even spacing over the section
    lines = [ln.strip() for ln in text.splitlines() if ln.strip() and not ln.strip().startswith("[")]
    if not lines:
        return False, "no lyric lines"
    total = (end - start) if (start is not None and end is not None) else _dur(audio) - (start or 0)
    total = max(3.0, total)
    lead = min(1.5, total * 0.05)
    each = (total - lead) / len(lines)
    out = []
    for i, ln in enumerate(lines):
        s = lead + i * each
        out.append({"text": ln, "start": round(s, 2), "end": round(s + each * 0.95, 2), "match": 0.0, "interpolated": True})
    out_lrc.parent.mkdir(parents=True, exist_ok=True)
    out_lrc.write_text("\n".join(f"[{_fmt(o['start'])}]{o['text']}" for o in out) + "\n", "utf-8")
    out_lrc.with_suffix(".json").write_text(json.dumps({"lines": out, "method": "even"}, ensure_ascii=False, indent=1), "utf-8")
    why = "faster-whisper not installed" if "faster_whisper" in err or "No module" in err else err.strip().splitlines()[-1] if err.strip() else "aligner failed"
    return True, f"lines {len(out)}, spread evenly over {total:.1f}s ({why}; pip install faster-whisper for timing by ear)"
