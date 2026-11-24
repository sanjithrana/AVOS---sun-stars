"""Is this link OK to clip (any site), live streams, long streams. Network and yt-dlp are faked."""
from __future__ import annotations

import shutil
import subprocess
import time

import pytest

from studio.autoclip import intake, pipeline, rights, store, youtube

needs_ffmpeg = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg missing")


@pytest.fixture(autouse=True)
def root(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "ROOT", tmp_path / "ac")
    monkeypatch.setattr(intake, "public_url", lambda u: u.strip())
    monkeypatch.setattr(youtube, "channels", lambda: [{"id": "UCmine", "title": "Mine"}])
    rights._CACHE.clear()


def meta(**kw):
    return {"title": "Some video", "channel": "Creator", "channel_id": "UCx", "channel_url": "https://www.youtube.com/channel/UCx", "license": "", **kw}


Y = "https://www.youtube.com/watch?v=abc"


# ---------- which site ----------
@pytest.mark.parametrize("url,want", [
    ("https://www.youtube.com/watch?v=1", "youtube"), ("https://youtu.be/1", "youtube"), ("https://www.twitch.tv/somebody/video/1", "twitch"), ("https://kick.com/x", "kick"),
    ("https://www.tiktok.com/@a/video/1", "tiktok"), ("https://www.instagram.com/reel/1", "instagram"), ("https://x.com/a/status/1", "x"), ("https://vimeo.com/1", "vimeo"),
    ("https://www.netflix.com/watch/1", "drm"), ("https://www.hotstar.com/in/x", "drm"), ("https://open.spotify.com/track/1", "drm"), ("https://www.primevideo.com/detail/1", "drm"),
    ("https://example.com/a.mp4", "other"), ("https://notyoutube.com/x", "other"), ("https://youtube.com.evil.example/x", "other")])
def test_platform(url, want):
    assert rights.platform(url) == want


# ---------- the verdicts ----------
def test_paid_streaming_is_blocked_without_any_network(monkeypatch):
    monkeypatch.setattr(rights, "_meta", lambda u: pytest.fail("must not even look"))
    r = rights.check("https://www.netflix.com/watch/81")
    assert r["verdict"] == "blocked" and r["clippable"] is False and "DRM" in r["tip"]


@pytest.mark.parametrize("avail", ["private", "subscriber_only", "premium_only", "needs_auth"])
def test_private_and_members_only_are_blocked(avail):
    r = rights.check(Y, meta(availability=avail))
    assert r["verdict"] == "blocked" and not r["clippable"] and r["title"] == "Some video"


def test_public_video_is_ask_with_site_specific_advice():
    r = rights.check("https://www.twitch.tv/somebody/video/1", meta(availability="public", channel_url="https://www.twitch.tv/somebody"))
    assert r["verdict"] == "ask" and r["clippable"] and "streamer" in r["tip"].lower() and r["platform"] == "twitch" and r["links"]["channel"].endswith("/somebody")
    assert "streamer" not in rights.check(Y, meta())["tip"].lower() and rights.check(Y, meta())["links"]["about"].endswith("/about")


@pytest.mark.parametrize("lic,v", [("Creative Commons Attribution license (reuse allowed)", "creative-commons"), ("by", "creative-commons"), ("CC BY", "creative-commons"), ("by-nc", "creative-commons"), ("All rights reserved", "ask"), ("", "ask")])
def test_licences(lic, v):
    assert rights.check("https://vimeo.com/1", meta(license=lic))["verdict"] == v


def test_own_channel_only_counts_on_youtube():
    assert rights.check(Y, meta(channel_id="UCmine"))["verdict"] == "own"
    assert rights.check("https://vimeo.com/1", meta(channel_id="UCmine"))["verdict"] == "ask"


def test_unreadable_page_is_unknown_not_safe(monkeypatch):
    monkeypatch.setattr(rights, "_meta", lambda u: None)
    r = rights.check("https://example.com/a")
    assert r["verdict"] == "unknown" and r["clippable"] and r["live"] is None


# ---------- live ----------
def test_live_now_can_be_recorded():
    r = rights.check(Y, meta(is_live=True, live_status="is_live"))
    assert r["live"] == {"state": "live"} and r["clippable"] and any("live right now" in n for n in r["notes"])


def test_upcoming_and_processing_are_not_clippable_yet():
    u = rights.check(Y, meta(live_status="is_upcoming"))
    assert u["live"]["state"] == "upcoming" and not u["clippable"]
    p = rights.check(Y + "2", meta(live_status="post_live"))
    assert p["live"]["state"] == "processing" and not p["clippable"]


def test_a_finished_stream_is_a_normal_video_with_a_note():
    r = rights.check(Y, meta(was_live=True, live_status="was_live"))
    assert r["live"] == {"state": "past"} and r["clippable"] and any("live stream" in n for n in r["notes"])


def test_long_streams_get_the_range_hint_on_youtube_and_twitch_only():
    assert any("4.0 hours" in n for n in rights.check(Y, meta(duration=4 * 3600))["notes"])
    assert not any("hours" in n for n in rights.check("https://vimeo.com/1", meta(duration=4 * 3600))["notes"])


def test_answers_are_remembered(monkeypatch):
    n = []
    monkeypatch.setattr(rights, "_meta", lambda u: n.append(u) or meta())
    rights.check(Y)
    rights.check(Y)
    assert len(n) == 1


def test_blocked_never_posts():
    assert rights.permission_for("blocked", True) == "blocked"
    assert rights.can_post({"permission": "blocked"}) is False and rights.can_post({"permission": "cc"}) and rights.can_post({})


# ---------- recording a live stream ----------
@pytest.fixture
def stream(tmp_path):
    p = tmp_path / "live.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=640x360:r=25:d=10", "-f", "lavfi", "-i", "sine=f=300:d=10", "-b:v", "900k", "-c:v", "libx264",
                    "-preset", "ultrafast", "-c:a", "aac", "-shortest", str(p)], check=True)
    return p


@needs_ffmpeg
def test_record_live_makes_a_source_and_reports_progress(stream, tmp_path, monkeypatch):
    monkeypatch.setattr(intake, "have_ytdlp", lambda: True)
    monkeypatch.setattr(intake, "live_urls", lambda u: [str(stream)])
    seen = []
    out = intake.record_live("https://www.twitch.tv/x", 60, tmp_path / "d", progress=lambda p, t: seen.append((p, t)))
    assert out.name == "source.mp4" and out.stat().st_size > 50_000
    from studio.autoclip import pick
    assert 8 <= pick.duration(str(out)) <= 11                          # a stream that ends early keeps what it got


@needs_ffmpeg
def test_record_live_with_separate_video_and_audio_streams(stream, tmp_path, monkeypatch):
    monkeypatch.setattr(intake, "have_ytdlp", lambda: True)
    monkeypatch.setattr(intake, "live_urls", lambda u: [str(stream), str(stream)])
    assert intake.record_live("https://www.twitch.tv/x", 60, tmp_path / "d").is_file()


def test_record_live_failures_are_plain_words(tmp_path, monkeypatch):
    monkeypatch.setattr(intake, "have_ytdlp", lambda: True)
    def no(u):
        raise RuntimeError("Could not open the live stream: offline")
    monkeypatch.setattr(intake, "live_urls", no)
    with pytest.raises(RuntimeError, match="offline"):
        intake.record_live("https://www.twitch.tv/x", 60, tmp_path / "d")
    monkeypatch.setattr(intake, "have_ytdlp", lambda: False)
    with pytest.raises(RuntimeError, match="yt-dlp"):
        intake.record_live("https://www.twitch.tv/x", 60, tmp_path / "d")


@needs_ffmpeg
def test_record_live_with_nothing_received_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(intake, "have_ytdlp", lambda: True)
    monkeypatch.setattr(intake, "live_urls", lambda u: [str(tmp_path / "missing.mp4")])
    with pytest.raises(RuntimeError, match="live recording failed"):
        intake.record_live("https://www.twitch.tv/x", 60, tmp_path / "d")
    assert not (tmp_path / "d" / "source.mp4").exists()


def test_stop_ends_the_recording_and_removes_the_pieces(tmp_path, monkeypatch):
    killed = []

    class Fake:
        returncode = None
        def __init__(self, *a, **k): pass
        def poll(self): return None
        def kill(self): killed.append(1)
        def wait(self): return 0
    monkeypatch.setattr(intake, "have_ytdlp", lambda: True)
    monkeypatch.setattr(intake, "live_urls", lambda u: ["http://x/y.m3u8"])
    monkeypatch.setattr(intake.subprocess, "Popen", Fake)
    class Stopped(Exception): pass
    def cancel():
        raise Stopped()
    with pytest.raises(Stopped):
        intake.record_live("https://www.twitch.tv/x", 600, tmp_path / "d", cancel=cancel)
    assert killed


def test_a_section_is_requested_from_yt_dlp(tmp_path, monkeypatch):
    got = {}

    class Fake:
        returncode = 1
        def __init__(self, cmd, **k): got["cmd"] = cmd
        def poll(self): return 1
        def kill(self): pass
        def wait(self): return 1
    monkeypatch.setattr(intake, "have_ytdlp", lambda: True)
    monkeypatch.setattr(intake.subprocess, "Popen", Fake)
    with pytest.raises(RuntimeError):
        intake.download(Y, tmp_path / "d", section=(600, 1800))
    c = got["cmd"]
    assert c[c.index("--download-sections") + 1] == "*600-1800"
    with pytest.raises(RuntimeError):
        intake.download(Y, tmp_path / "e")
    assert "--download-sections" not in got["cmd"]


# ---------- the HTTP side ----------
def client(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from studio.autoclip import routes
    monkeypatch.setattr(pipeline, "start", lambda jid: None)
    app = FastAPI()
    app.include_router(routes.router)
    return TestClient(app)


def fake_check(monkeypatch, **kw):
    base = {"verdict": "ask", "clippable": True, "platform": "youtube", "tip": "t", "notes": [], "title": "Their stream", "channel": "c", "links": {}, "live": None}
    monkeypatch.setattr(rights, "check", lambda url, extra=None: {**base, **kw})


def test_blocked_links_are_refused_by_the_server(monkeypatch):
    fake_check(monkeypatch, verdict="blocked", clippable=False, tip="Paid streaming services protect their videos (DRM).")
    r = client(monkeypatch).post("/api/autoclip/jobs", json={"url": "https://www.netflix.com/watch/1", "verdict": "own", "ack": True})
    assert r.status_code == 400 and "DRM" in r.json()["error"]


def test_upcoming_streams_are_refused(monkeypatch):
    fake_check(monkeypatch, clippable=False, live={"state": "upcoming"}, notes=["This stream hasn't started yet."])
    r = client(monkeypatch).post("/api/autoclip/jobs", json={"url": Y})
    assert r.status_code == 400 and "hasn't started" in r.json()["error"]


def test_the_server_verdict_beats_what_the_form_says(monkeypatch):
    fake_check(monkeypatch, verdict="ask")
    c = client(monkeypatch)
    j = c.post("/api/autoclip/jobs", json={"url": Y, "verdict": "own", "ack": False}).json()          # a form claiming "own" does not make it own
    assert store.load(j["id"])["permission"] == "unconfirmed" and store.load(j["id"])["title"] == "Their stream"
    fake_check(monkeypatch, verdict="creative-commons")
    j2 = c.post("/api/autoclip/jobs", json={"url": Y + "2", "verdict": "ask"}).json()
    assert store.load(j2["id"])["permission"] == "cc"


def test_a_live_link_becomes_a_recording_job(monkeypatch):
    fake_check(monkeypatch, live={"state": "live"})
    c = client(monkeypatch)
    j = c.post("/api/autoclip/jobs", json={"url": Y, "live_minutes": 30, "verdict": "ask", "ack": True}).json()
    s = store.load(j["id"])["source"]
    assert s["kind"] == "live" and s["minutes"] == 30
    assert store.load(c.post("/api/autoclip/jobs", json={"url": Y, "live_minutes": 99999}).json()["id"])["source"]["minutes"] == 240
    assert store.load(c.post("/api/autoclip/jobs", json={"url": Y, "live_minutes": "abc"}).json()["id"])["source"]["minutes"] == 20


def test_check_endpoint_reports_live_and_does_not_block(monkeypatch):
    monkeypatch.setattr(rights, "_meta", lambda u: (time.sleep(0.1), meta(is_live=True))[1])
    r = client(monkeypatch).post("/api/autoclip/check", json={"url": Y}).json()
    assert r["live"] == {"state": "live"} and r["platform"] == "youtube"


# ---------- the whole pipeline ----------
@needs_ffmpeg
def test_a_live_job_records_then_clips(stream, monkeypatch, tmp_path):
    def fake_record(url, secs, dest, log=None, cancel=None, progress=None):
        dest.mkdir(parents=True, exist_ok=True)
        shutil.copy(stream, dest / "source.mp4")
        assert secs == 600
        return dest / "source.mp4"
    monkeypatch.setattr(intake, "record_live", fake_record)
    job = pipeline.new_job(pipeline.build_opts({"hype_only": "false", "count": 1, "min_seconds": 3, "max_seconds": 6}), {"kind": "live", "url": "https://www.twitch.tv/x", "minutes": 10, "name": "Live"})
    pipeline._run(job["id"])
    j = store.load(job["id"])
    assert j["status"] == "done", j.get("error")
    assert j["clips"][0]["file"]


@needs_ffmpeg
def test_a_range_on_a_long_stream_downloads_only_that_part(stream, monkeypatch):
    seen = {}

    def fake_dl(url, dest, log=None, cancel=None, progress=None, section=None):
        seen["section"] = section
        dest.mkdir(parents=True, exist_ok=True)
        shutil.copy(stream, dest / "source.mp4")
        return dest / "source.mp4"
    monkeypatch.setattr(intake, "download", fake_dl)
    opts = pipeline.build_opts({"hype_only": "false", "count": 1, "min_seconds": 3, "max_seconds": 6, "start_min": 60, "end_min": 61})
    job = pipeline.new_job(opts, {"kind": "url", "url": Y, "name": "Long"})
    pipeline._run(job["id"])
    j = store.load(job["id"])
    assert seen["section"] == (3600, 3660) and j["status"] == "done", j.get("error")        # the file is 10 s long: the window was not applied a second time
    assert j["source"]["section"] == [3600, 3660]
