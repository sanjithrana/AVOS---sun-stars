from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import io
import logging
import os
import re
import struct
import wave

from packages.contracts.audio import WordTimestamp

logger = logging.getLogger(__name__)


@dataclass
class SynthesizedAudio:
    audio_bytes: bytes
    format: str
    duration_seconds: float
    sample_rate: int
    # Real per-word timings when the provider reports them (Edge TTS
    # does). When present the audio pipeline uses these instead of the
    # (mock) Whisper pass, so captions and shot cuts land on the words
    # actually spoken.
    words: list[WordTimestamp] = field(default_factory=list)


class TTSProvider(ABC):
    name: str = "unknown"

    @abstractmethod
    async def synthesize(self, text: str) -> SynthesizedAudio:
        raise NotImplementedError


class MockTTSProvider(TTSProvider):
    """
    Deterministic offline TTS.

    Produces a real, valid (silent) WAV file whose duration is derived
    from word count at a fixed speaking rate (~150 wpm), so downstream
    code (whisper mock, timestamps, asset storage) has real bytes and a
    real, consistent duration to work with — no network call needed.
    Used by the test suite and when TTS_PROVIDER=mock.
    """

    name = "mock"
    WORDS_PER_MINUTE = 150
    SAMPLE_RATE = 16_000

    async def synthesize(self, text: str) -> SynthesizedAudio:
        word_count = max(1, len(text.split()))
        duration_seconds = round((word_count / self.WORDS_PER_MINUTE) * 60, 2)

        num_frames = int(duration_seconds * self.SAMPLE_RATE)
        buffer = io.BytesIO()

        with wave.open(buffer, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(self.SAMPLE_RATE)
            wav_file.writeframes(struct.pack("<%dh" % num_frames, *([0] * num_frames)))

        return SynthesizedAudio(
            audio_bytes=buffer.getvalue(),
            format="wav",
            duration_seconds=duration_seconds,
            sample_rate=self.SAMPLE_RATE,
        )


# -- Edge TTS (free) -------------------------------------------------------

_TICKS_PER_SECOND = 10_000_000  # Edge reports offsets in 100 ns ticks


def _norm(token: str) -> str:
    return re.sub(r"[^\w]", "", token.lower())


def align_words(
    text: str,
    boundaries: list[tuple[str, float, float]],
    duration_seconds: float,
) -> list[WordTimestamp]:
    """
    Map the provider's word boundaries (which drop punctuation, e.g.
    "world" for "world.") back onto the narration's own tokens, so the
    sentence splitter downstream still sees the "." / "!" / "?" it splits
    on. Tokens the provider skipped or split differently get timings
    interpolated from their neighbours; if most tokens can't be matched
    at all, timings fall back to an even spread over the real duration.
    """
    tokens = text.split()
    if not tokens:
        return []

    timings: list[tuple[float, float] | None] = []
    bi = 0
    for token in tokens:
        target = _norm(token)
        if not target:
            timings.append(None)
            continue
        matched: tuple[float, float] | None = None
        # Allow skipping a stray boundary or two (e.g. a spoken symbol).
        for skip in range(0, 3):
            j = bi + skip
            acc, start, end = "", None, None
            while j < len(boundaries) and len(acc) < len(target):
                piece = _norm(boundaries[j][0])
                if not piece or not target[len(acc):].startswith(piece):
                    break
                acc += piece
                start = boundaries[j][1] if start is None else start
                end = boundaries[j][2]
                j += 1
            if acc == target and start is not None and end is not None:
                matched = (start, end)
                bi = j
                break
        timings.append(matched)

    matched_count = sum(1 for t in timings if t is not None)
    if matched_count < max(1, len(tokens) // 2):
        per = duration_seconds / len(tokens)
        return [
            WordTimestamp(word=tok, start=round(i * per, 3), end=round((i + 1) * per, 3))
            for i, tok in enumerate(tokens)
        ]

    # Interpolate gaps between known neighbours.
    filled: list[tuple[float, float]] = []
    for i, t in enumerate(timings):
        if t is not None:
            filled.append(t)
            continue
        prev_end = filled[-1][1] if filled else 0.0
        nxt = next((timings[k] for k in range(i + 1, len(timings)) if timings[k] is not None), None)
        next_start = nxt[0] if nxt else duration_seconds
        filled.append((prev_end, max(prev_end, next_start)))

    return [
        WordTimestamp(word=tok, start=round(max(0.0, s), 3), end=round(max(s, e), 3))
        for tok, (s, e) in zip(tokens, filled)
    ]


class EdgeTTSProvider(TTSProvider):
    """
    Microsoft Edge's online neural voices via the ``edge-tts`` package:
    free, no API key, natural-sounding, and it reports real per-word
    timings (used for captions and shot cuts). Needs internet access
    from the worker container.

    Voice/rate are set with TTS_VOICE (e.g. en-US-ChristopherNeural,
    en-US-AndrewNeural, en-GB-RyanNeural, en-IN-PrabhatNeural) and
    TTS_RATE (e.g. "+10%"). `edge-tts --list-voices` lists them all.
    """

    name = "edge"
    SAMPLE_RATE = 24_000  # Edge's default MP3 output: 24 kHz mono

    def __init__(self, voice: str = "en-US-ChristopherNeural", rate: str = "+0%") -> None:
        self.voice = voice
        self.rate = rate

    async def synthesize(self, text: str) -> SynthesizedAudio:
        try:
            import edge_tts
        except ImportError as exc:  # pragma: no cover - image always has it
            raise RuntimeError(
                "TTS_PROVIDER=edge but the edge-tts package is not installed. "
                "Rebuild the api/worker image (it's in api/requirements.txt)."
            ) from exc

        communicate = edge_tts.Communicate(text, self.voice, rate=self.rate, boundary="WordBoundary")
        audio = bytearray()
        boundaries: list[tuple[str, float, float]] = []
        try:
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio.extend(chunk["data"])
                elif chunk["type"] == "WordBoundary":
                    start = chunk["offset"] / _TICKS_PER_SECOND
                    end = (chunk["offset"] + chunk["duration"]) / _TICKS_PER_SECOND
                    boundaries.append((chunk["text"], start, end))
        except Exception as exc:
            raise RuntimeError(
                f"Edge TTS failed for voice '{self.voice}': {exc}. The worker needs internet "
                "access to speech.platform.bing.com; set TTS_PROVIDER=mock to run offline."
            ) from exc

        if not audio:
            raise RuntimeError(f"Edge TTS returned no audio for voice '{self.voice}'.")

        audio_bytes = bytes(audio)
        duration = await _audio_duration(audio_bytes, boundaries)
        words = align_words(text, boundaries, duration)

        return SynthesizedAudio(
            audio_bytes=audio_bytes,
            format="mp3",
            duration_seconds=round(duration, 2),
            sample_rate=self.SAMPLE_RATE,
            words=words,
        )


async def _audio_duration(audio_bytes: bytes, boundaries: list[tuple[str, float, float]]) -> float:
    """Exact duration via ffprobe; the last spoken word's end (+ a short
    tail) if ffprobe isn't available."""
    try:
        from agentic_core.media.ffmpeg import probe_duration_bytes

        return await probe_duration_bytes(audio_bytes, "mp3")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not probe TTS duration with ffprobe (%s); estimating.", exc)
        return (boundaries[-1][2] + 0.4) if boundaries else 1.0


def get_tts_provider() -> TTSProvider:
    """TTS_PROVIDER=edge -> free Edge neural voices (docker-compose sets
    this). Unset / "mock" -> the silent offline mock (tests, no network)."""
    choice = (os.getenv("TTS_PROVIDER") or "mock").strip().lower()
    if choice in ("", "mock"):
        return MockTTSProvider()
    if choice == "edge":
        return EdgeTTSProvider(
            voice=os.getenv("TTS_VOICE") or "en-US-ChristopherNeural",
            rate=os.getenv("TTS_RATE") or "+0%",
        )
    raise ValueError(f"Unknown TTS_PROVIDER '{choice}'. Known providers: ('mock', 'edge').")
