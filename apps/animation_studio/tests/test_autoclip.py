"""Auto Clip: picking, cutting, the YouTube login and upload (all faked: no network, no real key) and the autopilot's rules."""
from __future__ import annotations

import json
import shutil
import subprocess
import time
from datetime import datetime, timedelta, timezone

import pytest

from studio.autoclip import autopilot, cut, intake, pick, pipeline, store, transcript, youtube

needs_ffmpeg = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not installed")
SRT = "1\n00:00:21,000 --> 00:00:24,000\nThis is the loud part of the stream\n\n2\n00:00:24,500 --> 00:00:27,000\nand here it gets wild\n"


@pytest.fixture(autouse=True)
def root(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "ROOT", tmp_path / "ac")
    autopilot._last_stats = 0.0
    yield


@pytest.fixture
def video(tmp_path):
    p = tmp_path / "src.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=640x360:r=25:d=60", "-f", "lavfi", "-i", "sine=f=300:d=60",
                    "-filter_complex", "[1:a]volume='if(between(t,20,35),1.0,0.05)':eval=frame[a]", "-map", "0:v", "-map", "[a]", "-c:v", "libx264",
                    "-preset", "ultrafast", "-c:a", "aac", "-shortest", str(p)], check=True)
    return p


# ---------- transcript ----------
def test_srt_words_and_text():
    cues = transcript.parse_srt(SRT)
    assert len(cues) == 2 and cues[0]["start"] == 21.0
    w = transcript.words_of(cues)
    assert [x["w"] for x in w][:3] == ["This", "is", "the"] and w[0]["s"] == 21.0 and w[-1]["e"] == pytest.approx(27.0, abs=0.01)
    assert "wild" in transcript.text_between(cues, 25, 26)


# ---------- picking ----------
@needs_ffmpeg
def test_the_loud_stretch_is_picked(video):
    lv = pick.loudness(str(video))
    assert 58 <= len(lv) <= 62
    m = pick.choose(lv, 1, 10, 20)
    assert len(m) == 1 and 15 <= m[0]["start"] <= 25


def test_edges_move_to_sentence_edges_and_never_break_the_limits():
    cues = [{"start": 18.2, "end": 22.0, "text": "a"}, {"start": 22.5, "end": 33.4, "text": "b"}]
    a, b = pick._snap(20.0, 32.0, cues, 10, 20)
    assert a == 18.2 and b == 33.4 and b - a <= 20
    a, b = pick._snap(20.0, 25.0, [], 10, 20)
    assert (a, b) == (20.0, 25.0)


def test_titles():
    assert pick.title_for("This is the loud part of the stream. And more.", 1) == "This is the loud part of the stream"
    assert "Highlight" not in pick.title_for("", 4)
    assert len(pick.title_for("word " * 40, 1)) <= 60


# ---------- cutting ----------
@needs_ffmpeg
def test_cut_makes_a_vertical_clip_with_captions_in_each_layout(video, tmp_path):
    words = transcript.words_of(transcript.parse_srt(SRT))
    for lay in cut.LAYOUTS:
        out = tmp_path / f"{lay}.mp4"
        cut.cut(str(video), str(out), 20, 30, lay, "720p", cut.ass_for(words, 20, 30, "bounce", 720, 1280))
        info = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=width,height", "-of", "csv=p=0", str(out)], capture_output=True, text=True).stdout
        assert "720,1280" in info and out.with_suffix(".jpg").is_file()
    assert cut.ass_for(words, 20, 30, "none", 720, 1280) is None and cut.ass_for([], 20, 30, "bounce", 720, 1280) is None
    a = cut.ass_for(words, 20, 30, "hype", 720, 1280)
    assert "THIS" in a and a.count("Dialogue:") == len(words)


# ---------- intake ----------
def test_private_addresses_and_bad_links_are_refused():
    for bad in ("http://127.0.0.1/x", "http://192.168.0.5/a", "ftp://example.com/x", "file:///etc/passwd", "not a link"):
        with pytest.raises(RuntimeError):
            intake.public_url(bad)


def test_a_youtube_block_is_reported_plainly_and_not_worked_around(monkeypatch, tmp_path):
    monkeypatch.setattr(intake, "public_url", lambda u: u)
    monkeypatch.setattr(intake, "have_ytdlp", lambda: True)

    class P:
        returncode = 1

        def __init__(self, cmd, stdout=None, stderr=None, text=None):
            stderr.write("ERROR: Sign in to confirm you're not a bot")

        def poll(self):
            return 1
    monkeypatch.setattr(intake.subprocess, "Popen", P)
    with pytest.raises(RuntimeError, match="YouTube isn't letting Auto Clip download"):
        intake.download("https://youtu.be/abc", tmp_path)
    monkeypatch.setattr(intake, "have_ytdlp", lambda: False)
    with pytest.raises(RuntimeError, match="pip install yt-dlp"):
        intake.download("https://example.com/v", tmp_path)


# ---------- settings ----------
def test_settings_are_clamped_and_safe_by_default():
    st = store.settings()
    assert st["autopilot"]["enabled"] is False and st["autopilot"]["review_first"] is True and st["autopilot"]["privacy"] == "private" and st["rights_ack"] is False
    st = store.clean_settings({"autopilot": {"per_day": 999, "min_gap_minutes": 1, "hours": [25, -3], "privacy": "weird", "enabled": 1},
                               "defaults": {"count": 99, "min_seconds": 100, "max_seconds": 20, "layout": "x"}})
    assert st["autopilot"]["per_day"] == 20 and st["autopilot"]["min_gap_minutes"] == 10 and st["autopilot"]["hours"] == [23, 0]
    assert st["autopilot"]["privacy"] == "private" and st["autopilot"]["enabled"] is True
    assert st["defaults"]["count"] == 20 and st["defaults"]["max_seconds"] == 100 and st["defaults"]["layout"] == "blur"
    st = store.clean_settings({"watch": [{"channel_id": "UC" + "a" * 22, "name": "x"}, {"channel_id": "bad"}]})
    assert [w["channel_id"] for w in st["watch"]] == ["UC" + "a" * 22]


# ---------- YouTube (faked) ----------
class Resp:
    def __init__(self, code=200, js=None, headers=None, text=""):
        self.status_code, self._js, self.headers, self.text = code, js or {}, headers or {}, text or json.dumps(js or {})

    def json(self):
        return self._js


def connect(monkeypatch, scopes="a yt-analytics-monetary.readonly"):
    youtube.set_client("123.apps.googleusercontent.com", "secret-not-real")
    url = youtube.auth_url("http://localhost:3000")
    state = url.split("state=")[1].split("&")[0]
    calls = []

    def fake(method, url, **kw):
        calls.append((method, url, kw))
        if url == youtube.TOKEN:
            return Resp(js={"access_token": "AT", "refresh_token": "RT", "expires_in": 3600, "scope": scopes})
        if url.endswith("/channels"):
            return Resp(js={"items": [{"id": "UCtest", "snippet": {"title": "My Channel", "thumbnails": {}}, "statistics": {"subscriberCount": "12"}}]})
        raise AssertionError(url)
    monkeypatch.setattr(youtube, "_req", fake)
    info = youtube.finish("code123", state)
    return info, calls


def test_connect_flow_keeps_tokens_private_and_rejects_a_forged_state(monkeypatch):
    youtube.set_client("123.apps.googleusercontent.com", "secret-not-real")
    url = youtube.auth_url("http://localhost:3000")
    assert "access_type=offline" in url and "localhost%3A3000%2Fstudio-api%2Fautoclip%2Fyoutube%2Fcallback" in url and "yt-analytics-monetary" in url
    with pytest.raises(RuntimeError, match="expired or is not from this studio"):
        youtube.finish("x", "forged")
    info, calls = connect(monkeypatch)
    assert info["id"] == "UCtest"
    ch = youtube.channels()
    assert ch[0]["title"] == "My Channel" and "refresh" not in ch[0] and "access" not in ch[0] and ch[0]["revenue_scope"] is True
    assert oct((store.ROOT / "accounts.json").stat().st_mode & 0o777) == "0o600"


def test_a_dead_login_is_reported_not_retried(monkeypatch):
    connect(monkeypatch)
    a = store.accounts()
    a["channels"]["UCtest"]["expires"] = 0
    store.save_accounts(a)
    monkeypatch.setattr(youtube, "_req", lambda *a, **k: Resp(400, {"error": "invalid_grant"}))
    with pytest.raises(youtube.NeedsLogin):
        youtube.token("UCtest")
    assert youtube.channels()[0]["needs_login"] is True


def test_upload_is_resumable_private_by_default_and_tagged_shorts(monkeypatch, tmp_path):
    connect(monkeypatch)
    f = tmp_path / "c.mp4"
    f.write_bytes(b"x" * 100)
    seen = []

    def fake(method, url, **kw):
        seen.append((method, url, kw))
        if method == "POST":
            return Resp(headers={"location": "https://upload/session"})
        return Resp(js={"id": "VID123"})
    monkeypatch.setattr(youtube, "_req", fake)
    vid = youtube.upload("UCtest", str(f), "Hello <b>", "desc", "weird")
    assert vid == "VID123"
    meta = seen[0][2]["json"]
    assert meta["status"]["privacyStatus"] == "private" and "#Shorts" in meta["snippet"]["description"] and "<" not in meta["snippet"]["title"]
    assert seen[0][2]["headers"]["Authorization"] == "Bearer AT" and seen[1][0] == "PUT"


def test_latest_uploads_reads_the_public_feed(monkeypatch):
    feed = "<feed><entry><yt:videoId>abcdefghijk</yt:videoId><title>New &amp; loud</title></entry><entry><yt:videoId>lmnopqrstuv</yt:videoId><title>Old</title></entry></feed>"
    monkeypatch.setattr(youtube, "_req", lambda *a, **k: Resp(text=feed))
    assert youtube.latest_uploads("UCx") == [{"id": "abcdefghijk", "title": "New & loud"}, {"id": "lmnopqrstuv", "title": "Old"}]


# ---------- autopilot ----------
def make_job(n=3, approved=True):
    job = pipeline.new_job(pipeline.build_opts({}), {"kind": "upload", "name": "t"})
    d = store.jdir(job["id"])
    (d / "clips").mkdir()
    clips = []
    for i in range(1, n + 1):
        (d / "clips" / f"clip-{i}.mp4").write_bytes(b"v")
        clips.append({"n": i, "title": f"T{i}", "file": f"clips/clip-{i}.mp4", "status": "ready", "approved": approved, "youtube_id": None})
    store.update(job["id"], lambda j: j.update(status="done", clips=clips))
    return job["id"]


def arm(monkeypatch, **ap):
    connect(monkeypatch)
    store.clean_settings({"rights_ack": True, "autopilot": {"enabled": True, "hours": [0, 23], "min_gap_minutes": 10, "per_day": 5, **ap}})


def noon():
    t = datetime.now(timezone.utc).replace(hour=6, minute=30)         # 12:00 at +5:30
    return t - timedelta(days=1) if t > datetime.now(timezone.utc) else t     # never in the future, whatever time the tests run


def test_autopilot_does_nothing_until_every_switch_is_on(monkeypatch):
    make_job()
    calls = []
    up = lambda *a: calls.append(a) or "V"  # noqa: E731
    assert autopilot.tick(up) == "off"
    store.clean_settings({"autopilot": {"enabled": True}})
    assert autopilot.tick(up).startswith("waiting: confirm you own")          # no rights tick: nothing posts
    arm(monkeypatch)
    store.clean_settings({"autopilot": {"paused": True}})
    assert autopilot.tick(up) == "paused" and calls == []


def test_review_first_posts_only_approved_clips(monkeypatch):
    jid = make_job(2, approved=False)
    arm(monkeypatch, review_first=True)
    up = lambda *a: "V1"  # noqa: E731
    assert autopilot.tick(up, now=noon()) == "nothing to post"
    store.update(jid, lambda j: j["clips"][0].update(approved=True))
    assert autopilot.tick(up, now=noon()) == "posted V1"
    j = store.load(jid)
    assert j["clips"][0]["status"] == "posted" and j["clips"][0]["youtube_id"] == "V1" and j["clips"][1]["youtube_id"] is None


def test_fully_automatic_respects_cap_gap_hours_and_schedule(monkeypatch):
    jid = make_job(4, approved=False)
    arm(monkeypatch, review_first=False, per_day=2, min_gap_minutes=60)
    out = iter(["A", "B", "C"])
    up = lambda *a: next(out)  # noqa: E731
    assert autopilot.tick(up, now=noon()) == "posted A"
    assert autopilot.tick(up, now=noon()) == "waiting for the minimum gap"
    st = store.settings()
    st["posted_log"] = [(noon() - timedelta(minutes=90)).isoformat()]
    store.save_settings(st)
    assert autopilot.tick(up, now=noon()) == "posted B"
    assert autopilot.tick(up, now=noon() + timedelta(hours=3)) == "daily limit reached (2)"
    store.clean_settings({"autopilot": {"hours": [9, 10]}})
    st = store.settings()
    st["posted_log"] = []
    store.save_settings(st)
    assert autopilot.tick(up, now=noon() + timedelta(hours=8)) == "outside posting hours"      # 20:00 local, window is 9 to 10
    assert autopilot.in_hours(datetime(2026, 1, 1, 20, 30, tzinfo=timezone.utc), [22, 6], 330) is True     # a window that wraps midnight: 02:00 local
    store.update(jid, lambda j: [c.update(schedule_at=(noon() + timedelta(days=1)).isoformat()) for c in j["clips"] if c["youtube_id"] is None])
    store.clean_settings({"autopilot": {"hours": [0, 23]}})
    assert autopilot.tick(up, now=noon()) == "nothing to post"                      # their own schedule time has not come


def test_a_failed_upload_is_counted_and_a_dead_login_pauses_posting(monkeypatch):
    jid = make_job(1)
    arm(monkeypatch)

    def boom(*a):
        raise RuntimeError("quota")
    assert autopilot.tick(boom, now=noon()) == "post failed"
    c = store.load(jid)["clips"][0]
    assert c["status"] == "ready" and c["attempts"] == 1 and "quota" in c["error"]

    def dead(*a):
        raise youtube.NeedsLogin("Google no longer accepts the saved login")
    assert autopilot.tick(dead, now=noon()) == "paused: login expired"
    st = store.settings()
    assert st["autopilot"]["paused"] is True and "no longer accepts" in st["notice"]
    assert autopilot.tick(lambda *a: "X", now=noon()) == "paused"


def test_the_chosen_channel_is_never_swapped_for_another(monkeypatch):
    make_job(1)
    arm(monkeypatch, channel="UCsomeoneelse")
    assert autopilot.tick(lambda *a: "V", now=noon()) == "no channel"


def test_the_watch_list_makes_jobs_from_new_uploads_but_not_the_backlog(monkeypatch):
    arm(monkeypatch, review_first=True, auto_make=True)
    store.clean_settings({"watch": [{"channel_id": "UC" + "a" * 22, "name": "Streamer"}]})
    started = []
    monkeypatch.setattr(pipeline, "start", lambda jid: started.append(jid) or True)
    feed = [{"id": "aaaaaaaaaaa", "title": "Old"}]
    assert autopilot.tick(lambda *a: "V", lambda c: feed, now=noon()) == "nothing to post" and started == []     # first look records only
    feed.insert(0, {"id": "bbbbbbbbbbb", "title": "Fresh stream"})
    assert autopilot.tick(lambda *a: "V", lambda c: feed, now=noon()).startswith("started clips from 'Fresh stream'")
    assert len(started) == 1 and store.load(started[0])["auto"] is True
    assert autopilot.tick(lambda *a: "V", lambda c: feed, now=noon()) == "nothing to post" and len(started) == 1       # seen now


def test_stats_are_written_onto_the_clips(monkeypatch):
    jid = make_job(1)
    arm(monkeypatch)
    store.update(jid, lambda j: j["clips"][0].update(youtube_id="VID", channel="UCtest", status="posted"))
    monkeypatch.setattr(youtube, "stats", lambda cid, ids: {"VID": {"views": 42, "likes": 3, "comments": 0, "privacy": "private"}})
    assert autopilot.refresh_stats(force=True) == 1
    assert store.load(jid)["clips"][0]["stats"]["views"] == 42


# ---------- the whole job, with real ffmpeg ----------
@needs_ffmpeg
def test_a_job_runs_from_upload_to_clips(video):
    job = pipeline.new_job(pipeline.build_opts({"count": 1, "min_seconds": 8, "max_seconds": 15}), {"kind": "upload", "name": "t"})
    d = store.jdir(job["id"])
    shutil.copy(video, d / "source.mp4")
    (d / "source.srt").write_text(SRT)
    pipeline._cancel[job["id"]] = __import__("threading").Event()
    pipeline._run(job["id"])
    j = store.load(job["id"])
    assert j["status"] == "done", j.get("error")
    c = j["clips"][0]
    assert c["status"] == "ready" and c["captions"] is True and (d / c["file"]).is_file() and c["approved"] is False
    assert 8 <= c["end"] - c["start"] <= 15 and "your subtitles" in j["steps"]["pick"]["note"]


# ---------- the HTTP API ----------
def client():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from studio.autoclip.routes import router
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_api_overview_never_leaks_a_token_and_rejects_bad_input(monkeypatch):
    connect(monkeypatch)
    c = client()
    body = c.get("/api/autoclip").text
    assert "RT" not in json.loads(body)["channels"][0] and "secret-not-real" not in body and "refresh" not in body
    assert c.post("/api/autoclip/jobs", json={"url": "http://127.0.0.1/x"}).status_code == 400
    assert c.post("/api/autoclip/jobs", json={}).status_code == 400
    assert c.post("/api/autoclip/youtube/client", json={"client_id": "nope", "client_secret": "x"}).status_code == 400
    assert c.get("/api/autoclip/youtube/connect", params={"origin": "http://evil.example"}).status_code == 400
    r = c.get("/api/autoclip/youtube/callback", params={"error": "access_denied"}, follow_redirects=False)
    assert r.status_code in (302, 307) and "error=" in r.headers["location"]


def test_api_posting_needs_the_rights_tick_and_files_are_fenced(monkeypatch):
    jid = make_job(1)
    c = client()
    connect(monkeypatch)
    assert c.post(f"/api/autoclip/jobs/{jid}/clips/1/post").status_code == 409                 # no rights tick
    d = store.jdir(jid)
    (d / "source.mp4").write_bytes(b"secret source")
    assert c.get(f"/api/autoclip/jobs/{jid}/file/clips/clip-1.mp4").status_code == 200
    assert c.get(f"/api/autoclip/jobs/{jid}/file/source.mp4").status_code == 404                # the raw source is never served
    assert c.get(f"/api/autoclip/jobs/{jid}/file/..%2F..%2Fsettings.json").status_code == 404
    assert c.get(f"/api/autoclip/jobs/{jid}/file/job.json").status_code == 404


def test_api_edit_approve_settings_and_pause(monkeypatch):
    jid = make_job(1, approved=False)
    c = client()
    r = c.patch(f"/api/autoclip/jobs/{jid}/clips/1", json={"title": "New <title>", "approved": True, "schedule_at": "2026-12-01T10:00:00+05:30"})
    clip = r.json()["clips"][0]
    assert clip["title"] == "New title" and clip["approved"] is True and clip["schedule_at"] == "2026-12-01T04:30:00+00:00"
    s = c.put("/api/autoclip/settings", json={"rights_ack": True, "autopilot": {"enabled": True, "per_day": 500}}).json()["settings"]
    assert s["rights_ack"] is True and s["autopilot"]["per_day"] == 20 and "posted_log" not in s
    assert c.post("/api/autoclip/pause", json={"paused": True}).json()["settings"]["autopilot"]["paused"] is True
    assert c.post("/api/autoclip/pause", json={"paused": False}).json()["settings"]["autopilot"]["paused"] is False


@needs_ffmpeg
def test_api_upload_runs_a_job(video):
    import time as _t
    c = client()
    with open(video, "rb") as f:
        r = c.post("/api/autoclip/jobs", data={"count": "1", "min_seconds": "8", "max_seconds": "15"}, files={"file": ("my stream.mp4", f, "video/mp4"),
                                                                                                           "srt": ("s.srt", SRT.encode(), "text/plain")})
    assert r.status_code == 200, r.text
    jid = r.json()["id"]
    for _ in range(120):
        j = c.get(f"/api/autoclip/jobs/{jid}").json()
        if j["status"] != "working":
            break
        _t.sleep(0.5)
    assert j["status"] == "done", j.get("error")
    assert c.get(f"/api/autoclip/jobs/{jid}/file/{j['clips'][0]['file']}").status_code == 200


# ---------- the Library / top-bar feed ----------
def test_finished_clips_show_in_the_library_with_a_ready_message():
    from studio import activity
    job = pipeline.new_job(pipeline.build_opts({}), {"kind": "upload", "name": "My long stream"})
    store.update(job["id"], lambda j: j.update(status="done", clips=[{"n": 1, "title": "a", "thumb": "clips/clip-1.jpg", "file": "clips/clip-1.mp4", "status": "ready"},
                                                                    {"n": 2, "title": "b", "status": "ready"}]))
    items = [x for x in activity.everything()["items"] if x["studio"] == "Auto Clip"]
    assert len(items) == 1
    it = items[0]
    assert it["state"] == "done" and "ready" in it["stage"] and "2 clips" in it["stage"]
    assert it["href"] == f"/autoclip?open={job['id']}" and it["thumb"].endswith("/clips/clip-1.jpg")
    # a running video shows as running, with no picture yet
    j2 = pipeline.new_job(pipeline.build_opts({}), {"kind": "upload", "name": "Another"})
    run = [x for x in activity.collect()["jobs"] if x["id"] == j2["id"]]
    assert run and run[0]["state"] == "running" and run[0]["thumb"] is None


# ---------- GTA 6 Clip Kit preset ----------
def test_the_gta6_preset_reads_moments_from_what_is_said():
    from studio.autoclip import presets
    assert presets.classify("The cops are chasing me, wanted level, police helicopter!")[0] == "cop chase"
    assert presets.classify("Oh no we crashed, the car exploded, huge crash")[0] == "crash"
    assert presets.classify("the weather is nice today") == (None, 0.0)
    assert presets.hook("cop chase") == "The cops did NOT expect this" and presets.hook(None)
    p = presets.get("gta6")
    assert presets.title(p, "crash", "Big one") == "GTA 6 crash: Big one" and presets.title(p, None, "").startswith("GTA 6")
    assert presets.get("nope") is None


def test_the_preset_lets_what_is_said_outrank_plain_loudness():
    from studio.autoclip import presets
    moments = [{"score": 5.0}, {"score": 5.2}, {"score": 5.1}, {"score": 4.9}]
    texts = ["quiet talk about the weather", "more talk about lunch", "the cops chase me, police helicopter, wanted", "random words"]
    assert presets.rerank(moments, texts, 2) == [1, 2] or 2 in presets.rerank(moments, texts, 2)
    assert 2 in presets.rerank(moments, texts, 1)


def test_the_hook_line_is_burned_for_the_first_seconds_even_without_a_transcript():
    from studio.autoclip import cut
    a = cut.ass_for([], 0, 30, "bounce", 720, 1280, hook="He did NOT see that coming")
    assert a and "Style: Hook" in a and "HE DID NOT SEE\\NTHAT COMING" in a and "0:00:02.80" in a
    assert cut.ass_for([], 0, 30, "bounce", 720, 1280) is None
    assert cut.ass_for([{"w": "hi", "s": 1, "e": 2}], 0, 30, "bounce", 720, 1280) and "Hook," not in cut.ass_for([{"w": "hi", "s": 1, "e": 2}], 0, 30, "bounce", 720, 1280).split("[Events]")[1]


def test_an_unknown_preset_is_dropped_from_the_job_options():
    from studio.autoclip import pipeline
    assert pipeline.build_opts({"preset": "gta6"})["preset"] == "gta6"
    assert pipeline.build_opts({"preset": "evil"})["preset"] == ""
    assert pipeline.build_opts({})["preset"] == ""


def test_stop_ends_a_download_in_progress(tmp_path, monkeypatch):
    import sys
    import time
    from studio.autoclip import intake, pipeline
    monkeypatch.setattr(intake, "public_url", lambda u: u)
    monkeypatch.setattr(intake, "have_ytdlp", lambda: True)
    monkeypatch.setattr(intake.sys, "executable", sys.executable)
    (tmp_path / "fake_yt").mkdir()
    (tmp_path / "fake_yt" / "yt_dlp.py").write_text("import time\nopen('source.part','w').write('x')\ntime.sleep(60)\n")
    monkeypatch.setenv("PYTHONPATH", str(tmp_path / "fake_yt"))
    stopped = {"n": 0}

    def cancel():
        stopped["n"] += 1
        if stopped["n"] > 3:
            raise pipeline.Stopped()
    t0 = time.time()
    with pytest.raises(pipeline.Stopped):
        intake.download("https://example.com/v", tmp_path, cancel=cancel)
    assert time.time() - t0 < 10


def test_download_progress_is_reported_from_ytdlp_lines(tmp_path, monkeypatch):
    import sys
    from studio.autoclip import intake
    monkeypatch.setattr(intake, "public_url", lambda u: u)
    monkeypatch.setattr(intake, "have_ytdlp", lambda: True)
    (tmp_path / "fake").mkdir()
    (tmp_path / "fake" / "yt_dlp.py").write_text(
        "import sys, time, pathlib\nfor p in (10, 55, 100):\n"
        "    print('PCT  %.1f%% | %d.0MiB of 200.0MiB | 5.0MiB/s | ETA 00:0%d' % (p, p*2, 3), flush=True); time.sleep(0.9)\n"
        "out = pathlib.Path(sys.argv[sys.argv.index('-o')+1].replace('%(ext)s','mp4')); out.write_bytes(b'x'*10)\nprint(out)\n")
    monkeypatch.setenv("PYTHONPATH", str(tmp_path / "fake"))
    got = []
    r = intake.download("https://example.com/v", tmp_path, progress=lambda pct, text: got.append((pct, text)))
    assert r.name == "source.mp4" and got and got[-1][0] >= 55 and "MiB" in got[-1][1]


def test_progress_is_written_to_the_job_and_cleared_when_a_step_starts():
    from studio.autoclip import pipeline, store
    job = pipeline.new_job(pipeline.build_opts({}), {"kind": "upload", "name": "x"})
    pipeline.progress(job["id"], 42.0, "Downloading: 84 MiB of 200 MiB")
    assert store.load(job["id"])["progress"]["pct"] == 42.0
    pipeline._step(job["id"], "pick", status="working")
    assert store.load(job["id"])["progress"] is None


def test_captions_wrap_and_never_run_off_the_frame():
    import re
    from studio.autoclip import cut
    words = [{"w": w, "s": i * 0.4, "e": i * 0.4 + 0.35} for i, w in enumerate("supercars throwback videos in a long airport and as".split())]
    a = cut.ass_for(words, 0, 10, "hype", 720, 1280, hook="Impossible stunt. Watch this")
    assert "WrapStyle: 2" in a                       # one line, never wrapped: a long line gets a smaller font instead
    for ln in re.findall(r"Dialogue: 0,[^,]+,[^,]+,Default,,0,0,0,,(.*)", a):
        plain = re.sub(r"\{[^}]*\}", "", ln)
        assert len(plain) <= 26 and len(plain.split()) <= 3, plain
        fs = re.search(r"\\fs(\d+)", ln)
        size = int(fs.group(1)) if fs else 64
        assert len(plain) * size * 0.66 <= 720 - 100, (plain, size)


def test_one_caption_at_a_time_with_rolling_youtube_captions():
    import re
    from studio.autoclip import cut
    roll = [{"w": "on", "s": 0.0, "e": 0.3}, {"w": "all", "s": 0.3, "e": 0.6}, {"w": "units", "s": 0.6, "e": 1.0},
            {"w": "units", "s": 0.7, "e": 1.0}, {"w": "passports,", "s": 0.9, "e": 1.4}, {"w": "be", "s": 1.4, "e": 1.6}, {"w": "advised.", "s": 1.6, "e": 2.2},
            {"w": "[", "s": 2.2, "e": 2.3}, {"w": "__", "s": 2.3, "e": 2.4}, {"w": "]", "s": 2.4, "e": 2.5}, {"w": "to", "s": 2.5, "e": 2.7}]
    a = cut.ass_for(roll, 0, 4, "hype", 720, 1280)
    ev = [(cut_t(x[0]), cut_t(x[1])) for x in re.findall(r"Dialogue: 0,([^,]+),([^,]+),Default", a)]
    assert all(e1 <= s2 + 1e-6 for (_, e1), (s2, _) in zip(ev, ev[1:])), ev
    assert "__" not in a and "[" not in a.split("[Events]")[1]
    assert a.count("UNITS") <= 3


def cut_t(s: str) -> float:
    h, m, rest = s.split(":")
    return int(h) * 3600 + int(m) * 60 + float(rest)


def test_stream_cam_puts_the_streamer_on_top_for_the_whole_clip():
    from studio.autoclip import reframe
    frames = [{"t": i / 3, "faces": [{"cx": 0.1, "cy": 0.3, "w": 0.04, "h": 0.07, "m": 0}], "col": [1.0] * reframe.BINS} for i in range(30)]
    cam = reframe.stream_cam(frames, 1920, 1080)
    assert cam and abs(cam[0] - 0.1) < 0.01
    plan = {"scenes": [{"layout": "salient", "tracks": {"sal": [[0, 0.5, 0.5, 0.2]]}}, {"layout": "follow", "tracks": {}}]}
    reframe.use_cam(plan, cam)
    assert [s["layout"] for s in plan["scenes"]] == ["camtop", "camtop"] and plan["cam"] == cam
    g = reframe.scene_graph(plan["scenes"][0], 0, 720, 1280, 1920, 1080)
    assert "vstack" in g and "[top0]" in g
    mid = [{"t": i / 3, "faces": [{"cx": 0.5, "cy": 0.5, "w": 0.1, "h": 0.15, "m": 0}], "col": [1.0] * reframe.BINS} for i in range(30)]
    assert reframe.stream_cam(mid, 1920, 1080) is None            # a face in the middle is the content, not a cam
    assert reframe.stream_cam(frames, 1080, 1920) is None          # already vertical


def test_default_length_is_30_to_45_seconds():
    from studio.autoclip import store, craft
    assert store.DEFAULT_SETTINGS["defaults"]["min_seconds"] == 30 and store.DEFAULT_SETTINGS["defaults"]["max_seconds"] == 45
    words = [{"w": w, "s": i * 0.5, "e": i * 0.5 + 0.4} for i, w in enumerate(("this is a sentence. " * 30).split())]
    out = craft.finish([{"start": 0, "end": 12}], words, 30, 45, 200)
    assert out[0]["end"] - out[0]["start"] >= 30
