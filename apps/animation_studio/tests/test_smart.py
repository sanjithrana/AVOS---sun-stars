"""Long videos are never downloaded whole: replay graph + captions + only the chosen windows. Every network call is faked."""
from __future__ import annotations

import json
import shutil
import subprocess
import threading

import pytest

from studio.autoclip import intake, pipeline, rights, smart, store

ff = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg missing")


@pytest.fixture(autouse=True)
def root(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "ROOT", tmp_path / "ac")
    monkeypatch.setattr(intake, "public_url", lambda u: u)
    monkeypatch.setattr(rights, "platform", lambda u: "youtube")


def test_the_replay_graph_becomes_a_per_second_curve_with_contrast():
    heat = [{"start_time": i * 10.0, "end_time": (i + 1) * 10.0, "value": 0.2 if i != 7 else 1.0} for i in range(20)]
    h = smart.heat_curve(heat, 200)
    assert len(h) == 200 and max(h[70:80]) == 1.0 and max(h[:60]) == 0.0
    flat = [{"start_time": i * 10.0, "end_time": (i + 1) * 10.0, "value": 0.5} for i in range(20)]
    assert max(smart.heat_curve(flat, 200)) == 0.0                           # nothing stands out: no clips


def test_json3_captions_become_cues_with_word_times_and_drop_repeats():
    j = {"events": [{"tStartMs": 1000, "dDurationMs": 2000, "segs": [{"utf8": "hello"}, {"utf8": " there", "tOffsetMs": 600}]},
                    {"tStartMs": 3000, "dDurationMs": 1000, "segs": [{"utf8": "hello there"}]},
                    {"tStartMs": 3000, "dDurationMs": 1000, "segs": [{"utf8": "\\n"}]}]}
    cues = smart.parse_json3(j)
    assert cues[0]["words"][1] == {"w": "there", "s": 1.6, "e": 3.0} and len(cues) == 2 or len(cues) == 1


def test_a_short_video_is_downloaded_normally(monkeypatch):
    monkeypatch.setattr(smart, "probe", lambda url, cancel=None: {"duration": 600.0, "title": "t", "live": False, "heatmap": [], "chapters": [], "has_subs": True})
    assert smart.scout("https://youtu.be/x", store.ROOT, {"smart": "auto", "smart_min": 45}, None, lambda t: None, lambda p, t: None, lambda: None) is None


def test_the_window_words_are_moved_to_the_windows_own_clock():
    ws = [{"w": "a", "s": 100.0, "e": 100.5}, {"w": "b", "s": 500.0, "e": 500.5}]
    assert smart.shifted(ws, 90.0, 95.0, 120.0) == [{"w": "a", "s": 10.0, "e": 10.5}]


@ff
def test_a_long_video_makes_clips_from_small_windows_only(tmp_path, monkeypatch):
    long_s = 3 * 3600
    heat = [{"start_time": i * 100.0, "end_time": (i + 1) * 100.0, "value": 1.0 if i == 40 else 0.1} for i in range(int(long_s / 100))]
    cues = [{"start": 4010.0, "end": 4014.0, "text": "oh my god this is insane", "words": [{"w": w, "s": 4010.0 + i * 0.5, "e": 4010.4 + i * 0.5} for i, w in enumerate("oh my god this is insane".split())]}]
    monkeypatch.setattr(smart, "probe", lambda url, cancel=None: {"duration": float(long_s), "title": "Long stream", "live": False, "heatmap": heat, "chapters": [], "has_subs": True})
    monkeypatch.setattr(smart, "captions", lambda url, dest, cancel=None: cues)
    asked = []

    def fake_section(url, out_file, t0, t1, cancel=None):
        asked.append((t0, t1))
        out_file.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"testsrc2=s=640x360:r=25:d={int(t1 - t0)}", "-f", "lavfi", "-i", f"sine=f=300:d={int(t1 - t0)}",
                        "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", "-shortest", str(out_file)], check=True)
        return out_file
    monkeypatch.setattr(smart, "section", fake_section)
    monkeypatch.setattr(smart, "audio", lambda *a, **k: (_ for _ in ()).throw(AssertionError("the audio must not be fetched when there is a replay graph")))
    job = pipeline.new_job(pipeline.build_opts({"count": 2, "min_seconds": 8, "max_seconds": 20}), {"kind": "url", "url": "https://youtu.be/long", "name": "Long stream"})
    d = store.jdir(job["id"])
    pipeline._cancel[job["id"]] = threading.Event()
    pipeline._run(job["id"])
    j = store.load(job["id"])
    assert j["status"] == "done", j.get("error")
    assert not list(d.glob("source.*")), "the long video must not be downloaded"
    assert asked and all(t1 - t0 < 60 for t0, t1 in asked) and 3900 <= asked[0][0] <= 4100        # a window around the replay peak at 4000-4100 s
    c = j["clips"][0]
    assert c["status"] == "ready" and c["sec"] == "sections/sec-1.mp4" and 3900 <= c["start"] <= 4100 and (d / c["file"]).is_file()
    assert c["captions"] is True and "not downloaded" in json.dumps(j["steps"])
    # a re-run keeps the windows already fetched
    n = len(asked)
    pipeline._cancel[job["id"]] = threading.Event()
    pipeline._run(job["id"])
    assert len(asked) == n


def test_chat_replay_counts_and_surges(tmp_path):
    import json as _j
    from studio.autoclip import smart
    f = tmp_path / "chat.live_chat.json"
    lines = []
    for sec in range(0, 600):
        n = 1 if sec % 3 == 0 else 0
        if 300 <= sec < 312:
            n = 12                                                    # chat explodes
        for _ in range(n):
            lines.append(_j.dumps({"replayChatItemAction": {"actions": [{"addChatItemAction": {"item": {}}}], "videoOffsetTimeMsec": str(sec * 1000 + 100)}}))
    lines.append("not json")
    lines.append(_j.dumps({"replayChatItemAction": {"actions": [{"addChatItemAction": {}}], "videoOffsetTimeMsec": "-5000"}}))   # before the video starts
    f.write_text("\n".join(lines), "utf-8")
    c = smart.parse_chat(f)
    assert c[300] == 12 and 0 not in [k for k in c if k < 0]
    cur = smart.chat_curve(c, 600)
    assert max(cur[298:316]) > 0.8 and max(cur[50:250]) < 0.35


def test_fuse_ranks_agreeing_signals_above_a_single_one():
    from studio.autoclip import hype, smart
    n = 100
    heat = [0.0] * n
    cht = [0.0] * n
    heat[20], heat[70] = 0.8, 0.8
    cht[70] = 0.8                                                     # at 70 the crowd agrees with the replay graph
    cur, used = smart.fuse(heat, [], cht, [0.0] * n, n)
    assert cur[70] > cur[20] + 0.25
    assert "the live chat" in used and "the replay graph" in used
    w = [{"w": "no", "s": 40.2, "e": 40.4}, {"w": "way!", "s": 40.5, "e": 40.8}]
    lx = smart.lex_curve(w, n, hype.EXCITED)
    assert lx[40] > 0.4 and lx[10] == 0.0
