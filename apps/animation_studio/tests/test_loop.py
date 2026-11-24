"""Resume, readiness, retention, title tests, the coach's change log and comments."""
from __future__ import annotations

import json
import shutil
import subprocess
import threading
from datetime import datetime, timedelta, timezone

import pytest

from studio.autoclip import coach, comments, experiments, pipeline, readiness, retention, store, youtube

ff = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg missing")
SRT = "1\n00:00:21,000 --> 00:00:24,000\nThis is the loud part of the stream\n\n2\n00:00:24,500 --> 00:00:27,000\nand here it gets wild\n"


@pytest.fixture(autouse=True)
def root(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "ROOT", tmp_path / "ac")
    retention._last = 0.0
    comments._last = 0.0


def iso(days=0.0, hours=0.0):
    return (datetime.now(timezone.utc) - timedelta(days=days, hours=hours)).isoformat(timespec="seconds")


def posted_job(n=1, days=5, **over):
    job = pipeline.new_job(pipeline.build_opts({}), {"kind": "upload", "name": "t"})
    clips = [{"n": i + 1, "start": 0, "end": 30, "title": f"Clip title {i + 1}", "text": "money talk", "status": "posted", "youtube_id": f"VID{i + 1}", "channel": "UC1", "posted_at": iso(days),
              "recipe": {"edit": "punchy", "caption": "bounce", "look": "clean", "zoom": True, "stickers": True, "music": "none", "length": "20-35s", "title": "statement"},
              "stats": {"views": 500, "likes": 30, "comments": 2}, **over} for i in range(n)]
    store.update(job["id"], lambda j: j.update(status="done", clips=clips))
    return job["id"]


# ---------- resume ----------
@ff
def test_a_run_again_keeps_the_moments_and_the_clips_already_cut(tmp_path):
    src = tmp_path / "s.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=640x360:r=25:d=60", "-f", "lavfi", "-i", "sine=f=300:d=60", "-filter_complex",
                    "[1:a]volume='if(between(t,20,35),1.0,0.05)':eval=frame[a]", "-map", "0:v", "-map", "[a]", "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", str(src)], check=True)
    job = pipeline.new_job(pipeline.build_opts({"count": 2, "min_seconds": 8, "max_seconds": 15, "hype_only": "false"}), {"kind": "upload", "name": "t"})
    d = store.jdir(job["id"])
    shutil.copy(src, d / "source.mp4")
    (d / "source.srt").write_text(SRT)
    pipeline._cancel[job["id"]] = threading.Event()
    pipeline._run(job["id"])
    j1 = store.load(job["id"])
    assert j1["status"] == "done" and j1["clips"][0]["status"] == "ready"
    stamp = (d / j1["clips"][0]["file"]).stat().st_mtime_ns
    n = len(j1["log"])
    pipeline._cancel[job["id"]] = threading.Event()
    pipeline._run(job["id"])
    j2 = store.load(job["id"])
    texts = [x["text"] for x in j2["log"][n:]]
    assert j2["status"] == "done" and any("Reusing the" in t for t in texts) and any("already cut" in t for t in texts)
    assert (d / j2["clips"][0]["file"]).stat().st_mtime_ns == stamp           # not re-rendered


# ---------- readiness ----------
def test_readiness_reports_rows_and_never_raises(monkeypatch):
    r = readiness.run()
    ids = {x["id"] for x in r["rows"]}
    assert {"ffmpeg", "disk", "font", "ai", "ollama", "yt"} <= ids and all(x["status"] in ("ok", "warn", "fail") for x in r["rows"])
    monkeypatch.setattr(readiness, "_ffmpeg", lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    assert any("Could not check" in x["detail"] for x in readiness.run()["rows"])


def test_readiness_flags_a_login_from_before_the_new_permissions(monkeypatch):
    store.save_accounts({"client": {"id": "a", "secret": "b"}, "channels": {"UC1": {"id": "UC1", "title": "Mine", "scopes": "https://www.googleapis.com/auth/youtube.upload", "refresh": "r"}}})
    monkeypatch.setattr(youtube, "token", lambda cid: "tok")
    row = next(x for x in readiness.run()["rows"] if x["id"] == "yt-UC1")
    assert row["status"] == "warn" and "analytics" in row["detail"] and "comments" in row["detail"]


# ---------- retention ----------
def curve(drop):
    return [round(max(0.05, 1 - drop * i / 19), 3) for i in range(20)]


def test_retention_is_fetched_only_for_old_enough_clips_and_flags_old_logins():
    old, young = posted_job(1, days=5), posted_job(1, days=1)
    calls = []

    def rd(ch, vid, since, until):
        calls.append(vid)
        return {"views": 400, "avg_view_sec": 12.0, "avg_view_pct": 55.0, "minutes": 80.0, "curve": curve(0.8)}
    res = retention.refresh(force=True, reader=rd)
    assert res["updated"] == 1 and store.load(old)["clips"][0]["retention"]["avg_view_pct"] == 55.0 and "retention" not in store.load(young)["clips"][0]
    retention._last = 0
    assert retention.refresh(force=True, reader=rd)["updated"] == 0                      # a fresh copy isn't fetched again

    def need(*a):
        raise youtube.NeedsScope("insufficient")
    j = posted_job(1, days=6, channel="UC9")
    assert "UC9" in retention.refresh(force=True, reader=need)["needs_reconnect"]


def test_retention_summary_reads_the_curve_and_shortens_the_lead_in():
    early = [1.0, 0.8, 0.6, 0.5] + [0.4] * 16
    obs = [{"retention": {"curve": early, "avg_view_pct": 40.0}} for _ in range(4)]
    s = retention.summary(obs)
    assert s["n"] == 4 and s["early_hold"] < 0.6 and any("closer to the peak" in t for t in s["tips"])
    assert retention.lead_in(s) == 1 and retention.lead_in(retention.summary(obs[:2])) == 2          # not enough evidence yet
    good = retention.summary([{"retention": {"curve": curve(0.2), "avg_view_pct": 85.0}}] * 4)
    assert retention.lead_in(good) == 2 and any("longer clips" in t for t in good["tips"])


def test_watch_time_changes_the_reward():
    obs = [{"retention": {"avg_view_pct": 90.0}, "raw": 5.0}, {"retention": {"avg_view_pct": 20.0}, "raw": 5.0}, {"raw": 5.0}]
    coach._add_watch_time(obs)
    assert obs[0]["raw"] > obs[2]["raw"] > obs[1]["raw"]


# ---------- title tests ----------
def test_evaluate_needs_clear_evidence():
    assert experiments.evaluate(100, 24, 100, 24)["winner"] is None
    assert experiments.evaluate(300, 24, 520, 24)["winner"] == "B"
    assert experiments.evaluate(500, 24, 250, 24)["winner"] == "A"
    r = experiments.evaluate(20, 24, 40, 24)
    assert r["winner"] is None and "Not enough views" in r["note"]
    assert experiments.evaluate(1000, 24, 1100, 24)["winner"] is None                            # +10%: clear but under the 20% bar


def armed(days=0.0, **var):
    jid = posted_job(1, days=days, variants={"title_b": "Why this money trick works", "cover_b": None, **var})
    store.update(jid, lambda j: j["clips"][0].update(cover=None))
    t0 = datetime.now(timezone.utc) - timedelta(hours=30)
    assert experiments.begin(jid, 1, now=t0) and not experiments.begin(jid, 1)
    return jid, t0


def run_test(views_a, views_b, hours=24):
    jid, t0 = armed()
    sets = []
    setter = {"title": lambda ch, vid, t: sets.append(t), "thumb": lambda *a: None}
    views = iter([views_a, views_a + views_b])
    assert experiments.tick(now=t0 + timedelta(hours=hours + 1), viewer=lambda ch, v: next(views), setter=setter) == 1
    e = store.load(jid)["clips"][0]["exp"]
    assert e["phase"] == "B" and sets == ["Why this money trick works"]
    assert experiments.tick(now=t0 + timedelta(hours=hours + 1), viewer=lambda *a: 0, setter=setter) == 0                    # B's window isn't over
    assert experiments.tick(now=t0 + timedelta(hours=2 * hours + 2), viewer=lambda ch, v: next(views), setter=setter) == 1
    return jid, sets


def test_a_clearly_better_b_title_is_kept():
    jid, sets = run_test(300, 520)
    e = store.load(jid)["clips"][0]["exp"]
    assert e["phase"] == "done" and e["result"]["winner"] == "B" and e["result"]["kept"] == "B" and sets == ["Why this money trick works"]


def test_otherwise_the_original_title_is_put_back():
    jid, sets = run_test(300, 310)
    e = store.load(jid)["clips"][0]["exp"]
    assert e["result"]["kept"] == "A" and sets == ["Why this money trick works", "Clip title 1"]
    assert experiments.summary()["n"] == 1 and experiments.summary()["wins_b"] == 0


def test_summary_turns_wins_into_a_tip():
    jid, _ = run_test(300, 520)
    s = experiments.summary()
    assert s["wins_b"] == 1 and s["tips"] and "title beat the original" in s["tips"][0]


# ---------- coach change log ----------
def test_apply_best_is_logged_and_can_be_undone(monkeypatch):
    monkeypatch.setattr(coach, "best_choices", lambda min_n=3: {"edit": "punchy", "look": "film"})
    before = store.settings()["defaults"]["edit"]
    coach.apply_best()
    assert store.settings()["defaults"]["edit"] == "punchy"
    ch = coach.changes()[0]
    assert ch["kind"] == "defaults" and ch["diff"]["edit"] == {"from": before, "to": "punchy"}
    store.clean_settings({"defaults": {"look": "mono"}})                                    # the user changed one of them since
    out = coach.undo(ch["id"])
    d = store.settings()["defaults"]
    assert d["edit"] == before and d["look"] == "mono" and out["restored"].get("look") is None
    with pytest.raises(ValueError):
        coach.undo(ch["id"])


def test_clip_draws_log_only_differences():
    coach.log_draw("c1", 2, {"caption": "bounce", "look": "clean", "zoom": True}, {"caption": "hype", "look": "clean", "zoom": True})
    row = coach.changes()[0]
    assert row["kind"] == "clip" and row["diff"] == {"caption": {"from": "bounce", "to": "hype"}}
    n = len(coach.changes())
    coach.log_draw("c1", 3, {"caption": "bounce"}, {"caption": "bounce"})
    assert len(coach.changes()) == n
    coach.set_config({"mode": "suggest"})                                                    # saving config keeps the log
    assert len(coach.changes()) == n


# ---------- comments ----------
def test_spam_and_requests_are_told_apart():
    assert comments.classify("check out my channel for free robux")["why"] == "asks for subs or views"
    assert comments.classify("Visit https://bad.example.com/win now")["spam"]
    assert comments.classify("WHATSAPP me on 98765 43210 for deals")["spam"]
    assert comments.classify("THIS IS THE BEST VIDEO EVER MADE IN HISTORY")["why"] == "shouting"
    assert comments.classify("nice", dup=4)["spam"]
    assert not comments.classify("Great clip, loved the ending!")["spam"]
    assert comments.classify("please make a video about the new GTA map")["request"] == "the new gta map" or "gta map" in comments.classify("please make a video about the new GTA map")["request"]
    assert comments.classify("Part 2 please", )["request"].startswith("part")
    assert comments.classify("hi", "UCme", {"UCme"})["spam"] is False


def fake_reader(ch, vid, limit=50):
    return [{"id": "c1", "author": "A", "author_channel": "UCa", "text": "Please make a video on the new map", "likes": 9, "at": iso(1), "replies": 0},
            {"id": "c2", "author": "B", "author_channel": "UCb", "text": "sub4sub check my channel", "likes": 0, "at": iso(1), "replies": 0},
            {"id": "c3", "author": "C", "author_channel": "UCc", "text": "How do you make the captions?", "likes": 2, "at": iso(1), "replies": 0},
            {"id": "c4", "author": "D", "author_channel": "UCd", "text": "Make a video about the new map pls", "likes": 4, "at": iso(1), "replies": 0},
            {"id": "c5", "author": "Me", "author_channel": "UC1", "text": "thanks all", "likes": 0, "at": iso(1), "replies": 0}]


def test_sync_flags_spam_drafts_replies_and_mines_ideas():
    posted_job(1, days=2)
    store.save_accounts({"client": {"id": "a", "secret": "b"}, "channels": {"UC1": {"id": "UC1", "title": "Mine", "refresh": "r"}}})
    res = comments.sync(fake_reader)
    assert res["new"] == 4 and res["drafted"] == 3                                       # my own comment skipped, spam gets no draft
    v = comments.view()
    by = {i["id"]: i for i in v["items"]}
    assert by["c2"]["status"] == "spam" and by["c2"]["draft"] is None and by["c1"]["draft"]["by"] == "template" and "idea" in by["c1"]["draft"]["text"].lower()
    assert v["counts"]["spam"] == 1 and v["ideas"] and v["ideas"][0]["count"] == 2 and "map" in v["ideas"][0]["idea"]
    assert comments.sync(fake_reader)["new"] == 0                                        # nothing is added twice


def test_a_reply_is_only_sent_when_posted_and_needs_text():
    posted_job(1, days=2)
    store.save_accounts({"client": {"id": "a", "secret": "b"}, "channels": {"UC1": {"id": "UC1", "title": "Mine", "refresh": "r"}}})
    comments.sync(fake_reader)
    sent = []
    with pytest.raises(ValueError):
        comments.post_reply("c1", "  ", poster=lambda *a: sent.append(a) or "x")
    assert sent == []
    it = comments.post_reply("c1", "Thanks, coming soon!", poster=lambda ch, cid, t: sent.append((ch, cid, t)) or "x")
    assert sent == [("UC1", "c1", "Thanks, coming soon!")] and it["status"] == "answered"


# ---------- HTTP ----------
def client():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from studio.autoclip.routes import router
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_routes(monkeypatch):
    c = client()
    assert c.get("/api/autoclip/readiness").json()["rows"]
    assert c.get("/api/autoclip/experiments").json()["n"] == 0
    r = c.put("/api/autoclip/settings", json={"experiments": {"enabled": True, "window_hours": 12}})
    assert r.status_code == 200 and r.json()["settings"]["experiments"] == {"enabled": True, "window_hours": 12, "thumbnails": False}
    posted_job(1, days=2)
    store.save_accounts({"client": {"id": "a", "secret": "b"}, "channels": {"UC1": {"id": "UC1", "title": "Mine", "refresh": "r"}}})
    monkeypatch.setattr(youtube, "comments", fake_reader)
    r = c.post("/api/autoclip/comments/sync").json()
    assert r["sync"]["new"] == 4 and r["ideas"]
    assert c.post("/api/autoclip/comments/c2/release").json()["counts"].get("spam") is None
    assert c.post("/api/autoclip/comments/c1/reply", json={"text": ""}).status_code == 400
    monkeypatch.setattr(youtube, "reply", lambda ch, pid, t: "x")
    assert c.post("/api/autoclip/comments/c1/reply", json={"text": "Thanks!"}).json()["counts"]["answered"] == 1
    monkeypatch.setattr(youtube, "hold_comment", lambda ch, cid: (_ for _ in ()).throw(youtube.NeedsScope("x")))
    assert c.post("/api/autoclip/comments/c3/hold").status_code == 403
    assert c.post("/api/autoclip/comments/c3/dismiss").json()["counts"]["dismissed"] == 1


def test_undoing_a_clip_change_re_renders_it(monkeypatch, tmp_path):
    from studio.autoclip import routes
    c = client()
    jid = posted_job(1, days=0, status="ready", youtube_id=None)
    coach.log_draw(jid, 1, {"caption": "bounce", "look": "clean"}, {"caption": "hype", "look": "film"})
    got = {}
    monkeypatch.setattr(routes, "_reedit", lambda j, n, b: got.update(j=j, n=n, b=b) or {"ok": True})
    ch = coach.changes()[0]
    r = c.post(f"/api/autoclip/coach/changes/{ch['id']}/undo")
    assert r.status_code == 200 and got["b"] == {"caption": "bounce", "look": "clean"} and coach.changes()[0]["undone"] is True
    assert c.post(f"/api/autoclip/coach/changes/{ch['id']}/undo").status_code == 409


def test_variants_are_prepared_only_when_tests_are_on(monkeypatch, tmp_path):
    from studio.autoclip import cut, pick
    c = {"n": 1, "start": 0, "end": 30, "title": "Original title", "text": "some words"}
    assert experiments.prepare({}, tmp_path, c, tmp_path / "v.mp4") is None                                   # off by default
    store.clean_settings({"experiments": {"enabled": True, "thumbnails": True}})
    monkeypatch.setattr(pick, "alt_title", lambda s, t, ti, log=None: "Why this works")
    seen = {}
    monkeypatch.setattr(cut, "cover", lambda v, o, title, at=1.2, style="a": seen.update(style=style, title=title, at=at) or True)
    v = experiments.prepare({}, tmp_path, c, tmp_path / "v.mp4")
    assert v == {"title_b": "Why this works", "cover_b": "clips/clip-1-cover-b.jpg"} and seen == {"style": "b", "title": "Why this works", "at": 15.0}
    monkeypatch.setattr(pick, "alt_title", lambda *a, **k: None)
    store.clean_settings({"experiments": {"thumbnails": False}})
    assert experiments.prepare({}, tmp_path, c, tmp_path / "v.mp4") is None                                    # no AI title and no cover test: nothing to test


@ff
def test_cover_variant_b_renders(tmp_path):
    from studio.autoclip import cut
    src = tmp_path / "s.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=640x360:r=25:d=4", "-c:v", "libx264", str(src)], check=True)
    assert cut.cover(str(src), str(tmp_path / "a.jpg"), "Hello world", 1.0, "a") and cut.cover(str(src), str(tmp_path / "b.jpg"), "Hello world", 1.0, "b")
    assert (tmp_path / "a.jpg").read_bytes() != (tmp_path / "b.jpg").read_bytes()
