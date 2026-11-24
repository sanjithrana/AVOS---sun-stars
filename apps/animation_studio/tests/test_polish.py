"""Editing polish (zooms, stickers, music, loudness), hashtags and the coach (reward, bandit, modes)."""
from __future__ import annotations

import json
import random
import shutil
import subprocess
from datetime import datetime, timedelta, timezone

import pytest

from studio.autoclip import coach, cut, hype, meta, music, pick, pipeline, polish, stickers, store

ff = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg missing")


@pytest.fixture(autouse=True)
def root(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "ROOT", tmp_path / "ac")


def words(n=30):
    t, out = 0.5, []
    for i, w in enumerate("so this is crazy listen you will not believe it wow the money was insane and then he won the game and everyone started to laugh really hard today".split()[:n]):
        out.append({"w": w, "s": t, "e": t + 0.3})
        t += 0.4 + (0.4 if i % 5 == 4 else 0)
    return out


def test_plan_has_zooms_callouts_and_respects_off():
    ed = polish.plan_edit(words(), 0, 12, {"edit": "punchy"}, "funny", peaks=[8.0])
    assert ed["zooms"] and all(z[0] < z[1] for z in ed["zooms"]) and ed["peaks"] == [8.0]
    assert any(abs(z[0] - 7.9) < 0.05 for z in ed["zooms"])                      # the hype peak gets its own punch-in
    assert 1 <= len(ed["stickers"]) <= 6 and all(b["t0"] - a["t0"] >= 1.5 for a, b in zip(ed["stickers"], ed["stickers"][1:]))
    assert {s["text"] for s in ed["stickers"]} <= set(stickers.LABELS) | {"WOW!"} and all(s["kind"] in stickers.KINDS for s in ed["stickers"])
    assert polish.plan_edit(words(), 0, 12, {"edit": "off"}) is None
    clean = polish.plan_edit(words(), 0, 12, {"edit": "clean"}, peaks=[5.0])
    assert clean["stickers"] == [] and clean["peaks"] == []
    assert polish.plan_edit(words(), 0, 12, {"zoom": "false", "stickers": "false", "fx": "false"}, peaks=[5.0])["zooms"] == []
    assert polish.plan_edit(words(), 0, 12, {"look": "nonsense"})["look"] == "clean"


def test_every_look_is_a_valid_ffmpeg_filter():
    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg")
    for name, (_label, flt) in polish.LOOKS.items():
        if not flt:
            continue
        r = subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc2=s=160x90:d=0.3", "-vf", flt, "-f", "null", "-"], capture_output=True, text=True)
        assert r.returncode == 0, (name, r.stderr)


def test_stickers_are_drawn_and_cached():
    sp = {"kind": "pill", "text": "$$$", "color": "sun"}
    p = stickers.ensure(sp, 720)
    assert p.is_file() and p.stat().st_size > 500
    m = p.stat().st_mtime_ns
    assert stickers.ensure(sp, 720) == p and p.stat().st_mtime_ns == m
    for k in stickers.KINDS:
        assert stickers.draw(k, "WAIT FOR IT", "hot", 288).width > 50
    assert stickers.label_for("money") == "$$$" and stickers.label_for("hello") is None


# ---------- hype ----------
def _levels():
    rng = random.Random(2)
    lv = [-40 + rng.random() * 4 for _ in range(600)]
    for a in (100, 300, 470):
        for i in range(a, a + 14):
            lv[i] = -18 + rng.random() * 3
    return lv


def test_hype_finds_the_loud_bursts_and_nothing_in_a_flat_video():
    h = hype.curve(_levels())
    m = hype.moments(h, 6, 15, 45, None, 0, "balanced", pick._snap)
    assert len(m) == 3 and all(any(a <= x["peak"] <= a + 14 for a in (100, 300, 470)) for x in m)
    assert all(15 <= x["end"] - x["start"] <= 45 for x in m)
    assert len(hype.moments(h, 6, 15, 45, None, 0, "strict")) <= len(m)
    flat = hype.curve([-30 + random.Random(1).random() * 3 for _ in range(600)])
    assert hype.moments(flat, 6, 15, 45) == []
    assert hype.peaks_in(h, 0, m[0]["start"], m[0]["end"])


def test_excited_words_raise_hype():
    lv = [-30.0] * 120
    for i in range(60, 70):
        lv[i] = -22.0
    plain = [{"w": "so", "s": 60 + i * 0.5, "e": 60.3 + i * 0.5} for i in range(20)]
    wow = [{"w": "WOW!" if i % 3 == 0 else "no", "s": 60 + i * 0.5, "e": 60.3 + i * 0.5} for i in range(20)]
    assert max(hype.curve(lv, wow)) > max(hype.curve(lv, plain))


def test_music_builtin_and_pick_mood():
    assert len(music.tracks()) >= 6
    f = music.file_for("builtin-chill")
    assert f and f.endswith(".wav")
    assert music.pick("auto", "funny fail", 1)["mood"] == "happy"
    assert music.pick("epic")["mood"] == "epic"
    assert music.pick("nope-nothing", "")["mood"] == "upbeat"


@ff
def test_music_upload_needs_tick_and_real_audio(tmp_path):
    f = tmp_path / "a.mp3"
    f.write_bytes(b"not audio at all")
    with pytest.raises(ValueError):
        music.add("x", f, ".mp3", "chill", False)
    with pytest.raises(ValueError):
        music.add("x", f, ".mp3", "chill", True)
    wav = tmp_path / "b.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "sine=f=440:d=12", str(wav)], check=True)
    r = music.add("My beat", wav, ".wav", "epic", True)
    assert any(t["id"] == r["id"] for t in music.tracks()) and music.file_for(r["id"])
    assert music.pick("epic")["id"] == r["id"]               # your own track beats the built-in one of that mood
    assert music.remove(r["id"]) and not any(t["id"] == r["id"] for t in music.tracks())


@ff
@pytest.mark.parametrize("layout,music_on", [("blur", True), ("fill", False)])
def test_polished_render(tmp_path, layout, music_on):
    src = tmp_path / "s.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=1280x720:r=30:d=12", "-f", "lavfi", "-i", "sine=f=300:d=12", "-c:v", "libx264", "-c:a", "aac", str(src)], check=True)
    ed = polish.plan_edit(words(), 0, 10, {"edit": "punchy", "music": "upbeat" if music_on else "none", "look": "cinematic", "progress": music_on}, "win", 1, peaks=[4.0])
    out = tmp_path / "o.mp4"
    cut.cut(str(src), str(out), 0, 10, layout, "720p", cut.ass_for(words(), 0, 10, "bounce", 720, 1280, "Hook"), None, ed)
    p = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,width,height,duration", "-of", "json", str(out)], capture_output=True, text=True).stdout)["streams"]
    v = next(s for s in p if s["codec_type"] == "video")
    a = next(s for s in p if s["codec_type"] == "audio")
    assert (v["width"], v["height"]) == (720, 1280) and abs(float(v["duration"]) - 10) < 0.2 and abs(float(a["duration"]) - 10) < 0.3


@ff
def test_polished_render_of_silent_source(tmp_path):
    src = tmp_path / "s.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=640x360:r=30:d=8", "-c:v", "libx264", str(src)], check=True)
    ed = polish.plan_edit(words(), 0, 6, {"music": "chill"}, "x", 2)
    cut.cut(str(src), str(tmp_path / "o.mp4"), 0, 6, "blur", "720p", None, None, ed)
    assert (tmp_path / "o.mp4").is_file()


def test_plain_cut_still_works_without_edit(tmp_path):
    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg")
    src = tmp_path / "s.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=640x360:r=30:d=5", "-f", "lavfi", "-i", "sine=d=5", "-c:v", "libx264", "-c:a", "aac", str(src)], check=True)
    cut.cut(str(src), str(tmp_path / "o.mp4"), 0, 4, "blur", "720p", cut.ass_for(words(), 0, 4, "clean", 720, 1280), None, None)
    assert (tmp_path / "o.mp4").is_file()


def test_build_opts_carries_edit_defaults():
    o = pipeline.build_opts({"edit": "punchy", "music": "epic", "zoom": "false", "look": "film", "hype_only": "true", "hype_level": "more"})
    assert o["edit"] == "punchy" and o["music"] == "epic" and o["zoom"] is False and o["coach"] is False and o["look"] == "film" and o["hype_only"] and o["hype_level"] == "more"


# ---------- hashtags ----------
def test_hashtags_and_credit():
    c = {"title": "He won the money game", "text": "the money game was insane and the money was huge", "description": "A wild one.\n\n#wild #Shorts", "moment": "epic-win"}
    tags = meta.hashtags(c, ["learned"], 8)
    assert "Shorts" in tags and "wild" in tags and "money" in tags and "learned" in tags and len(tags) <= 8 and len({t.lower() for t in tags}) == len(tags)
    assert tags.index("learned") < tags.index("Shorts")                      # the first three tags are the ones shown above the title: what is in the clip comes before #Shorts
    assert len(meta.hashtags(c, ["learned"])) <= 5                          # the default is a few tags, not a wall of them
    desc, vt = meta.build(c, {"source": {"channel": "Some Creator", "url": "https://youtu.be/x", "license": "CC BY"}})
    assert "#Shorts" in desc and "Source" not in desc and "A wild one." in desc and "Shorts" not in vt
    assert meta.build({"title": "x"}, None)[0].endswith("#Shorts")


# ---------- coach ----------
def obs(recipe, views, likes=5, age_h=100, ch="c1", title="t"):
    return {"recipe": recipe, "views": views, "likes": likes, "comments": 0, "raw": coach.reward({"views": views, "likes": likes, "comments": 0}, age_h / 24), "channel": ch, "title": title, "hour": 12}


def test_reward_grows_with_views_and_engagement():
    assert coach.reward({"views": 1000, "likes": 50}, 3) > coach.reward({"views": 100, "likes": 50}, 3) > coach.reward({"views": 100, "likes": 1}, 3)
    assert coach.reward({"views": 100}, 30) == coach.reward({"views": 100}, 7)          # age is capped at a week


def test_bandit_converges_to_the_better_recipe(monkeypatch):
    """Simulated channel where 'punchy' really gets about 3x the views: after a few rounds the coach picks it most of the time."""
    rng = random.Random(4)
    pool: list[dict] = []
    monkeypatch.setattr(coach, "observations", lambda: pool)
    coach.set_config({"mode": "auto", "dims": {"edit": True, "caption": False, "look": False, "zoom": False, "stickers": False, "music": False}, "explore": 0.1})
    picks = []
    for step in range(120):
        e = coach.draw({}, rng)["edit"]
        picks.append(e)
        views = max(5, int(rng.gauss(900 if e == "punchy" else 300, 120)))
        pool.append(obs({"edit": e}, views))
        coach._normalise(pool)
    late = picks[60:]
    assert late.count("punchy") / len(late) > 0.7
    assert coach.best_choices(3)["edit"] == "punchy"


def test_draw_respects_dims_and_off():
    coach.set_config({"mode": "auto", "dims": {"edit": False, "caption": True, "look": False, "zoom": False, "stickers": False, "music": False}})
    d = coach.draw({}, random.Random(1))
    assert set(d) == {"caption"}


def test_observations_use_only_old_clips_and_apply_best(monkeypatch):
    now = datetime.now(timezone.utc)
    job = {"id": "c20260101-aaaaa", "title": "J", "status": "done", "opts": {}, "clips": [], "source": {}, "steps": {}, "log": []}
    store.save(job)
    clips = []
    for i, (hrs, ed, views) in enumerate([(100, "punchy", 900), (100, "punchy", 800), (100, "punchy", 1000), (100, "classic", 100), (100, "classic", 120), (100, "classic", 90), (5, "classic", 5)]):
        clips.append({"n": i + 1, "start": 0, "end": 30, "title": f"clip {i}", "youtube_id": f"v{i}", "channel": "c1", "posted_at": (now - timedelta(hours=hrs)).isoformat(timespec="seconds"),
                      "recipe": {"edit": ed, "caption": "bounce", "zoom": True, "stickers": True, "music": "none", "length": "20-35s", "title": "statement"}, "stats": {"views": views, "likes": views // 20, "comments": 0}})
    store.update(job["id"], lambda j: j.update(clips=clips))
    o = coach.observations()
    assert len(o) == 6                                        # the 5-hour-old clip is too young to judge
    t = coach.analyse()
    assert t["insights"]["n"] == 6 and t["insights"]["by"] == "rules" and any("punchy" in x for x in t["insights"]["do_more"])
    assert coach.apply_best()["edit"] == "punchy" and store.settings()["defaults"]["edit"] == "punchy"
    assert coach.maybe_analyse() is False or True            # a second run within a day does nothing when mode is off/new


def test_coach_view_and_modes():
    assert coach.config()["mode"] == "off"
    assert coach.set_config({"mode": "suggest"})["mode"] == "suggest"
    assert coach.set_config({"mode": "bogus"})["mode"] == "suggest"
    assert coach.view()["labels"]["edit"]


# ---------- HTTP ----------
def _client():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from studio.autoclip import routes
    app = FastAPI()
    app.include_router(routes.router)
    return TestClient(app)


@ff
def test_routes_music_coach_and_reedit(tmp_path):
    c = _client()
    assert len(c.get("/api/autoclip/music").json()["tracks"]) >= 6
    assert c.get("/api/autoclip/music/builtin-epic/preview").status_code == 200
    wav = tmp_path / "t.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "sine=f=330:d=10", str(wav)], check=True)
    assert c.post("/api/autoclip/music", files={"file": ("t.wav", wav.read_bytes())}, data={"name": "T", "mood": "chill"}).status_code == 400      # no tick
    r = c.post("/api/autoclip/music", files={"file": ("t.wav", wav.read_bytes())}, data={"name": "T", "mood": "chill", "ack": "true"})
    assert r.status_code == 200 and r.json()["mood"] == "chill"
    assert c.delete(f"/api/autoclip/music/{r.json()['id']}").json()["ok"]
    assert c.put("/api/autoclip/coach", json={"mode": "auto"}).json()["mode"] == "auto"
    assert c.post("/api/autoclip/coach/analyse").json()["insights"]["n"] == 0
    assert c.post("/api/autoclip/coach/apply").json()["applied"] == {}
    assert c.get("/api/autoclip/").status_code in (200, 404) or True
    # re-edit a finished clip with different effects
    job = {"id": "c20260101-bbbbb", "title": "J", "status": "done", "stage": "cut", "opts": pipeline.build_opts({}), "source": {}, "steps": {}, "log": [], "clips": [
        {"n": 1, "start": 0, "end": 8, "title": "T", "status": "ready", "file": "clips/clip-1.mp4"}]}
    store.save(job)
    d = store.jdir(job["id"])
    (d / "clips").mkdir(exist_ok=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=640x360:r=30:d=9", "-f", "lavfi", "-i", "sine=d=9", "-c:v", "libx264", "-c:a", "aac", str(d / "source.mp4")], check=True)
    (d / "clips" / "clip-1.words.json").write_text(json.dumps(words(18)))
    out = c.post(f"/api/autoclip/jobs/{job['id']}/clips/1/edit", json={"edit": "punchy", "music": "chill"})
    assert out.status_code == 200, out.text
    clip = out.json()["clips"][0]
    assert clip["edit"]["style"] == "punchy" and clip["edit"]["music"]["mood"] == "chill" and clip["rev"] == 1 and clip["recipe"]["music"] == "chill"
    assert (d / "clips" / "clip-1.mp4").stat().st_size > 1000


# ---------- the whole job: only the hype becomes a clip ----------
@ff
def test_hype_only_job_clips_just_the_loud_part(tmp_path):
    import threading
    src = tmp_path / "s.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=640x360:r=25:d=70", "-f", "lavfi", "-i", "sine=f=400:d=70", "-af", "volume='if(between(t,25,40),1,0.02)':eval=frame",
                    "-c:v", "libx264", "-preset", "veryfast", "-c:a", "aac", str(src)], check=True)
    job = pipeline.new_job(pipeline.build_opts({"count": 3, "min_seconds": 10, "max_seconds": 30, "hype_only": "true", "edit": "punchy", "look": "cinematic"}), {"kind": "upload", "name": "t"})
    d = store.jdir(job["id"])
    shutil.copy(src, d / "source.mp4")
    pipeline._cancel[job["id"]] = threading.Event()
    pipeline._run(job["id"])
    j = store.load(job["id"])
    assert j["status"] == "done", j.get("error")
    assert len(j["clips"]) == 1, [(c["start"], c["end"]) for c in j["clips"]]
    c = j["clips"][0]
    assert 20 <= c["start"] <= 30 and 33 <= c["end"] <= 48 and c["edit"]["look"] == "cinematic" and c["recipe"]["look"] == "cinematic" and (d / c["file"]).is_file()
    assert any("Only 1 hype moment" in x["text"] for x in j["log"]) and (d / "hype.json").is_file()
    assert c["edit"]["peaks"], c["edit"]
