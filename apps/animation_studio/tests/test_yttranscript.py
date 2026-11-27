"""YouTube's own transcript through youtube-transcript-api (no network: a fake list)."""
from __future__ import annotations

from types import SimpleNamespace as NS

import pytest

from studio.autoclip import yttranscript


def T(code, gen, lang="x"):
    return NS(language_code=code, is_generated=gen, language=lang)


def test_video_ids():
    for u in ("https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=3", "https://youtu.be/dQw4w9WgXcQ", "https://youtube.com/shorts/dQw4w9WgXcQ",
              "https://www.youtube.com/live/dQw4w9WgXcQ?si=x", "dQw4w9WgXcQ"):
        assert yttranscript.video_id(u) == "dQw4w9WgXcQ", u
    assert yttranscript.video_id("https://twitch.tv/x") is None


def test_written_beats_automatic_and_my_languages_first():
    assert yttranscript.pick([T("de", False), T("en", True), T("hi", False)]).language_code == "hi"
    assert yttranscript.pick([T("de", False), T("en", True)]).language_code == "de"
    assert yttranscript.pick([T("ta", True), T("en", True)]).language_code == "en"
    assert yttranscript.pick([T("ta", True)]).language_code == "ta"           # the spoken language's auto captions
    assert yttranscript.pick([]) is None


def test_lines_become_cues_with_word_times():
    cues = yttranscript.to_cues([{"text": "[Music]", "start": 0, "duration": 2},
                                 {"text": "no way bro\nthat was insane", "start": 2.0, "duration": 4.0},
                                 {"text": "okay", "start": 5.0, "duration": 1.0}])
    assert [c["text"] for c in cues] == ["no way bro that was insane", "okay"]
    c = cues[0]
    assert c["end"] == 5.0                                    # stops where the next line starts (auto-captions overlap)
    ws = c["words"]
    assert len(ws) == 6 and ws[0]["s"] == 2.0 and all(a["s"] < b["s"] for a, b in zip(ws, ws[1:])) and ws[-1]["e"] <= 5.0


def test_fetch_never_raises(monkeypatch):
    assert yttranscript.fetch("https://twitch.tv/x")[0] is None
    class Boom:
        def __init__(self, **k): pass
        def list(self, vid): raise RuntimeError("blocked")
    youtube_transcript_api = pytest.importorskip("youtube_transcript_api")
    monkeypatch.setattr(youtube_transcript_api, "YouTubeTranscriptApi", Boom)
    cues, why = yttranscript.fetch("https://youtu.be/dQw4w9WgXcQ")
    assert cues is None and "blocked" in why
