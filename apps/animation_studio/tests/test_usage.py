"""The usage ledger: an estimate you can check, never a guess."""
from __future__ import annotations

import pytest

from studio import usage


@pytest.fixture(autouse=True)
def ledger(tmp_path, monkeypatch):
    monkeypatch.setattr(usage, "_path", lambda: tmp_path / "usage.jsonl")


def test_the_models_that_cost_money_are_priced_and_the_free_ones_are_not():
    assert usage.price_of("Seedance 2.0 Mini", "video") == (0.155, "second", True)
    assert usage.price_of("Seedance 2.0", "video") == (0.303, "second", True)
    assert usage.price_of("Wan 2.2", "video")[0] == 0.08
    for free in ("drawn in code", "macro move", "camera move", "Cloudflare FLUX.2 klein (from references)"):
        price, _unit, priced = usage.price_of(free, "image")
        assert price == 0.0 and priced, free


def test_an_unknown_model_is_counted_but_never_guessed_at():
    price, _unit, priced = usage.price_of("some-model-shipped-next-year", "image")
    assert price == 0.0 and not priced
    usage.record("image", "some-model-shipped-next-year", 1)
    s = usage.summary()
    assert s["total"]["calls"] == 1 and s["total"]["cost"] == 0.0
    assert s["total"]["unpriced"] == 1, "a total missing half its calls must not look like a small bill"


def test_a_sixty_second_company_story_comes_to_about_nine_dollars():
    """The figure that made the video model worth changing. Six scenes, ten seconds each, on Seedance Mini."""
    for _ in range(6):
        usage.record("image", "Cloudflare FLUX.2 klein (from references)", 1, run="r1", skill="company-story")
        usage.record("video", "Seedance 2.0 Mini", 10, run="r1", skill="company-story")
    s = usage.summary()
    assert 9.2 < s["total"]["cost"] < 9.4
    video = next(b for b in s["by_kind"] if b["name"] == "video")
    assert video["cost"] == s["total"]["cost"], "video is the whole bill; images round to nothing"


def test_the_free_skills_show_up_as_free_rather_than_missing():
    usage.record("free", "drawn in code", 1, run="c1", skill="asmr-cutting")
    s = usage.summary()
    assert s["total"]["calls"] == 1 and s["total"]["cost"] == 0.0 and s["total"]["free"] == 1
    assert s["total"]["unpriced"] == 0


def test_one_run_can_be_totted_up_on_its_own():
    usage.record("video", "Seedance 2.0 Mini", 10, run="a", skill="film-art-deco")
    usage.record("video", "Seedance 2.0 Mini", 10, run="b", skill="film-art-deco")
    assert usage.for_run("a")["cost"] == pytest.approx(1.55)
    assert usage.for_run("a")["calls"] == 1


def test_a_failed_call_is_recorded_because_most_plans_bill_for_it():
    usage.record("video", "Seedance 2.0 Mini", 8, ok=False, run="x")
    assert usage.summary()["total"]["failed"] == 1


def test_metering_never_raises_even_with_nowhere_to_write(monkeypatch):
    monkeypatch.setattr(usage, "_path", lambda: None)
    row = usage.record("image", "flux-schnell", 1)
    assert row["cost"] == pytest.approx(0.003)         # still returns the row for the caller
    assert usage.summary()["total"]["calls"] == 0      # just nothing persisted
