"""Broken downloads and broken clips never reach you; the clip count follows the video's length."""
import subprocess
from pathlib import Path

import pytest

from studio.autoclip import cut, intake, pipeline, smart


@pytest.fixture(autouse=True)
def no_dns(monkeypatch):
    monkeypatch.setattr(intake, "public_url", lambda u: u)


def test_section_retries_until_it_has_sound_and_length(tmp_path, monkeypatch):
    calls = []
    def fake_exec(cmd, cancel, timeout):
        calls.append(cmd)
        f = tmp_path / "sec-1.mp4"
        f.write_bytes(b"x" * 30000)
        return 0, str(f) + "\n", ""
    infos = iter([(0.0, True), (40.0, False), (40.0, True)])            # 1st: 0 s, 2nd: silent, 3rd: good
    monkeypatch.setattr(smart, "_exec", fake_exec)
    monkeypatch.setattr(cut, "media_info", lambda p: next(infos))
    got = smart.section("https://youtu.be/x", tmp_path / "sec-1.mp4", 100, 140)
    assert got.name == "sec-1.mp4" and len(calls) == 3 and "--force-keyframes-at-cuts" in calls[0] and "--force-keyframes-at-cuts" not in calls[1]


def test_section_gives_up_with_a_reason(tmp_path, monkeypatch):
    monkeypatch.setattr(smart, "_exec", lambda cmd, cancel, timeout: (1, "", "ERROR: ffmpeg exited with code 251"))
    with pytest.raises(RuntimeError, match="251"):
        smart.section("https://youtu.be/x", tmp_path / "sec-2.mp4", 0, 30)


@pytest.mark.skipif(subprocess.run(["which", "ffmpeg"], capture_output=True).returncode != 0, reason="no ffmpeg")
def test_check_clip(tmp_path):
    good, mute = tmp_path / "g.mp4", tmp_path / "m.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=320x240:d=6", "-f", "lavfi", "-i", "sine=d=6", "-shortest", str(good)], check=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=320x240:d=6", str(mute)], check=True)
    assert pipeline.check_clip(good, 6, True) is None
    assert "no sound" in pipeline.check_clip(mute, 6, True)
    assert "long instead" in pipeline.check_clip(good, 40, True)
    assert pipeline.check_clip(tmp_path / "none.mp4", 6, True) == "the file is empty"


def test_auto_count():
    assert pipeline.auto_count(8 * 60) == 3 and pipeline.auto_count(50 * 60) == 10 and pipeline.auto_count(5 * 3600) == 15
    assert pipeline.build_opts({"count": 0})["count"] == 0 and pipeline.build_opts({})["count"] == 0
