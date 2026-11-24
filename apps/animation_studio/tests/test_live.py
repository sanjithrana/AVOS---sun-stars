import shutil
import subprocess

import pytest

from studio.autoclip import live


def feed(det, counts, uniq_ratio=0.9, start=0.0):
    out = []
    for i, c in enumerate(counts):
        r = det.push(start + i * 5, {"count": c, "unique": int(c * uniq_ratio), "hype": 0, "top": [], "samples": []})
        if r:
            out.append((i, r))
    return out


def test_parse_irc_and_counter_rules():
    assert live.parse_irc(":bob!bob@bob.tmi.twitch.tv PRIVMSG #speed :LOL no way") == ("bob", "LOL no way")
    assert live.parse_irc("PING :tmi.twitch.tv") is None
    c = live.ChatCounter()
    for _ in range(5):
        c.add("fan", "omg")                    # only 2 per person count
    c.add("nightbot", "buy merch")             # bots are ignored
    c.add("x", "!clip")                        # commands are ignored
    c.add("y", "wtf lol")
    b = c.flush()
    assert b["count"] == 3 and b["unique"] == 2 and b["hype"] >= 3
    assert c.flush()["count"] == 0


def test_spike_needs_all_the_rules():
    d = live.Detector(10)
    got = feed(d, [3, 4, 3, 5, 4, 3, 4, 5, 3, 4, 4, 3, 4, 3, 4, 40, 3])
    assert len(got) == 1 and got[0][0] == 15 and got[0][1]["score"] > 5
    d = live.Detector(10)
    assert feed(d, [3, 4] * 8 + [40], uniq_ratio=0.2) == []                 # one person spamming is not a crowd
    d = live.Detector(10)
    assert feed(d, [3, 4] * 3 + [40]) == []                                  # still warming up
    d = live.Detector(50)
    assert feed(d, [3, 4] * 8 + [40]) == []                                  # under the streamer's own minimum
    d = live.Detector(10)
    got = feed(d, [3, 4] * 8 + [40, 45, 50])
    assert len(got) == 1                                                     # the 90 s cooldown holds the next buckets back


def test_audio_only_fallback_needs_two_loud_seconds():
    d = live.Detector(10)
    t = 0
    for i in range(80):
        assert d.push_audio(t, -30 + (i % 3)) is None
        t += 1
    assert d.push_audio(t, -5) is None
    assert d.push_audio(t + 1, -4) and True


def test_window_math():
    assert live.window(0, 200, 75, 45, 600) == (12, 24)
    assert live.window(0, 20, 75, 45, 600) == (0, 6)
    assert live.window(0, 590, 75, 45, 600)[1] == 59


def test_save_streamers_cleans_and_dedupes():
    rows = live.save_streamers([{"platform": "twitch", "handle": "https://twitch.tv/Speed/"}, {"platform": "twitch", "handle": "speed"}, {"platform": "kick", "handle": "x y", "min_messages": 999}, {"handle": ""}])
    assert [r["id"] for r in rows] == ["twitch-speed", "kick-xy"] and rows[1]["min_messages"] == 200
    assert live.url_for(rows[0]) == "https://www.twitch.tv/Speed"


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="needs ffmpeg")
def test_join_pieces_and_make_job(tmp_path, monkeypatch):
    from studio.autoclip import pipeline, store
    files = []
    for i in range(4):
        f = tmp_path / f"{i:06d}.ts"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc=s=160x90:r=15:d=2", "-f", "lavfi", "-i", "sine=d=2", "-c:v", "libx264", "-c:a", "aac", "-f", "mpegts", str(f)], check=True)
        files.append(f)
    started = []
    monkeypatch.setattr(pipeline, "start", lambda jid: started.append(jid) or True)
    s = {"id": "twitch-speed", "platform": "twitch", "handle": "speed", "permission": False}
    jid = live.make_job(s, files, {"kind": "chat", "count": 30, "unique": 28, "score": 7.5, "audio_z": 2.0, "top": ["lol"], "samples": ["lol"]}, live.DEFAULT_SETTINGS)
    job = store.load(jid)
    assert started == [jid] and (store.jdir(jid) / "source.mp4").is_file()
    assert job["permission"] == "unconfirmed" and job["source"]["live"]["handle"] == "speed"
    s["permission"] = True
    jid2 = live.make_job(s, files, {"kind": "chat", "count": 30, "unique": 28, "score": 7.5, "audio_z": 2.0, "top": [], "samples": []}, live.DEFAULT_SETTINGS)
    assert store.load(jid2)["permission"] == "granted"
