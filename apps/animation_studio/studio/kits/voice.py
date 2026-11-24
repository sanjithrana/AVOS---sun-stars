"""Narration for the kits: edge-tts → mp3 plus exact word timings (words.json), aligned to the script with the kit's own aligner."""
from __future__ import annotations

import asyncio
import importlib.util
import json
from pathlib import Path

VOICES = {"male": "en-US-GuyNeural", "female": "en-US-JennyNeural"}


def _kit_voice(kit_dir: Path):
    spec = importlib.util.spec_from_file_location("kit_voice_" + kit_dir.name, kit_dir / "scripts" / "voice.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)  # the kit's voice.py is stdlib-only and guards its CLI behind __main__
    return m


def _plain(script: str) -> str:
    return " ".join(script.replace("*", "").replace("…", "... ").split())


async def _speak(text: str, voice: str, mp3: Path) -> list[tuple[str, float, float]]:
    import edge_tts
    words: list[tuple[str, float, float]] = []
    comm = edge_tts.Communicate(text, voice, rate="+0%")
    with mp3.open("wb") as f:
        async for ch in comm.stream():
            if ch["type"] == "audio":
                f.write(ch["data"])
            elif ch["type"] == "WordBoundary":
                s = ch["offset"] / 1e7
                words.append((ch["text"], s, s + ch["duration"] / 1e7))
    return words


def narrate(script: str, who: str, out_dir: Path, kit_dir: Path | None = None) -> dict:
    """Write voice.mp3 and words.json into out_dir. Returns {file, words, seconds}."""
    out_dir.mkdir(parents=True, exist_ok=True)
    mp3 = out_dir / "voice.mp3"
    spoken = asyncio.run(_speak(_plain(script), VOICES.get(who, VOICES["male"]), mp3))
    if not spoken or not mp3.is_file() or mp3.stat().st_size < 800:
        raise RuntimeError("Edge TTS returned no audio (it needs an internet connection).")
    words = None
    if kit_dir is not None:
        try:
            words = _kit_voice(kit_dir).align(script, spoken)
        except Exception:  # noqa: BLE001 - the player can line the script up with the pauses by itself
            words = None
    if words is None:
        words = [{"text": t, "start": round(a, 3), "end": round(b, 3)} for t, a, b in spoken]
    (out_dir / "words.json").write_text(json.dumps(words), "utf-8")
    return {"file": "voice.mp3", "words": len(words), "seconds": round(max(w["end"] for w in words), 2)}
