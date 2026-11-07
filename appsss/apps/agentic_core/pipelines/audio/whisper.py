from abc import ABC, abstractmethod

from packages.contracts.audio import TranscriptionResult, WordTimestamp


class WhisperProvider(ABC):
    name: str = "unknown"

    @abstractmethod
    async def transcribe(
        self,
        audio_bytes: bytes,
        *,
        duration_seconds: float,
        known_text: str | None = None,
    ) -> TranscriptionResult:
        raise NotImplementedError


class MockWhisperProvider(WhisperProvider):
    """
    Deterministic offline transcription.

    A real Whisper call transcribes the actual audio and ignores any
    "known_text" hint. Because our mock TTS produces silent audio (see
    tts.py), we instead evenly distribute the known source text's words
    across the reported duration. This keeps the whole audio pipeline
    (TTS -> Whisper -> timestamps -> semantic beats) runnable end-to-end
    with real, internally-consistent data and no external service.
    """

    name = "mock"

    async def transcribe(
        self,
        audio_bytes: bytes,
        *,
        duration_seconds: float,
        known_text: str | None = None,
    ) -> TranscriptionResult:
        words = (known_text or "").split()

        if not words:
            return TranscriptionResult(words=[], duration_seconds=duration_seconds)

        per_word = duration_seconds / len(words)
        timestamps = [
            WordTimestamp(
                word=word,
                start=round(i * per_word, 3),
                end=round((i + 1) * per_word, 3),
            )
            for i, word in enumerate(words)
        ]

        return TranscriptionResult(
            words=timestamps,
            duration_seconds=duration_seconds,
        )


def get_whisper_provider() -> WhisperProvider:
    return MockWhisperProvider()
