"""The packaging team, with the searches faked (no network)."""
from __future__ import annotations

import pytest

from studio.autoclip import meta, pipeline, research, store

ROWS = [
    {"id": "a1", "title": "Speed DESTROYS the cops in GTA 6 💀 #ishowspeed #gta6", "description": "@IShowSpeed went crazy #ishowspeed #gta6 #speed #fyp", "tags": [], "channel": "Clips", "views": 26_000_000, "track": "Raya (Slowed)", "artist": "Zericxxn"},
    {"id": "a2", "title": "IShowSpeed plays GTA 6 for the first time", "description": "#ishowspeed #gta6 #gaming #viral", "tags": ["ishowspeed", "gta 6"], "channel": "X", "views": 11_000_000, "track": "Raya (Slowed)", "artist": "Zericxxn"},
    {"id": "a3", "title": "Speed rage quits 😭", "description": "#ishowspeed #rage #speed", "tags": [], "channel": "Y", "views": 9_000_000, "track": "Other song", "artist": "Z"},
    {"id": "a4", "title": "gta 6 speed funny", "description": "#gta6 #speed #shorts #trending", "tags": [], "channel": "Z", "views": 400_000},
    {"id": "a5", "title": "GTA 5 Speed", "description": "#gta5 #ishowspeed", "tags": [], "channel": "W", "views": 300_000},
    {"id": "a6", "title": "speed", "description": "#ishowspeed #speed #gta6", "tags": [], "channel": "V", "views": 200_000},
]


@pytest.fixture(autouse=True)
def root(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "ROOT", tmp_path / "ac")
    monkeypatch.setattr(research, "_api_search", lambda q, n: None)
    monkeypatch.setattr(research, "_ytdlp_search", lambda q, n: [dict(r) for r in ROWS])
    monkeypatch.setattr(research, "_details", lambda ids: {})


JOB = {"title": "IShowSpeed plays GTA 6 stream", "source": {"channel": "IShowSpeed", "url": "https://youtu.be/x", "channel_url": "https://youtube.com/@IShowSpeed"}}
CLIP = {"n": 1, "title": "Speed vs the cops", "text": "bro the cops are chasing me in gta 6 this is crazy chat", "moment": "cop chase", "franchise": "gta6"}


def test_query_is_who_and_which_game():
    assert research.query_for(JOB, CLIP) == "IShowSpeed GTA 6"
    assert research.query_for({"title": "my cooking video", "source": {}}, {"title": "", "text": "we cook pasta tonight with garlic"}) != ""


def test_analysis_scores_tags_by_views_and_finds_the_sound():
    a = research.analyse(ROWS)
    tags = [h["tag"] for h in a["hashtags"]]
    assert tags[:2] == ["ishowspeed", "gta6"] and "fyp" not in tags and "shorts" not in tags and "viral" not in tags
    assert a["sounds"][0]["title"] == "Raya (Slowed)" and a["sounds"][0]["uses"] == 2
    assert "@IShowSpeed" in a["mentions"] and a["examples"][0]["views"] == 26_000_000


def test_rules_pack_never_uses_the_wrong_game():
    res = research.top_shorts("IShowSpeed GTA 6")
    pk = research.recommend(JOB, CLIP, res)
    assert pk["hashtags"][0] == "ishowspeed" and "gta6" in pk["hashtags"] and "gta5" not in pk["hashtags"] and len(pk["hashtags"]) <= 5
    assert pk["mentions"] == ["@IShowSpeed"] and "@IShowSpeed" in pk["description"] and pk["sound"]["title"] == "Raya (Slowed)" and pk["by"] == "rules"


def test_the_checker_drops_what_the_ai_invents():
    res = research.top_shorts("IShowSpeed GTA 6")
    ai = lambda sysm, prompt: {"title": "Speed escapes the cops in GTA 5", "description": "Speed vs the cops #fake", "hashtags": ["#ishowspeed", "madeuptag", "gta6", "copchase"],  # noqa: E731
                               "mentions": ["@IShowSpeed", "@randomguy"], "hook": "He did NOT expect this"}
    pk = research.recommend(JOB, CLIP, res, ai)
    assert pk["by"] == "ai" and pk["title"] is None                         # names a game the footage is not: dropped
    assert "madeuptag" not in pk["hashtags"] and pk["hashtags"][:2] == ["ishowspeed", "gta6"]
    assert pk["mentions"] == ["@IShowSpeed"] and "#fake" not in pk["description"] and pk["hook"] == "He did NOT expect this"


def test_run_applies_packs_and_uses_the_sound_from_the_shelf(monkeypatch):
    from studio.autoclip import music
    monkeypatch.setattr(music, "tracks", lambda: [{"id": "t1", "name": "Raya slowed", "builtin": False}])
    clips = [dict(CLIP)]
    logs: list[str] = []
    summary = research.run(JOB, clips, None, logs.append)
    assert "IShowSpeed GTA 6" in summary and clips[0]["seo"]["music_id"] == "t1" and any("Best hashtags" in x for x in logs)
    pipeline.apply_packs(clips)
    assert "#ishowspeed" in clips[0]["description"]
    desc, tags = meta.build(clips[0], JOB)
    assert tags[0] == "ishowspeed" and desc.rstrip().endswith("#Shorts") and meta.mention_title("Speed vs the cops", JOB, clips[0]).endswith("@IShowSpeed")


def test_research_is_cached(monkeypatch):
    calls = []
    monkeypatch.setattr(research, "_ytdlp_search", lambda q, n: calls.append(q) or [dict(r) for r in ROWS])
    research.top_shorts("IShowSpeed GTA 6")
    research.top_shorts("IShowSpeed GTA 6")
    assert len(calls) == 1
    research.top_shorts("IShowSpeed GTA 6", fresh=True)
    assert len(calls) == 2
