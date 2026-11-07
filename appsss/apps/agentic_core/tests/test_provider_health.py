"""A provider with no credit / a refused key is skipped for a while (shared with the Studio), and says why."""
from pathlib import Path

import httpx
import pytest

from agentic_core.models import catalog, fal_client, provider_health as PH

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def iso(monkeypatch, tmp_path):
    monkeypatch.setenv("AVOS_SETTINGS_FILE", str(tmp_path / "settings.json"))
    monkeypatch.setenv("FAL_KEY", "k1")
    yield


def test_classify_mark_and_expire(monkeypatch):
    assert PH.classify(403, '{"detail":"User is locked. Reason: Exhausted balance."}') == "billing"
    assert PH.classify(401, "bad key") == "auth" and PH.classify(429, "daily quota of neurons") == "quota" and PH.classify(500, "x") is None
    msg = PH.mark("fal", "billing", '{"detail":"User is locked. Reason: Exhausted balance."}')
    assert msg.startswith("fal.ai: no credit left (User is locked") and "fal.ai/dashboard/billing" in msg
    assert PH.down("fal") == msg and PH.snapshot() == {"fal": msg}
    assert "no credit left" in catalog.available_backends("z-image")["fal"]
    monkeypatch.setenv("FAL_KEY", "k2")                     # a new key → tried again
    assert PH.down("fal") is None and catalog.available_backends("z-image")["fal"] is None


def test_the_fal_client_marks_it(monkeypatch):
    r = httpx.Response(403, json={"detail": "User is locked. Reason: Exhausted balance."}, request=httpx.Request("POST", "https://queue.fal.run/x"))
    with pytest.raises(fal_client.FalError):
        fal_client._check(r, "submitting", "fal-ai/z-image/turbo")
    assert "no credit left" in PH.down("fal")


def test_the_studio_has_an_identical_copy():
    assert (ROOT / "agentic_core/models/provider_health.py").read_text() == (ROOT / "animation_studio/studio/provider_health.py").read_text()
