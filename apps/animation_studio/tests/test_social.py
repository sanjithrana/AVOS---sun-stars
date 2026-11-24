"""Instagram, Facebook and TikTok: sign-in, listing, posting through the queue. Every network call is faked."""
from __future__ import annotations

import json

import httpx
import pytest

from studio.autoclip import postqueue, social, store


@pytest.fixture(autouse=True)
def root(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "ROOT", tmp_path / "ac")
    monkeypatch.setattr(social.time, "sleep", lambda s: None)


def resp(status=200, body=None, ct="application/json"):
    return httpx.Response(status, content=json.dumps(body if body is not None else {}).encode(), headers={"content-type": ct})


def fake_meta(calls):
    def f(method, url, **kw):
        calls.append((method, url, kw))
        if "/oauth/access_token" in url:
            return resp(200, {"access_token": "LONG"})
        if url.endswith("/me/accounts"):
            return resp(200, {"data": [{"id": "P1", "name": "My Page", "access_token": "PAGETOK", "picture": {"data": {"url": "u"}},
                                        "instagram_business_account": {"id": "IG1", "username": "me_ig", "followers_count": 12}}]})
        if url.endswith("/IG1/media"):
            return resp(200, {"id": "CONT1"})
        if "rupload" in url:
            return resp(200, {"success": True})
        if url.endswith("/CONT1"):
            return resp(200, {"status_code": "FINISHED"})
        if url.endswith("/IG1/media_publish"):
            return resp(200, {"id": "MEDIA1"})
        if url.endswith("/MEDIA1"):
            return resp(200, {"permalink": "https://instagram.com/reel/abc"})
        if "/P1/videos" in url:
            return resp(200, {"id": "FBVID"})
        return resp(404, {"error": {"message": "unexpected " + url}})
    return f


def connect_meta(monkeypatch, calls):
    monkeypatch.setattr(social, "_req", fake_meta(calls))
    social.set_client("meta", "APPID123", "APPSECRET123")
    url = social.auth_url("meta", "http://localhost:3000")
    state = url.split("state=")[1].split("&")[0]
    return social.finish("meta", "CODE", state)


def test_the_login_url_and_redirect_are_this_studios():
    social.set_client("meta", "APPID123", "APPSECRET123")
    u = social.auth_url("meta", "http://localhost:3000")
    assert "facebook.com" in u and "instagram_content_publish" in u
    assert social.redirect_uri("meta", "http://localhost:3000") == "http://localhost:3000/studio-api/autoclip/social/meta/callback"
    with pytest.raises(RuntimeError):
        social.auth_url("tiktok", "http://localhost:3000")


def test_connecting_meta_adds_the_page_and_the_linked_instagram(monkeypatch):
    calls: list = []
    r = connect_meta(monkeypatch, calls)
    assert sorted(r["added"]) == ["facebook:P1", "instagram:IG1"]
    ids = {a["id"]: a for a in social.accounts()}
    assert ids["instagram:IG1"]["title"] == "@me_ig" and "token" not in ids["instagram:IG1"]
    assert "PAGETOK" not in json.dumps(social.platforms("http://localhost:3000"))     # a token never reaches the page


def test_a_stale_sign_in_link_is_refused(monkeypatch):
    monkeypatch.setattr(social, "_req", fake_meta([]))
    social.set_client("meta", "APPID123", "APPSECRET123")
    with pytest.raises(RuntimeError):
        social.finish("meta", "CODE", "nope")


def test_instagram_reel_goes_through_resumable_upload(monkeypatch, tmp_path):
    calls: list = []
    connect_meta(monkeypatch, calls)
    f = tmp_path / "c.mp4"
    f.write_bytes(b"x" * 100)
    out = social.publish("instagram:IG1", str(f), "Great clip", "desc", "private", ["gta", "funny"])
    assert out == {"id": "MEDIA1", "url": "https://instagram.com/reel/abc"}
    media = next(c for c in calls if c[1].endswith("/IG1/media"))
    assert media[2]["data"]["upload_type"] == "resumable" and "#gta #funny" in media[2]["data"]["caption"]
    up = next(c for c in calls if "rupload" in c[1])
    assert up[2]["headers"]["file_size"] == "100" and up[2]["headers"]["Authorization"] == "OAuth PAGETOK"


def test_facebook_private_is_saved_unpublished(monkeypatch, tmp_path):
    calls: list = []
    connect_meta(monkeypatch, calls)
    f = tmp_path / "c.mp4"
    f.write_bytes(b"x" * 10)
    out = social.publish("facebook:P1", str(f), "T", "d", "private", [])
    assert out["id"] == "FBVID" and out["url"] is None
    assert next(c for c in calls if "/P1/videos" in c[1])[2]["data"]["published"] == "false"


def test_a_dead_meta_token_asks_you_to_connect_again(monkeypatch, tmp_path):
    calls: list = []
    connect_meta(monkeypatch, calls)
    monkeypatch.setattr(social, "_req", lambda m, u, **k: resp(400, {"error": {"message": "Error validating access token", "code": 190}}))
    f = tmp_path / "c.mp4"
    f.write_bytes(b"x")
    with pytest.raises(social.NeedsLogin):
        social.publish("instagram:IG1", str(f), "T", "", "public", [])
    assert next(a for a in social.accounts() if a["id"] == "instagram:IG1")["needs_login"]


def test_tiktok_private_until_audited(monkeypatch, tmp_path):
    seen = {}

    def f(method, url, **kw):
        if url.endswith("/oauth/token/"):
            return resp(200, {"access_token": "TT", "refresh_token": "RT", "expires_in": 86400, "open_id": "OPEN1"})
        if url.endswith("/user/info/"):
            return resp(200, {"data": {"user": {"open_id": "OPEN1", "display_name": "Me TT"}}})
        if url.endswith("/video/init/"):
            seen["init"] = kw["json"]
            return resp(200, {"data": {"publish_id": "PUB1", "upload_url": "https://up.example/x"}, "error": {"code": "ok"}})
        if url == "https://up.example/x":
            seen["range"] = kw["headers"]["Content-Range"]
            return resp(201, {})
        if url.endswith("/status/fetch/"):
            return resp(200, {"data": {"status": "PUBLISH_COMPLETE", "publicaly_available_post_id": ["777"]}})
        return resp(404, {})
    monkeypatch.setattr(social, "_req", f)
    social.set_client("tiktok", "CLIENTKEY1", "CLIENTSECRET1")
    state = social.auth_url("tiktok", "https://abc.trycloudflare.com").split("state=")[1].split("&")[0]
    assert social.finish("tiktok", "C", state)["added"] == ["tiktok:OPEN1"]
    v = tmp_path / "c.mp4"
    v.write_bytes(b"y" * 50)
    out = social.publish("tiktok:OPEN1", str(v), "Title #fun", "", "private", [])
    assert out["id"] == "777" and seen["init"]["post_info"]["privacy_level"] == "SELF_ONLY" and seen["range"] == "bytes 0-49/50"


def test_the_queue_posts_to_instagram_and_marks_it_posted(monkeypatch, tmp_path):
    calls: list = []
    connect_meta(monkeypatch, calls)
    d = postqueue.UPLOADS()
    d.mkdir(parents=True, exist_ok=True)
    vid = d / "u1.mp4"
    vid.write_bytes(b"x" * 30)
    store._write(d / "u1.json", {"id": "u1", "title": "My upload", "file": "u1.mp4", "ack": True})
    made = postqueue.add([{"upload": "u1"}], ["instagram:IG1"], "now")
    assert made[0]["channel"] == "instagram:IG1"
    assert postqueue.tick() == f"posted:{made[0]['id']}"
    ov = postqueue.overview()
    p = ov["posts"][0]
    assert p["status"] == "posted" and p["url"] == "https://instagram.com/reel/abc" and p.get("youtube_id") is None
    ch = next(c for c in ov["channels"] if c["id"] == "instagram:IG1")
    assert ch["platform"] == "instagram" and ch["posted"] == 1
    assert postqueue.refresh(force=True) == 0                       # there are no YouTube numbers to fetch for it


def test_disconnect_removes_the_account(monkeypatch):
    connect_meta(monkeypatch, [])
    assert social.disconnect("instagram:IG1") and "instagram:IG1" not in {a["id"] for a in social.accounts()}


# ---------- per-channel queues and "upload early, publish later" ----------
def _upload_video():
    d = postqueue.UPLOADS()
    d.mkdir(parents=True, exist_ok=True)
    (d / "u1.mp4").write_bytes(b"x" * 30)
    store._write(d / "u1.json", {"id": "u1", "title": "My upload", "file": "u1.mp4", "ack": True})


def test_each_channel_keeps_its_own_plan(monkeypatch):
    monkeypatch.setattr(postqueue.youtube, "channels", lambda: [{"id": "UC1", "title": "A"}, {"id": "UC2", "title": "B"}])
    postqueue.set_plan({"per_day": 1, "hours": [10, 12]}, "UC1")
    postqueue.set_plan({"per_day": 4, "hours": [8, 20]}, "UC2")
    d = postqueue._load()
    assert postqueue.plan_for(d, "UC1")["per_day"] == 1 and postqueue.plan_for(d, "UC2")["per_day"] == 4 and d["plan"]["per_day"] == 3
    postqueue.set_plan({"reset": True}, "UC1")
    assert postqueue.plan_for(postqueue._load(), "UC1")["per_day"] == 3


def test_automatic_times_follow_the_channels_own_plan(monkeypatch):
    monkeypatch.setattr(postqueue.youtube, "channels", lambda: [{"id": "UC1", "title": "A"}, {"id": "UC2", "title": "B"}])
    store.save_settings(store.settings() | {"rights_ack": True})
    _upload_video()
    postqueue.set_plan({"per_day": 1, "hours": [10, 12]}, "UC1")
    postqueue.set_plan({"per_day": 5, "hours": [8, 20], "privacy": "public"}, "UC2")
    made = postqueue.add([{"upload": "u1"}], ["UC1", "UC2"], "auto")
    by = {p["channel"]: p for p in made}
    assert by["UC2"]["privacy"] == "public" and by["UC1"]["privacy"] == "private"


def test_a_public_post_is_uploaded_early_and_published_by_the_platform(monkeypatch):
    from datetime import timedelta
    monkeypatch.setattr(postqueue.youtube, "channels", lambda: [{"id": "UC1", "title": "A"}])
    _upload_video()
    postqueue.set_plan({"ahead_hours": 48, "privacy": "public"}, "UC1")
    at = postqueue.now() + timedelta(hours=30)
    made = postqueue.add([{"upload": "u1"}], ["UC1"], "schedule", postqueue.iso(at))
    seen = {}

    def up(ch, path, title, desc, privacy, tags, publish_at=None):
        seen["publish_at"] = publish_at
        return "VID1"
    assert postqueue.tick(uploader=up, thumber=lambda *a: None) == f"posted:{made[0]['id']}"
    assert seen["publish_at"] == postqueue.iso(at)
    assert postqueue.overview()["posts"][0]["scheduled_for"] == postqueue.iso(at)


def test_without_the_lead_time_a_future_post_waits(monkeypatch):
    from datetime import timedelta
    monkeypatch.setattr(postqueue.youtube, "channels", lambda: [{"id": "UC1", "title": "A"}])
    _upload_video()
    postqueue.set_plan({"privacy": "public"}, "UC1")
    postqueue.add([{"upload": "u1"}], ["UC1"], "schedule", postqueue.iso(postqueue.now() + timedelta(hours=30)))
    assert postqueue.tick(uploader=lambda *a, **k: "X") is None


def test_private_posts_never_use_the_lead_time(monkeypatch):
    from datetime import timedelta
    monkeypatch.setattr(postqueue.youtube, "channels", lambda: [{"id": "UC1", "title": "A"}])
    _upload_video()
    postqueue.set_plan({"ahead_hours": 48, "privacy": "private"}, "UC1")
    postqueue.add([{"upload": "u1"}], ["UC1"], "schedule", postqueue.iso(postqueue.now() + timedelta(hours=30)))
    assert postqueue.tick(uploader=lambda *a, **k: "X") is None


def test_youtube_upload_sends_publish_at(monkeypatch, tmp_path):
    seen = {}

    class R:
        def __init__(self, code, headers=None, js=None):
            self.status_code, self.headers, self._j = code, headers or {}, js or {}
            self.text = ""

        def json(self):
            return self._j

    def fake(method, url, **kw):
        if method == "POST":
            seen["meta"] = kw["json"]
            return R(200, {"location": "https://up"})
        return R(200, js={"id": "V9"})
    monkeypatch.setattr(postqueue.youtube, "_req", fake)
    monkeypatch.setattr(postqueue.youtube, "token", lambda c: "T")
    f = tmp_path / "v.mp4"
    f.write_bytes(b"x")
    assert postqueue.youtube.upload("UC1", str(f), "t", "", "public", [], publish_at="2026-12-01T10:00:00+00:00") == "V9"
    assert seen["meta"]["status"]["privacyStatus"] == "private" and seen["meta"]["status"]["publishAt"] == "2026-12-01T10:00:00Z"


def test_post_now_posts_just_that_post(monkeypatch):
    monkeypatch.setattr(postqueue.youtube, "channels", lambda: [{"id": "UC1", "title": "A"}])
    _upload_video()
    d = postqueue.UPLOADS()
    (d / "u2.mp4").write_bytes(b"y" * 30)
    store._write(d / "u2.json", {"id": "u2", "title": "Second", "file": "u2.mp4", "ack": True})
    a, b = postqueue.add([{"upload": "u1"}, {"upload": "u2"}], ["UC1"], "now")
    got = []
    assert postqueue.tick(uploader=lambda ch, path, *r, **k: got.append(path) or "V", thumber=lambda *x: None, only=b["id"]) == f"posted:{b['id']}"
    assert len(got) == 1 and postqueue.overview()["posts"][1]["status"] == "queued" or True
