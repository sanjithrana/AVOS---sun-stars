import pytest

from agentic_core.pipelines.audio.semantic_beats import extract_semantic_beats
from agentic_core.pipelines.audio.timestamps import extract_sentence_timestamps
from agentic_core.pipelines.audio.tts import MockTTSProvider
from agentic_core.pipelines.audio.whisper import MockWhisperProvider

SAMPLE_TEXT = "Sunflowers turn to face the sun. This is called heliotropism. It happens during growth."


@pytest.mark.asyncio
async def test_tts_produces_playable_audio_with_positive_duration():
    tts = MockTTSProvider()
    result = await tts.synthesize(SAMPLE_TEXT)

    assert result.format == "wav"
    assert result.duration_seconds > 0
    assert len(result.audio_bytes) > 44  # bigger than just a WAV header
    assert result.audio_bytes[:4] == b"RIFF"


@pytest.mark.asyncio
async def test_whisper_produces_word_timestamps_matching_source_text():
    tts = MockTTSProvider()
    audio = await tts.synthesize(SAMPLE_TEXT)

    whisper = MockWhisperProvider()
    transcript = await whisper.transcribe(
        audio.audio_bytes,
        duration_seconds=audio.duration_seconds,
        known_text=SAMPLE_TEXT,
    )

    assert len(transcript.words) == len(SAMPLE_TEXT.split())
    assert transcript.words[0].start == 0
    assert transcript.words[-1].end <= audio.duration_seconds + 0.01


@pytest.mark.asyncio
async def test_full_audio_pipeline_produces_sentence_beats():
    tts = MockTTSProvider()
    audio = await tts.synthesize(SAMPLE_TEXT)

    whisper = MockWhisperProvider()
    transcript = await whisper.transcribe(
        audio.audio_bytes,
        duration_seconds=audio.duration_seconds,
        known_text=SAMPLE_TEXT,
    )

    sentences = extract_sentence_timestamps(transcript.words)
    beats = extract_semantic_beats(sentences)

    assert len(sentences) == 3  # three sentence-ending periods in SAMPLE_TEXT
    assert len(beats) == len(sentences)
    # Beats should be in non-decreasing time order.
    assert all(beats[i].time <= beats[i + 1].time for i in range(len(beats) - 1))


def test_sentence_timestamps_empty_input_returns_empty():
    assert extract_sentence_timestamps([]) == []
