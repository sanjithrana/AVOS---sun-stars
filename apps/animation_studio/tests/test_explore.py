"""Explore: watched channels + charts ranked by views per hour, with YouTube faked."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from studio.autoclip import explore, store


@pytest.fixture(autouse=True)
def root(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "ROOT", tmp_path / "ac")


def vid(i, secs, views, hours_ago=10, live=False):
    pub = (datetime.now(timezone.utc) - timedelta(hours=hours_ago)).isoformat()
    return {"id": f"v{i}", "url": f"https://www.youtube.com/watch?v=v{i}", "title": f"T{i}", "channel": "C", "thumb": "", "views": views, "seconds": secs, "published": pub, "live": live}


def api(monkeypatch, watched, chart=None, search=None):
    monkeypatch.setattr(explore, "_auth", lambda: {"Authorization": "Bearer x"})
    monkeypatch.setattr(explore, "_watch_api", lambda h, handles, per=6: [x["id"] for x in watched])
    monkeypatch.setattr(explore, "_details", lambda h, ids: [x for x in watched if x["id"] in ids])
    calls = []
    monkeypatch.setattr(explore, "_api", lambda cat, region: calls.append(cat) or (chart if "chart" in cat else search) or [])
    return calls


def test_ranked_by_views_per_hour_live_first_short_dropped(monkeypatch):
    w = [vid(1, 3000, 1_000_000, hours_ago=100), vid(2, 3000, 600_000, hours_ago=10), vid(3, 120, 9_000_000), vid(4, 0, 50, live=True)]
    api(monkeypatch, w, chart=[vid(5, 1800, 100_000, hours_ago=1)] + [vid(10 + i, 1800, 10, 5) for i in range(10)])
    r = explore.trending("gaming", "IN")
    ids = [x["id"] for x in r["items"]]
    assert ids[0] == "v4" and ids[1:4] == ["v5", "v2", "v1"] and "v3" not in ids
    assert abs(r["items"][1]["per_hour"] - 100_000) <= 5 and r["source"] == "youtube" and "@IShowSpeed" in r["watching"]


def test_search_only_when_thin(monkeypatch):
    calls = api(monkeypatch, [vid(1, 3000, 100)], chart=None, search=[vid(9, 2400, 5)])
    r = explore.trending("podcasts", "US")
    assert any("chart" not in c for c in calls) and {x["id"] for x in r["items"]} == {"v1", "v9"}


def test_no_channel_uses_plain_search(monkeypatch):
    monkeypatch.setattr(explore, "_auth", lambda: None)
    monkeypatch.setattr(explore, "_watch_search", lambda handles, per=4: [vid(7, 2000, 10)])
    monkeypatch.setattr(explore, "_search", lambda cat: [vid(8, 2000, 5)])
    r = explore.trending("comedy", "IN")
    assert r["source"] == "search" and {x["id"] for x in r["items"]} == {"v7", "v8"}


def test_follow_your_own_channels(monkeypatch):
    assert explore.add_channel("https://www.youtube.com/@SomeStreamer") == ["@SomeStreamer"]
    assert explore.handles_for("comedy")[0] == "@SomeStreamer" and explore.handles_for("all")[0] == "@SomeStreamer"
    assert explore.remove_channel("@somestreamer") == []
    with pytest.raises(ValueError):
        explore.add_channel("@")


def test_api_rows_parse_duration_and_live():
    row = explore._row({"id": "abc", "snippet": {"title": "x", "channelTitle": "ch", "liveBroadcastContent": "live", "thumbnails": {"high": {"url": "u"}}},
                        "statistics": {"viewCount": "42"}, "contentDetails": {"duration": "PT1H2M3S"}})
    assert row["seconds"] == 3723 and row["live"] and row["views"] == 42 and row["thumb"] == "u"


def test_routes(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from studio.autoclip.routes import router
    api(monkeypatch, [vid(9, 900, 5)])
    app = FastAPI()
    app.include_router(router)
    c = TestClient(app)
    j = c.get("/api/autoclip/explore?cat=comedy&region=GB").json()
    assert j["items"][0]["id"] == "v9" and j["cats"]["comedy"] == "Comedy" and j["mine"] == []
    assert c.post("/api/autoclip/explore/channels", json={"handle": "@abc"}).json()["mine"] == ["@abc"]
    assert c.delete("/api/autoclip/explore/channels/@abc").json()["mine"] == []


def test_every_length_and_the_whole_chart(monkeypatch):
    api(monkeypatch, [vid(1, 3000, 100)], chart=[vid(2, 60, 9_000_000, 2), vid(3, 900, 50_000, 3)])
    long_ = explore.trending("all", "IN")
    every = explore.trending("all", "IN", length="any")
    assert {x["id"] for x in long_["items"]} == {"v1", "v3"} and long_["total"] == 3
    assert every["items"][0]["id"] == "v2" and len(every["items"]) == 3
    assert {"music", "film", "entertainment", "pets"} <= set(explore.CATS) and explore.CATS["all"]["chart"] == ""


def test_chart_pages_through_up_to_200(monkeypatch):
    from studio.autoclip import youtube

    class R:
        def __init__(self, n, tok):
            self.status_code, self._n, self._tok = 200, n, tok

        def json(self):
            return {"items": [{"id": f"p{self._n}-{i}", "snippet": {}, "statistics": {}, "contentDetails": {"duration": "PT10M"}} for i in range(50)], "nextPageToken": self._tok}
    pages = iter([R(1, "a"), R(2, "b"), R(3, "c"), R(4, None)])
    monkeypatch.setattr(explore, "_auth", lambda: {"Authorization": "x"})
    monkeypatch.setattr(youtube, "_req", lambda *a, **k: next(pages))
    assert len(explore._api(explore.CATS["all"], "IN")) == 200


def test_channels_are_read_in_parallel(monkeypatch):
    import time as _t
    def slow(h, hd, per, since):
        _t.sleep(0.2)
        return [hd]
    monkeypatch.setattr(explore, "_one_channel", slow)
    t0 = _t.time()
    ids = explore._watch_api({}, [f"@c{i}" for i in range(24)])
    assert len(ids) == 24 and _t.time() - t0 < 1.5            # 24 channels x 0.2 s one by one would be 4.8 s
