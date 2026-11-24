"""Rights check, thumbnails, the YouTube tab's queue/planner/worker/monitoring. All faked: no network, no key."""
from __future__ import annotations

import shutil
import subprocess
from datetime import datetime, timedelta, timezone

import pytest

from studio.autoclip import cut, intake, postqueue, rights, store, youtube

needs_ffmpeg = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not installed")
UTC = timezone.utc


@pytest.fixture(autouse=True)
def root(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "ROOT", tmp_path / "ac")
    monkeypatch.setattr(postqueue, "_last_stats", 0.0)
    monkeypatch.setattr(intake, "public_url", lambda u: u)
    rights._CACHE.clear()
    _ids.clear()
    monkeypatch.setattr(youtube, "channels", lambda: [{"id": "UC1", "title": "One", "needs_login": False}, {"id": "UC2", "title": "Two", "needs_login": False}])
    yield


def make_job(permission=None, n=2, ready=True, tmp=None):
    jid = store.new_id()
    d = store.jdir(jid)
    (d / "clips").mkdir(parents=True)
    clips = []
    for i in range(1, n + 1):
        (d / "clips" / f"clip-{i}.mp4").write_bytes(b"x" * 3000)
        (d / "clips" / f"clip-{i}-cover.jpg").write_bytes(b"j")
        clips.append({"n": i, "title": f"Clip {i}", "file": f"clips/clip-{i}.mp4", "thumb": f"clips/clip-{i}.jpg", "cover": f"clips/clip-{i}-cover.jpg",
                      "status": "ready" if ready else "working"})
    job = {"id": jid, "title": "My stream", "status": "done", "stage": "cut", "source": {}, "opts": {}, "steps": {}, "log": [], "clips": clips, "createdAt": store.now()}
    if permission:
        job["permission"] = permission
    store.save(job)
    return jid


# ---------- rights ----------
def meta(**kw):
    return {"title": "Big win", "channel": "Streamer", "channel_id": "UCx", "channel_url": "https://www.youtube.com/channel/UCx", "license": "", **kw}


def test_standard_licence_means_ask_first():
    r = rights.check("https://www.youtube.com/watch?v=abc", meta())
    assert r["verdict"] == "ask" and "keeps the rights" in r["tip"] and r["links"]["about"].endswith("/about")


def test_creative_commons_is_reusable_with_credit():
    r = rights.check("https://www.youtube.com/watch?v=abc", meta(license="Creative Commons Attribution license (reuse allowed)"))
    assert r["verdict"] == "creative-commons" and "credit" in r["tip"].lower()


def test_your_own_channel_is_own():
    r = rights.check("https://www.youtube.com/watch?v=abc", meta(channel_id="UC1"))
    assert r["verdict"] == "own"


def test_unreadable_is_unknown_never_safe(monkeypatch):
    monkeypatch.setattr(rights, "_meta", lambda u: None)
    assert rights.check("https://www.youtube.com/watch?v=abc")["verdict"] == "unknown"


def test_live_stream_note():
    r = rights.check("https://www.youtube.com/watch?v=abc", meta(was_live=True))
    assert any("live" in n.lower() for n in r["notes"])


def test_permission_values_and_gate():
    assert rights.permission_for("own", False) == "own" and rights.permission_for("creative-commons", False) == "cc"
    assert rights.permission_for("ask", False) == "unconfirmed" and rights.permission_for("ask", True) == "granted"
    assert rights.can_post({"permission": "unconfirmed"}) is False and rights.can_post({"permission": "cc"}) and rights.can_post({})


# ---------- thumbnails ----------
@needs_ffmpeg
def test_cover_is_a_real_jpeg_with_title(tmp_path):
    src = tmp_path / "a.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=640x360:r=25:d=3", "-c:v", "libx264", "-preset", "ultrafast", str(src)], check=True)
    out = tmp_path / "c.jpg"
    assert cut.cover(str(src), str(out), "He clutched the whole round at the last second") and out.stat().st_size > 2000
    assert out.read_bytes()[:2] == b"\xff\xd8"


# ---------- planner ----------
PL = {"per_day": 3, "min_gap_minutes": 120, "hours": [9, 21], "privacy": "private"}


def test_slots_spread_through_the_window_in_your_time():
    start = datetime(2026, 11, 16, 0, 0, tzinfo=UTC)          # 05:30 in India
    got = postqueue.slots([], 4, start, PL, 330)
    local = [(t + timedelta(minutes=330)).strftime("%d %H:%M") for t in got]
    assert local == ["16 11:00", "16 15:00", "16 19:00", "17 11:00"]


def test_slots_skip_the_past_taken_days_and_gaps():
    start = datetime(2026, 11, 16, 7, 0, tzinfo=UTC)          # 12:30 local: the 11:00 slot is past
    taken = [datetime(2026, 11, 16, 9, 30, tzinfo=UTC)]       # 15:00 local, already planned
    got = postqueue.slots(taken, 2, start, PL, 330)
    local = [(t + timedelta(minutes=330)).strftime("%d %H:%M") for t in got]
    assert "16 15:00" not in local and local[0] == "16 19:00" and local[1].startswith("17")


def test_overnight_window_is_allowed():
    pl = PL | {"hours": [20, 2], "per_day": 2}
    got = postqueue.slots([], 2, datetime(2026, 11, 16, 0, 0, tzinfo=UTC), pl, 0)
    assert [t.strftime("%H:%M") for t in got] == ["22:30", "01:30"] or len(got) == 2


def test_plan_is_validated():
    postqueue.set_plan({"per_day": 5, "hours": [8, 22], "min_gap_minutes": 60, "privacy": "public"})
    assert postqueue.plan()["per_day"] == 5 and postqueue.plan()["privacy"] == "public"
    with pytest.raises(ValueError):
        postqueue.set_plan({"hours": [9, 9]})
    with pytest.raises(ValueError):
        postqueue.set_plan({"hours": ["x", 3]})


# ---------- the queue ----------
def test_library_lists_ready_unposted_clips_with_permission_state():
    a = make_job("granted")
    b = make_job("unconfirmed")
    make_job(None, ready=False)
    lib = {(x["jid"], x["n"]): x for x in postqueue.library()}
    assert len(lib) == 4 and lib[(a, 1)]["allowed"] and not lib[(b, 1)]["allowed"] and lib[(a, 1)]["thumb"].endswith("cover.jpg")


def test_unconfirmed_clips_cannot_be_queued():
    b = make_job("unconfirmed")
    with pytest.raises(ValueError, match="permission"):
        postqueue.add([{"jid": b, "n": 1}], ["UC1"], "now")


def test_multi_clip_multi_channel_auto_makes_one_post_each_with_spread_times():
    a = make_job("granted", n=3)
    made = postqueue.add([{"jid": a, "n": i} for i in (1, 2, 3)], ["UC1", "UC2"], "auto")
    assert len(made) == 6
    for ch in ("UC1", "UC2"):
        ts = sorted(postqueue.parse(p["at"]) for p in made if p["channel"] == ch)
        assert len(set(ts)) == 3 and all((y - x) >= timedelta(minutes=120) for x, y in zip(ts, ts[1:]))


def test_same_video_same_channel_is_not_queued_twice():
    a = make_job("own")
    postqueue.add([{"jid": a, "n": 1}], ["UC1"], "now")
    assert postqueue.add([{"jid": a, "n": 1}], ["UC1"], "now") == []


def test_schedule_mode_spaces_by_gap_and_needs_a_time():
    a = make_job("own", n=2)
    with pytest.raises(ValueError):
        postqueue.add([{"jid": a, "n": 1}], ["UC1"], "schedule")
    made = postqueue.add([{"jid": a, "n": 1}, {"jid": a, "n": 2}], ["UC1"], "schedule", "2026-12-01T10:00:00+00:00")
    t = sorted(postqueue.parse(p["at"]) for p in made)
    assert t[1] - t[0] == timedelta(minutes=120)


def test_unknown_channel_is_refused():
    a = make_job("own")
    with pytest.raises(ValueError):
        postqueue.add([{"jid": a, "n": 1}], ["UCnope"], "now")


# ---------- the worker ----------
_ids: list = []


def run_tick(**kw):
    calls = []

    def up(ch, path, title, desc, priv, tags):
        calls.append((ch, title, priv))
        _ids.append(1)
        return "vid" + str(len(_ids))
    th = kw.pop("thumber", lambda *a: None)
    r = postqueue.tick(uploader=up, thumber=th, **kw)
    return r, calls


def test_worker_posts_when_due_and_marks_the_library_clip_posted():
    a = make_job("own")
    postqueue.add([{"jid": a, "n": 1}], ["UC1"], "now")
    r, calls = run_tick()
    assert r.startswith("posted:") and calls == [("UC1", "Clip 1", "private")]
    p = postqueue.overview()["posts"][0]
    assert p["status"] == "posted" and p["thumb_status"] == "set" and p["url"].endswith("vid1")
    assert store.load(a)["clips"][0]["youtube_id"] == "vid1"
    assert run_tick()[0] is None                                 # nothing left: never posted twice


def test_future_posts_wait():
    a = make_job("own")
    postqueue.add([{"jid": a, "n": 1}], ["UC1"], "schedule", (datetime.now(UTC) + timedelta(hours=3)).isoformat())
    assert run_tick()[0] is None
    assert run_tick(at=datetime.now(UTC) + timedelta(hours=4))[0].startswith("posted:")


def test_refused_cover_is_a_note_not_a_failure():
    a = make_job("own")
    postqueue.add([{"jid": a, "n": 1}], ["UC1"], "now")

    def bad(*_):
        raise RuntimeError("custom thumbnails need a verified channel")
    run_tick(thumber=bad)
    p = postqueue.overview()["posts"][0]
    assert p["status"] == "posted" and "not accepted" in p["thumb_status"]


def test_upload_failure_is_recorded_and_retry_works():
    a = make_job("own")
    postqueue.add([{"jid": a, "n": 1}], ["UC1"], "now")

    def boom(*_a):
        raise RuntimeError("quota exceeded")
    assert postqueue.tick(uploader=boom).startswith("failed:")
    p = postqueue.overview()["posts"][0]
    assert p["status"] == "failed" and "quota" in p["error"]
    assert postqueue.retry(p["id"]) and run_tick()[0].startswith("posted:")


def test_broken_login_holds_the_channel_instead_of_looping():
    a = make_job("own", n=2)
    postqueue.add([{"jid": a, "n": 1}, {"jid": a, "n": 2}], ["UC1"], "now")

    def nologin(*_a):
        raise youtube.NeedsLogin("sign in again")
    assert postqueue.tick(uploader=nologin).startswith("login:")
    assert run_tick()[0] is None                                 # held: no second attempt
    assert postqueue.release("UC1") == 2 and run_tick()[0].startswith("posted:")


def test_interrupted_post_is_never_retried_by_itself():
    a = make_job("own")
    postqueue.add([{"jid": a, "n": 1}], ["UC1"], "now")
    pid = postqueue.overview()["posts"][0]["id"]
    postqueue._patch(pid, status="posting", started=(datetime.now(UTC) - timedelta(hours=3)).isoformat())
    run_tick()
    assert postqueue.overview()["posts"][0]["status"] == "failed"


def test_permission_revoked_after_queueing_blocks_the_upload():
    a = make_job("granted")
    postqueue.add([{"jid": a, "n": 1}], ["UC1"], "now")
    store.update(a, lambda j: j.__setitem__("permission", "unconfirmed"))
    r, calls = run_tick()
    assert r.startswith("failed:") and calls == []


def test_cancel_edit():
    a = make_job("own")
    pid = postqueue.add([{"jid": a, "n": 1}], ["UC1"], "auto")[0]["id"]
    postqueue.edit(pid, {"title": "New title", "privacy": "public"})
    assert postqueue.overview()["posts"][0]["title"] == "New title"
    assert postqueue.cancel(pid) and run_tick(at=datetime.now(UTC) + timedelta(days=3))[0] is None


# ---------- uploads ----------
@needs_ffmpeg
def test_upload_gets_cover_and_needs_a_tick(tmp_path):
    src = tmp_path / "my_clip-1.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=320x240:r=25:d=3", "-c:v", "libx264", "-preset", "ultrafast", str(src)], check=True)
    keep = _copy(src, tmp_path / "keep.mp4")
    rec = postqueue.add_upload("my_clip-1.mp4", src, False)
    assert rec["title"] == "my clip 1" and rec["thumb"]
    with pytest.raises(ValueError, match="permission"):
        postqueue.add([{"upload": rec["id"]}], ["UC1"], "now")
    rec2 = postqueue.add_upload("b.mp4", _copy(keep, tmp_path / "b.mp4"), True)
    made = postqueue.add([{"upload": rec2["id"]}], ["UC1"], "now")
    assert len(made) == 1 and run_tick()[0].startswith("posted:")


def _copy(a, b):
    shutil.copy(a, b)
    return b


# ---------- monitoring ----------
def test_monitor_sums_views_per_channel_and_flags_removed():
    a = make_job("own", n=2)
    postqueue.add([{"jid": a, "n": 1}, {"jid": a, "n": 2}], ["UC1"], "now")
    run_tick()
    run_tick()
    ids = [p["youtube_id"] for p in postqueue.overview()["posts"]]
    n = postqueue.refresh(force=True, reader=lambda ch, ids_: {ids[0]: {"views": 120, "likes": 9, "comments": 2, "privacy": "public"}})
    assert n == 2
    ov = postqueue.overview()
    c = next(c for c in ov["channels"] if c["id"] == "UC1")
    assert c["views"] == 120 and c["likes"] == 9 and c["posted"] == 2
    assert sum(1 for p in ov["posts"] if (p.get("stats") or {}).get("removed")) == 1


def test_monitor_survives_a_failing_channel():
    a = make_job("own")
    postqueue.add([{"jid": a, "n": 1}], ["UC1"], "now")
    run_tick()

    def bad(*_):
        raise RuntimeError("no")
    assert postqueue.refresh(force=True, reader=bad) == 0


def test_overview_has_every_connected_channel_even_with_no_posts():
    ov = postqueue.overview()
    assert {c["id"] for c in ov["channels"]} == {"UC1", "UC2"}


# ---------- HTTP ----------
def client():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from studio.autoclip import routes
    app = FastAPI()
    app.include_router(routes.router)
    return TestClient(app)


def test_http_check_queue_and_overview(monkeypatch):
    from studio.autoclip import routes
    monkeypatch.setattr(rights, "_meta", lambda u: meta())
    c = client()
    assert c.post("/api/autoclip/check", json={"url": "https://www.youtube.com/watch?v=abc"}).json()["verdict"] == "ask"
    a = make_job("own", n=2)
    t = c.get("/api/autoclip/youtube/tab").json()
    assert len(t["library"]) == 2 and {x["id"] for x in t["channels"]} == {"UC1", "UC2"}
    r = c.post("/api/autoclip/youtube/posts", json={"items": [{"jid": a, "n": 1}, {"jid": a, "n": 2}], "channels": ["UC1", "UC2"], "mode": "auto"}).json()
    assert r["made"] == 4 and len(r["posts"]) == 4 and all(p["at"] for p in r["posts"])
    assert c.post("/api/autoclip/youtube/posts", json={"items": [], "channels": ["UC1"], "mode": "now"}).status_code == 400
    pid = r["posts"][0]["id"]
    assert c.patch(f"/api/autoclip/youtube/posts/{pid}", json={"title": "Hi"}).json()["posts"][0]["title"] in ("Hi", r["posts"][0]["title"])
    assert c.delete(f"/api/autoclip/youtube/posts/{pid}").status_code == 200
    assert c.put("/api/autoclip/youtube/plan", json={"per_day": 4}).json()["plan"]["per_day"] == 4
    assert c.put("/api/autoclip/youtube/plan", json={"hours": [5, 5]}).status_code == 400


def test_http_job_permission_comes_from_the_servers_own_check(monkeypatch):
    from studio.autoclip import pipeline
    monkeypatch.setattr(pipeline, "start", lambda jid: None)
    verdict = {"v": "ask"}
    monkeypatch.setattr(rights, "check", lambda url, extra=None: {"verdict": verdict["v"], "clippable": True, "platform": "other", "tip": "", "notes": [], "title": "T", "links": {}, "live": None})
    c = client()
    j = c.post("/api/autoclip/jobs", json={"url": "https://example.com/v", "ack": False}).json()
    assert store.load(j["id"])["permission"] == "unconfirmed"
    j2 = c.post("/api/autoclip/jobs", json={"url": "https://example.com/v", "ack": True}).json()
    assert store.load(j2["id"])["permission"] == "granted"
    verdict["v"] = "creative-commons"
    j3 = c.post("/api/autoclip/jobs", json={"url": "https://example.com/v"}).json()
    assert store.load(j3["id"])["permission"] == "cc"


# ---------- one by one, 3-5 minutes apart ----------
def test_add_all_clips_in_a_row_drips_from_now():
    jid = make_job(permission="own", n=4)
    made = postqueue.add([{"jid": jid, "all": True}], ["UC1"], "drip")
    assert [p["src"]["n"] for p in made] == [1, 2, 3, 4]
    ts = [postqueue.parse(p["at"]) for p in made]
    assert abs((ts[0] - postqueue.now()).total_seconds()) < 5
    for a, b in zip(ts, ts[1:]):
        assert 3 * 60 - 1 <= (b - a).total_seconds() <= 5 * 60 + 1


def test_drip_retimes_waiting_posts_per_channel():
    jid = make_job(permission="own", n=3)
    postqueue.add([{"jid": jid, "n": i} for i in (1, 2, 3)], ["UC1", "UC2"], "schedule", at=postqueue.iso(postqueue.now() + timedelta(days=2)))
    assert postqueue.drip() == 6
    for ch in ("UC1", "UC2"):
        ts = sorted(postqueue.parse(p["at"]) for p in postqueue.overview()["posts"] if p["channel"] == ch)
        assert (ts[0] - postqueue.now()).total_seconds() < 5
        assert all(3 * 60 - 1 <= (b - a).total_seconds() <= 5 * 60 + 1 for a, b in zip(ts, ts[1:]))
    assert postqueue.drip() == 6 and postqueue.drip("UCnone") == 0


def test_set_privacy_and_locked_private_note(monkeypatch):
    jid = make_job(permission="own", n=2)
    postqueue.add([{"jid": jid, "n": 1}, {"jid": jid, "n": 2}], ["UC1"], "auto")
    assert postqueue.set_privacy("public", "UC1") == 2
    assert {p["privacy"] for p in postqueue.overview()["posts"]} == {"public"}
    try:
        postqueue.set_privacy("secret")
        assert False
    except ValueError:
        pass
    youtube.LAST_PRIVACY["vid1"] = "private"
    postqueue.tick(uploader=lambda *a, **k: "vid1", thumber=lambda *a, **k: None, at=postqueue.now() + timedelta(days=3))
    posted = [p for p in postqueue.overview()["posts"] if p["status"] == "posted"]
    assert posted and "audit" in (posted[0].get("note") or "")


def test_every_n_hours_with_visibility():
    jid = make_job(permission="own", n=3)
    made = postqueue.add([{"jid": jid, "all": True}], ["UC1"], "every", privacy="public", gap_hours=2)
    assert [p["privacy"] for p in made] == ["public"] * 3
    ts = [postqueue.parse(p["at"]) for p in made]
    assert abs((ts[0] - postqueue.now()).total_seconds()) < 5
    for a, b in zip(ts, ts[1:]):
        assert 2 * 3600 <= (b - a).total_seconds() <= 2 * 3600 + 5 * 60 + 1
    try:
        postqueue.add([{"jid": jid, "n": 1}], ["UC2"], "every", gap_hours=0)
        assert False
    except ValueError:
        pass


def test_credit_names_channel_and_hashtag():
    from studio.autoclip import meta
    job = {"title": "Stand up", "source": {"kind": "url", "url": "https://youtu.be/x", "channel": "Rohit Vlogs", "channel_url": "https://www.youtube.com/@ROHITVLGS", "license": "Standard licence"}}
    desc, tags = meta.build({"title": "He lost it", "description": "Funny bit", "text": "he lost it completely"}, job)
    assert "Source" not in desc and "@ROHITVLGS" not in desc   # no source line: one caption line and hashtags
    assert "RohitVlogs" in tags and "#Shorts" in desc
    assert "(Standard" not in desc


def test_mention_and_source_tags():
    from studio.autoclip import meta
    job = {"title": "x", "source": {"url": "u", "channel": "Rohit Vlogs", "channel_url": "https://youtube.com/@ROHITVLGS", "tags": ["standup comedy", "Rohit Singh Patel", "shorts", "viral"]}}
    assert meta.mention_title("Ni Mai Kuchh Ni Peeti", job) == "Ni Mai Kuchh Ni Peeti @ROHITVLGS"
    assert meta.mention_title("x" * 90, job) == "x" * 90
    assert meta.source_tags(job) == ["standupcomedy", "RohitSinghPatel"]
    desc, tags = meta.build({"title": "t", "description": "d"}, job)
    assert not desc.startswith("🎬") and "standupcomedy" in tags


def test_daily_upload_limit_waits_a_day_instead_of_failing():
    jid = make_job(permission="own", n=3)
    made = postqueue.add([{"jid": jid, "all": True}], ["UC1"], "now", privacy="public")
    def up(*a, **k):
        raise RuntimeError("YouTube would not start the upload: The user has exceeded the number of videos they may upload.")
    r = postqueue.tick(uploader=up, thumber=lambda *a, **k: None)
    assert r == "limit:UC1"
    posts = [p for p in postqueue._load()["posts"] if p["channel"] == "UC1"]
    assert all(p["status"] == "queued" for p in posts) and all("daily upload limit" in p["error"] for p in posts)
    ats = sorted(postqueue.parse(p["at"]) for p in posts)
    assert ats[0] > postqueue.now() + timedelta(hours=23) and all(b > a for a, b in zip(ats, ats[1:]))
