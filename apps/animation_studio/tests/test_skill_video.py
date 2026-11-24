"""Skills and Stickman can use the fabric's open video models (Wan 2.2 / LTX 2.3) when Seedance isn't available or isn't picked."""
from __future__ import annotations

import pytest

from studio import models
from studio.series import media
from studio.stickman import video


def run(model="auto", local=False):
    return {"settings": {"models": {"motion": {"model": model}}, "local_only": local}}


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    monkeypatch.delenv("FAL_KEY", raising=False)
    video._now.s = None


def test_seedance_first_when_a_fal_key_is_set(monkeypatch):
    monkeypatch.setenv("FAL_KEY", "test-not-real")
    s = run()
    assert video.ready(s) and video.engine(s) == "seedance-2-mini" and video.open_models(s) == []


def test_no_key_and_no_open_model_means_no_video(monkeypatch):
    monkeypatch.setattr(media, "usable", lambda s, step, mid: False)
    assert video.ready(run()) is False


def test_no_key_uses_an_installed_open_model(monkeypatch):
    monkeypatch.setattr(media, "usable", lambda s, step, mid: mid == "ltx-2.3")
    s = run()
    assert video.ready(s) and video.engine(s) == "ltx-2.3"


def test_picking_wan_beats_a_fal_key(monkeypatch):
    monkeypatch.setenv("FAL_KEY", "test-not-real")
    s = run("wan-2.2")
    assert video.ready(s) and video.engine(s) == "wan-2.2"


def test_off_and_this_pc_only_with_seedance(monkeypatch):
    monkeypatch.setenv("FAL_KEY", "test-not-real")
    monkeypatch.setattr(media, "usable", lambda s, step, mid: False)
    assert video.ready(run("off")) is False
    assert video.ready(run(local=True)) is False          # Seedance is fal-only


def test_clip_runs_the_open_model_with_the_first_picture_only(monkeypatch):
    seen = {}

    def fake(mid, **kw):
        seen.update(mid=mid, **kw)
        return b"VIDEO"
    monkeypatch.setattr(models, "run_model", fake)
    monkeypatch.setattr(media, "where", lambda s, step, mid: "gpu")
    s = run("wan-2.2")
    assert video.ready(s)
    out = video.clip("a hand stirs", [b"A", b"B"], None, 10, "9:16", True)
    assert out == b"VIDEO" and seen["mid"] == "wan-2.2" and seen["inputs"] == {"image": b"A"}
    assert (seen["w"], seen["h"]) == (480, 832) and seen["backend"] == "gpu" and seen["frames"] <= 81


def test_open_clip_falls_to_the_next_model_then_raises(monkeypatch):
    calls = []

    def fake(mid, **kw):
        calls.append(mid)
        if mid == "wan-2.2":
            raise RuntimeError("worker down")
        return b"OK"
    monkeypatch.setattr(models, "run_model", fake)
    monkeypatch.setattr(media, "where", lambda s, step, mid: None)
    monkeypatch.setattr(media, "usable", lambda s, step, mid: True)
    s = run()
    video.ready(s)
    assert video.clip("p", [b"A"], None, 5, "16:9", False) == b"OK" and calls == ["wan-2.2", "ltx-2.3"]
    monkeypatch.setattr(models, "run_model", lambda mid, **kw: (_ for _ in ()).throw(RuntimeError("down")))
    with pytest.raises(RuntimeError, match="No open video model"):
        video.clip("p", [b"A"], None, 5, "16:9", False)


# ---- Cost: Free / Paid / Automatic ----
def cost(tier, model="auto"):
    s = run(model)
    s["settings"]["models"]["tier"] = {"model": tier}
    return s


def test_tier_reads_the_setting():
    assert media.tier(cost("free")) == "free" and media.tier(cost("paid")) == "paid" and media.tier(run()) == "auto"
    assert media.tier(cost("nonsense")) == "auto"


def test_free_never_uses_seedance_even_with_a_key(monkeypatch):
    monkeypatch.setenv("FAL_KEY", "test-not-real")
    monkeypatch.setattr(media, "usable", lambda s, step, mid: False)
    s = cost("free")
    assert video.ready(s) is False and "Free" in video.why_not(s)


def test_free_uses_an_open_model_on_the_pc(monkeypatch):
    monkeypatch.setenv("FAL_KEY", "test-not-real")
    monkeypatch.setattr(media, "usable", lambda s, step, mid: mid == "wan-2.2")
    s = cost("free")
    assert video.ready(s) and video.engine(s) == "wan-2.2"


def test_paid_wants_a_paid_engine(monkeypatch):
    monkeypatch.setattr(media, "usable", lambda s, step, mid: True)
    monkeypatch.setattr(media, "fal_ok", lambda mid: False)
    s = cost("paid")
    assert video.ready(s) is False and "Paid" in video.why_not(s)       # no key: no silent free stand-in
    assert video.ready(cost("paid", "wan-2.2")) is False
    monkeypatch.setattr(media, "fal_ok", lambda mid: mid == "ltx-2.3")
    assert video.open_models(s) == ["ltx-2.3"]
    monkeypatch.setenv("FAL_KEY", "test-not-real")
    assert video.engine(s) == "seedance-2-mini"


def test_where_free_and_paid_pick_the_place(monkeypatch):
    avail = {"gpu": "worker offline", "fal": None, "cloudflare": None}
    monkeypatch.setattr(models, "available", lambda mid: avail)
    monkeypatch.setattr(models, "get", lambda mid: {"name": "Wan 2.2"})
    assert media.where(cost("free"), "motion", "wan-2.2") == "cloudflare"
    assert media.where(cost("paid"), "motion", "wan-2.2") == "fal"
    avail.pop("cloudflare"); avail["gpu"] = "worker offline"
    avail["fal"] = None
    with pytest.raises(models.ModelUnavailable, match="no paid service was tried"):
        media.where(cost("free"), "motion", "wan-2.2")
    assert media.where(run(), "motion", "wan-2.2") is None              # Automatic is unchanged


# ---- Free stock footage (Pexels) ----
from studio.series import stock   # noqa: E402


def footage(model="stock", tier="auto", motion="auto", local=False):
    s = run(motion, local)
    s["settings"]["models"]["footage"] = {"model": model}
    s["settings"]["models"]["tier"] = {"model": tier}
    return s


def test_stock_is_only_used_when_you_choose_it_and_have_a_key(monkeypatch):
    monkeypatch.setattr(media, "usable", lambda s, step, mid: False)
    assert video.ready(footage()) is False                      # no Pexels key
    monkeypatch.setenv("PEXELS_API_KEY", "test-not-real")
    s = footage()
    assert video.ready(s) and video.engine(s) == "pexels-stock"
    assert video.ready(footage("auto")) is False                # not chosen: never a silent stand-in
    assert video.ready(footage(tier="paid")) is False and video.ready(footage(local=True)) is False
    assert video.ready(footage(motion="off")) is False
    assert "Pexels" in video.why_not(footage(tier="paid"))


def test_stock_beats_seedance_when_chosen(monkeypatch):
    monkeypatch.setenv("FAL_KEY", "test-not-real")
    monkeypatch.setenv("PEXELS_API_KEY", "test-not-real")
    s = footage()
    video.ready(s)
    monkeypatch.setattr(stock, "clip", lambda prompt, secs, aspect, seed=0: b"STOCK")
    assert video.clip("a baker kneads dough", [b"A"], None, 5, "9:16", True) == b"STOCK"


def test_query_of_keeps_the_content_words():
    assert stock.query_of("Starting from the attached image. A baker kneads dough on a floury table. Camera: slow push in. No text.") == "baker kneads dough floury"


def test_pick_prefers_long_enough_mp4_near_1080():
    vids = [{"id": 1, "duration": 3, "video_files": [{"file_type": "video/mp4", "link": "a", "quality": "hd", "width": 1080}]},
            {"id": 2, "duration": 9, "video_files": [{"file_type": "video/mp4", "link": "b", "quality": "hd", "width": 2160},
                                                      {"file_type": "video/mp4", "link": "c", "quality": "hd", "width": 1080},
                                                      {"file_type": "video/webm", "link": "d", "quality": "hd", "width": 1080}]}]
    v, f = stock.pick(vids, 5, "9:16")
    assert v["id"] == 2 and f["link"] == "c"
    assert stock.pick([], 5, "9:16") is None


def test_stock_clip_searches_pexels_and_credits_the_film_maker(monkeypatch):
    monkeypatch.setenv("PEXELS_API_KEY", "test-not-real")
    calls = []

    class R:
        def __init__(self, js=None, content=b"MP4", code=200):
            self._js, self.content, self.status_code = js, content, code

        def json(self):
            return self._js

        def raise_for_status(self):
            pass

    def fake_get(url, **kw):
        calls.append((url, kw.get("params"), kw.get("headers")))
        if "search" in url:
            return R({"videos": [{"id": 7, "duration": 8, "url": "https://pexels.com/video/7", "user": {"name": "Ann", "url": "https://pexels.com/@ann"},
                                  "video_files": [{"file_type": "video/mp4", "link": "https://cdn/x.mp4", "quality": "hd", "width": 1080}]}]})
        return R()
    monkeypatch.setattr(stock.httpx, "get", fake_get)
    stock.CREDITS.clear()
    assert stock.clip("a baker kneads dough", 5, "9:16") == b"MP4"
    assert calls[0][1]["orientation"] == "portrait" and calls[0][2] == {"Authorization": "test-not-real"}
    assert any("Pexels" in l for l in stock.credit_lines()) and any("Ann" in l for l in stock.credit_lines())
