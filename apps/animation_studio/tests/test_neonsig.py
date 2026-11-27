"""NeonClipping's moment finders inside Auto Clip (neonsig.py, adapted from NeonClipping, MIT)."""
from __future__ import annotations

import shutil
import subprocess

import pytest

from studio.autoclip import neonsig

needs_ffmpeg = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not installed")


def W(text, t0=0.0, step=0.4):
    return [{"w": w, "s": t0 + i * step, "e": t0 + i * step + 0.3} for i, w in enumerate(text.split())]


def test_what_is_said_lights_up_the_right_seconds():
    ws = W("so we are just driving around here", 0) + W("oh my god bhaago police wasted", 30)
    sig = neonsig.excite(ws, 60)
    assert len(sig) == 60 and max(sig[28:36]) == 1.0 and max(sig[:10]) < 0.5
    assert neonsig.excite([], 10) == []
    assert "wasted" in neonsig.game_events("bro I got wasted again")


def test_filler_hooks_and_support():
    assert neonsig.filler("welcome back everyone, like and subscribe and hit the bell")
    assert not neonsig.filler("he finally found the keys in the car")
    text = "So we searched for an hour. But the keys were stuck in the car the whole time. Unbelievable."
    h = neonsig.extract_hook(text)
    assert "keys" in h and len(h.split()) <= 12
    assert neonsig.hook_supported("The keys were stuck in the car", text)
    assert not neonsig.hook_supported("Shocking secret revealed about space aliens", text)


def test_varied_drops_overlaps_and_prefers_different_words():
    ms = [{"start": 0, "end": 30, "score": 10, "t": "police chase on the highway"},
          {"start": 10, "end": 40, "score": 9, "t": "police chase again"},
          {"start": 100, "end": 130, "score": 8, "t": "police chase on the highway again"},
          {"start": 200, "end": 230, "score": 7.9, "t": "a quiet joke about pizza"}]
    got = neonsig.varied(ms, lambda m: m["t"], 2)
    assert [m["start"] for m in got] == [0, 200]


@needs_ffmpeg
def test_audio_finds_the_boom(tmp_path):
    src = tmp_path / "a.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "sine=f=300:d=40", "-f", "lavfi", "-i", "anoisesrc=d=2:a=0.9",
                    "-filter_complex", "[0]volume=0.05[q];[1]adelay=25000|25000[n];[q][n]amix=inputs=2:duration=first:normalize=0[a]",
                    "-map", "[a]", "-c:a", "aac", str(src)], check=True)
    a = neonsig.audio(str(src), 0, 40)
    assert set(a) == {"loud", "shout", "bang"} and len(a["loud"]) == 40
    cur = neonsig.audio_curve(a)
    assert cur.index(max(cur)) in range(24, 28)


@needs_ffmpeg
def test_scene_cut_alignment(tmp_path):
    src = tmp_path / "v.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=black:s=320x180:d=1", "-f", "lavfi", "-i", "testsrc2=s=320x180:d=30",
                    "-filter_complex", "[0][1]concat=n=2:v=1:a=0", "-r", "25", "-pix_fmt", "yuv420p", str(src)], check=True)
    ws = W("hello there this is the moment " * 5, 2.0, 0.5)
    m = neonsig.on_scene_cut(str(src), {"start": 0.3, "end": 25.0}, ws, 10)
    assert 0.9 <= m["start"] <= 1.1
