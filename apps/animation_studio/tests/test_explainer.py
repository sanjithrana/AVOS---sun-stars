"""Explainer Studio: the plan contract, the shot router, captions, and the whole line (idea → final.mp4) on stand-ins
for the AI models (pictures from ffmpeg, voice from a sine tone), so no GPU, key or internet is needed."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from studio import config
from studio.explainer import captions, engines, pipeline, planner, router, spec, store
from studio.series import media

from .conftest import needs_ffmpeg


def project(**kw) -> dict:
    p = {"id": store.new_id(), "brief": "Why can a straw go through a potato?", "title": "x", "seconds": 24, "aspect": "9:16", "language": "en",
         "crew": "builtin", "auto": True, "style": "", "voice": "male", "models": {}, "status": "working", "stage": "plan", "plan": None,
         "assets": {}, "log": [], "createdAt": store.now(), "updatedAt": store.now()}
    p.update(kw)
    return store.save(p)


# ---------- the contract ----------
def test_builtin_plan_is_valid_and_fits_the_length():
    s = {"brief": "Why can a straw go through a potato?", "seconds": 30, "aspect": "9:16", "language": "en", "id": "x1", "crew": "builtin"}
    plan = planner.plan(s)
    assert len(plan["shots"]) >= 5 and plan["characters"] and plan["props"]
    assert abs(spec.total_seconds(plan) - 30) < 8
    assert [x["id"] for x in plan["shots"]] == [f"S{i:02d}" for i in range(1, len(plan["shots"]) + 1)]
    assert any(x["shot_type"] == "scientific_cutaway" and x["visualization"]["force_arrows"] for x in plan["shots"])


def test_norm_plan_cleans_an_ai_answer():
    data = {"characters": [{"name": "Dr Pop"}], "props": ["potato"], "shots": [
        {"shot_type": "NOPE", "seconds": 99, "narration": "hi", "characters": ["ghost", "dr-pop"], "props": ["potato", "zzz"], "camera": {"type": "weird"}},
        {"shot_type": "scientific cutaway", "seconds": 0, "narration": ""}]}
    plan = spec.norm_plan(data, 20)
    a, b = plan["shots"]
    assert a["shot_type"] == "demonstration" and a["seconds"] <= spec.MAX_SHOT and a["characters"] == ["dr-pop"] and a["props"] == ["potato"]
    assert a["camera"]["type"] == "medium"
    assert b["shot_type"] == "scientific_cutaway" and b["seconds"] >= spec.MIN_SHOT and b["visualization"]["cross_section"]
    with pytest.raises(ValueError):
        spec.norm_plan({"characters": [], "shots": []}, 20)
    with pytest.raises(ValueError):
        spec.norm_plan({"characters": [{"name": "A"}], "shots": [{}]}, 20)


def test_a_long_narration_gets_enough_seconds():
    shot = spec.norm_shot({"narration": "x" * 140, "seconds": 2}, 0, {"characters": set(), "props": set()})
    assert shot["seconds"] >= 8.0 - 0.01 or shot["seconds"] == spec.MAX_SHOT


# ---------- the router ----------
CAPS_ALL, CAPS_NONE = {"ai_video": True, "blender": True}, {"ai_video": False, "blender": False}


def test_router_chooses_per_shot():
    cut = {"shot_type": "scientific_cutaway", "characters": [], "physics": True}
    person = {"shot_type": "presenter", "characters": ["h"]}
    assert router.route(cut, CAPS_ALL)[0] == "blender"
    assert router.route(person, CAPS_ALL)[0] == "ai_video"
    assert router.route(cut, {"ai_video": True, "blender": False})[0] == "ai_video"
    assert router.route(person, {"ai_video": False, "blender": True})[0] == "blender"
    assert router.route(person, CAPS_NONE)[0] == "still"
    assert router.route({**person, "force": "blender"}, CAPS_ALL) == ("blender", "chosen by you")
    assert router.route({**person, "force": "blender"}, CAPS_NONE)[0] == "still"        # never a forced engine that isn't there


def test_blender_scene_is_a_plain_validated_spec():
    p = {"plan": {"props": [{"id": "potato", "name": "Potato", "look": "a brown potato"}, {"id": "straw", "name": "Straw", "look": "red bendy straw"}]}}
    shot = {"index": 3, "shot_type": "scientific_cutaway", "characters": [], "props": ["potato", "straw"],
            "camera": {"type": "cutaway", "movement": "orbit", "lens_mm": 50}, "visualization": {"cross_section": True, "force_arrows": True}}
    sc = engines.scene_spec(p, shot, 4.0, 720, 1280)
    assert sc["actors"] == [] and len(sc["props"]) == 2 and sc["props"][0]["type"] == "sphere" and sc["props"][0]["color"] == "#8a5a2b"
    assert sc["camera"] == {"shot": "close", "move": "orbit", "target": ""}
    json.dumps(sc)


# ---------- captions ----------
def test_captions_cover_the_line_two_words_at_a_time():
    rows = captions.chunks("Look closely at what we are using", 1.0, 4.0)
    assert [r[2] for r in rows] == ["Look closely", "at what", "we are", "using"]
    assert rows[0][0] == 1.0 and abs(rows[-1][1] - 4.0) < 0.01 and all(a < b for a, b, _ in rows)
    out = captions.ass(rows, 720, 1280)
    assert out.count("Dialogue:") == 4 and "LOOK CLOSELY" in out and "PlayResY: 1280" in out


# ---------- the whole line, on stand-ins ----------
def _png(path: Path) -> bytes:
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=360x640:d=1", "-frames:v", "1", str(path)], check=True)
    return path.read_bytes()


@pytest.fixture()
def standins(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "ROOT", tmp_path / "explainer")
    png = _png(tmp_path / "k.png")
    monkeypatch.setattr(media, "_t2i", lambda prompt, w, h, seed, prefer=None, s=None: (png, "standin-image"))
    monkeypatch.setattr(media, "picture", lambda prompt, refs, w, h, seed, tag, priority=5, s=None, negative=None: (png, {"model": "standin-image"}))
    def say(text, voice, emotion="neutral"):
        out = tmp_path / "v.wav"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"sine=f=300:d={max(1.0, len(text) / 14):.2f}", "-ar", "24000", "-ac", "1", str(out)], check=True)
        return out.read_bytes()
    monkeypatch.setattr(media, "edge_say", say)
    monkeypatch.setattr(media, "music", lambda s, cue, seconds, tag: (None, {"model": None}))
    monkeypatch.setattr(engines, "capabilities", lambda s: {"ai_video": False, "blender": False, "lipsync": False})
    return tmp_path


@needs_ffmpeg
def test_idea_to_final_video(standins):
    p = project()
    pipeline._cancel[p["id"]] = __import__("threading").Event()
    pipeline._run(p["id"], "plan")
    q = store.load(p["id"])
    assert q["status"] == "done", q.get("error")
    assert all(s["engine"] == "still" and s.get("clip") for s in q["plan"]["shots"])
    fin = store.pdir(p["id"]) / "final.mp4"
    probe = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type,width,height", "-of", "json", str(fin)],
                                      capture_output=True, text=True).stdout)
    kinds = {s["codec_type"] for s in probe["streams"]}
    assert {"video", "audio"} <= kinds
    v = next(s for s in probe["streams"] if s["codec_type"] == "video")
    assert (v["width"], v["height"]) == (720, 1280)
    assert abs(float(probe["format"]["duration"]) - q["finalSeconds"]) < 1.0
    assert (store.pdir(p["id"]) / "final.srt").read_text("utf-8").strip()


@needs_ffmpeg
def test_gates_stop_for_approval_and_continue(standins):
    p = project(auto=False)
    pipeline._cancel[p["id"]] = __import__("threading").Event()
    pipeline._run(p["id"], "plan")
    q = store.load(p["id"])
    assert (q["status"], q["stage"]) == ("waiting", "plan") and pipeline.next_stage(q) == "design"
    pipeline._run(p["id"], pipeline.next_stage(q))
    q = store.load(p["id"])
    assert (q["status"], q["stage"]) == ("waiting", "design") and pipeline.next_stage(q) == "board"     # characters and backgrounds are approved before the storyboard
    assert q["assets"].get("world") and not any(s.get("frame") for s in q["plan"]["shots"])
    pipeline._run(p["id"], pipeline.next_stage(q))
    q = store.load(p["id"])
    assert (q["status"], q["stage"]) == ("waiting", "board") and all(s.get("frame") for s in q["plan"]["shots"])
    pipeline._run(p["id"], pipeline.next_stage(q))
    assert store.load(p["id"])["status"] == "done"


@needs_ffmpeg
def test_a_failure_is_kept_and_continue_skips_finished_work(standins, monkeypatch):
    p = project()
    pipeline._cancel[p["id"]] = __import__("threading").Event()
    calls = {"n": 0}
    real = media.picture
    def flaky(*a, **k):
        calls["n"] += 1
        if calls["n"] == 7:              # design draws the sheet and the key visual from the portrait (2), then each shot a first and a last frame: shot 3 fails
            raise RuntimeError("provider down")
        return real(*a, **k)
    monkeypatch.setattr(media, "picture", flaky)
    pipeline._run(p["id"], "plan")
    q = store.load(p["id"])
    assert q["status"] == "error" and "provider down" in q["error"] and q["stage"] == "board"
    done = [s for s in q["plan"]["shots"] if s.get("frame")]
    assert len(done) == 2
    monkeypatch.setattr(media, "picture", real)
    pipeline._run(p["id"], q["stage"])
    assert store.load(p["id"])["status"] == "done"


def test_recover_marks_interrupted_projects(standins):
    p = project(status="working")
    pipeline.recover()
    q = store.load(p["id"])
    assert q["status"] == "error" and "restarted" in q["error"]


@needs_ffmpeg
def test_pictures_are_tied_to_prompt_versions_and_your_rating_is_learned(standins):
    from studio.explainer import prompts
    p = project()
    pipeline._cancel[p["id"]] = __import__("threading").Event()
    pipeline._run(p["id"], "plan")
    q = store.load(p["id"])
    shot = q["plan"]["shots"][0]
    assert shot["pk"] and all(isinstance(v, int) for _, v in shot["pk"]) and shot["qhash"] is not None
    items = {i["key"]: i for i in prompts.library()["items"]}
    assert items["picture.base"]["active"]["uses"] >= len(q["plan"]["shots"])
    assert pipeline.rate_shot(p["id"], shot["id"], False, "the hands are wrong")
    assert not pipeline.rate_shot(p["id"], shot["id"], True)                      # one rating per picture
    after = {i["key"]: i for i in prompts.library()["items"]}
    assert after["picture.base"]["active"]["down"] == 1
    assert store.load(p["id"])["plan"]["shots"][0]["rating"] == "down"


# ---------- Autopilot ----------
def _go(pid, start="plan"):
    pipeline._cancel[pid] = __import__("threading").Event()
    pipeline._run(pid, start)
    return store.load(pid)


def _lib(key):
    from studio.explainer import prompts
    it = next(i for i in prompts.library()["items"] if i["key"] == key)
    return it["active"]


@needs_ffmpeg
def test_a_speaking_shot_gets_the_characters_voice_and_lipsync_and_falls_back_when_it_fails(standins, monkeypatch):
    seen = {}
    monkeypatch.setattr(engines, "capabilities", lambda s: {"ai_video": False, "blender": False, "lipsync": True})
    real = media.edge_say
    def say(text, voice, emotion="neutral"):
        seen.setdefault("voices", []).append(voice.get("edge"))
        return real(text, voice, emotion)
    monkeypatch.setattr(media, "edge_say", say)
    p = project(auto=False, voice_id="en-US-GuyNeural")
    q = _go(p["id"])
    def speak(x):
        x["plan"]["characters"].append({"id": "mia", "name": "Mia", "look": "a girl, she wears a red coat", "voice": "bright, female", "role": "supporting"})
        x["plan"]["shots"][1]["speaker"] = "mia"
        x["plan"]["shots"][1]["characters"] = ["mia"]
    store.update(p["id"], speak)
    calls = []
    def lip(s, shot, key, line, seconds, seed, tag, prompt):
        calls.append(shot["id"])
        raise RuntimeError("no credit")
    monkeypatch.setattr(engines, "lipsync", lip)
    q = _go(p["id"], "design")
    q = _go(p["id"], "board")
    q = _go(p["id"], "shoot")
    assert q["status"] == "done", q.get("error")
    sh = q["plan"]["shots"][1]
    assert calls == [sh["id"]] and sh["engine"] == "still" and sh["clip"]                      # lip-sync failed → still made normally
    assert sh["voice"].get("speaker") == "mia" and sh["voice"]["voice"] != "en-US-GuyNeural"    # her own voice, not the narrator's
    assert any("Lip-sync" in l.get("text", "") for l in q["log"])


@needs_ffmpeg
def test_lipsync_clip_is_used_when_a_model_works(standins, monkeypatch):
    monkeypatch.setattr(engines, "capabilities", lambda s: {"ai_video": False, "blender": False, "lipsync": True})
    p = project(auto=False)
    q = _go(p["id"], "plan")
    def speak(x):
        x["plan"]["shots"][0]["speaker"] = x["plan"]["characters"][0]["id"]
        x["plan"]["shots"][0]["characters"] = [x["plan"]["characters"][0]["id"]]
    pipeline._cancel[p["id"]] = __import__("threading").Event()
    store.update(p["id"], speak)
    from studio.explainer import skills
    def lip(s, shot, key, line, seconds, seed, tag, prompt):
        assert line[:4] == b"RIFF"
        return engines.still(s, shot, key, seconds)[0], {"model": "infinitetalk", "engine": "lipsync", "fallback": False}
    monkeypatch.setattr(engines, "lipsync", lip)
    _go(p["id"], "design")
    _go(p["id"], "board")
    q = _go(p["id"], "shoot")
    assert q["status"] == "done", q.get("error")
    assert q["plan"]["shots"][0]["engine"] == "lipsync" and next(x for x in skills.listing() if x["id"] == "lipsync")["ok"] >= 1


def test_skills_can_be_switched_and_always_on_ones_cannot():
    from studio.explainer import skills
    assert skills.on("lipsync")
    skills.set_on("lipsync", False)
    assert not skills.on("lipsync") and not next(x for x in skills.listing({}) if x["id"] == "lipsync")["on"]
    skills.set_on("lipsync", True)
    with pytest.raises(ValueError):
        skills.set_on("script", False)
    with pytest.raises(KeyError):
        skills.set_on("nope", True)
    skills.tick("voice", False, "offline")
    v = next(x for x in skills.listing({}) if x["id"] == "voice")
    assert v["fail"] >= 1 and v["last_error"] == "offline"
    assert [x["id"] for x in skills.listing({})][:3] == ["research", "script", "characters"]


@needs_ffmpeg
def test_your_ok_and_your_redo_teach_the_prompts(standins):
    p = project(auto=False)
    q = _go(p["id"])
    q = _go(p["id"], pipeline.next_stage(q))                       # design: waiting for your OK
    assert q["stage"] == "design" and q["asset_pk"]["char:" + q["plan"]["characters"][0]["id"]]
    before = _lib("sheet.character")
    key = "char:" + q["plan"]["characters"][0]["id"]
    old_rel = q["assets"][key]
    assert pipeline.redo_asset(p["id"], key, "make her face friendlier")
    pipeline._threads[p["id"]].join(30)
    q = store.load(p["id"])
    mid = _lib("sheet.character")
    assert mid["flags"] is not None and mid["uses"] > before["uses"]
    assert q["asset_ver"][key] == 1 and q["assets"][key] and q["status"] == "waiting" and q["stage"] == "design"
    assert not q["asset_ok"] or key not in q["asset_ok"]
    pipeline.on_approve(p["id"])
    after = _lib("sheet.character")
    assert after["up"] >= mid["up"]
    q = store.load(p["id"])
    assert "world" in q["asset_ok"] and key in q["asset_ok"]


# ---------- film language ----------
def test_shots_carry_the_full_cinematic_template_and_name_what_is_missing():
    from studio.explainer import cinema
    plan = spec.norm_plan({"characters": [{"name": "Dave"}], "props": [], "shots": [
        {"shot_type": "reaction", "narration": "Not again.", "action": "Dave checks left, right and under a parked car, shoulders tight, breathing fast.",
         "objective": "make sure the pigeon is gone", "angle": "low_angle", "composition": "blocking", "performance": "eyes dart, relief after one beat",
         "end_state": "Dave steps out, smiling", "continuity": "same green coat, same street", "lighting": "warm morning sun", "scene_title": "Home", "camera_note": "slow 1 m push-in over 3 s"},
        {"shot_type": "presenter", "angle": "nonsense", "narration": "x"}]}, 20)
    a, b = plan["shots"]
    assert a["angle"] == "low_angle" and a["composition"] == "blocking" and a["end_state"] and a["continuity"]
    assert "end_state" not in a["gaps"] and "continuity" not in a["gaps"] and "angle" not in a["gaps"]
    assert b["angle"] == "eye_level" and b["composition"] == "center"                       # a bad word falls back to the right default for the shot type
    assert {"objective", "end_state", "continuity", "lighting"} <= set(b["gaps"])
    assert any("low-angle" in x for x in cinema.phrases(a))


def test_the_pictures_and_the_motion_use_the_film_fields():
    plan = spec.norm_plan({"characters": [{"name": "Dave", "look": "tall man in a green coat"}], "props": [], "shots": [
        {"shot_type": "reaction", "action": "Dave looks up in dread at the pigeon on the statue", "angle": "high_angle", "composition": "negative_space",
         "performance": "jaw drops, eyes widen", "end_state": "Dave frozen, mouth open", "continuity": "same green coat", "objective": "escape the pigeon", "seconds": 4},
        {"shot_type": "result", "action": "the pigeon celebrates", "seconds": 3}]}, 8)
    p = {"id": "a1", "plan": plan}
    pic = engines.shot_prompt(p, plan["shots"][0])
    assert "looking down at the subject" in pic and "vast empty space" in pic and "performance: jaw drops" in pic
    mov = engines.animation_prompt(p, plan["shots"][0])
    assert "End exactly on: Dave frozen" in mov and "Keep unchanged: same green coat" in mov and "trying to: escape the pigeon" in mov


def test_master_prompt_is_one_timed_multi_shot_prompt_with_strict_rules():
    from studio.explainer import master
    plan = spec.norm_plan({"title": "The pigeon", "logline": "A man is hunted by a pigeon over one fry.", "characters": [{"id": "dave", "name": "Dave", "look": "tall man, green coat"}],
        "props": [{"name": "Fry", "look": "one golden french fry"}], "shots": [
        {"shot_type": "reaction", "scene": 1, "scene_title": "Home", "seconds": 4, "action": "Dave checks every direction", "characters": ["dave"], "speaker": "dave",
         "narration": "Not again.", "emotion": "dread", "end_state": "Dave steps outside", "lighting": "cold morning light"},
        {"shot_type": "result", "scene": 2, "scene_title": "Park", "seconds": 5, "action": "a fry falls at his feet", "props": ["fry"], "narration": ""}]}, 9)
    p = {"id": "m1", "plan": plan, "aspect": "16:9"}
    t = master.build(p)
    assert "0–4 SEC — HOME" in t and "4–9 SEC — PARK" in t and "CHARACTERS" in t and "SETTING AND PROPS" in t and "STRICT RULES" in t
    assert "Dave (dread): “Not again.”" in t and "End on: Dave steps outside." in t and "(1 line)" in t and "AUDIO" in t and "VISUAL DIRECTION" in t
    assert "Minimal dialogue and no narration." in t and "PART" not in t
    assert "PARK" not in master.build(p, scene=1) and master.build(p, scene=9) == ""
    long = master.parts(p, limit=6)                        # longer than one generation: split at shots, part 2 continues seamlessly
    assert len(long) == 2 and long[0].startswith("PART 1 OF 2") and "Continue seamlessly" in long[1] and "Dave" in long[1].split("CHARACTERS")[1]


def test_story_and_cinema_rules_reach_the_script_writer(monkeypatch):
    from studio.series import writers
    seen = {}
    monkeypatch.setattr(writers, "uses_ai", lambda s: True)
    def ask(s, kind, system, prompt, log=None, **k):
        seen["prompt"] = prompt
        return None
    monkeypatch.setattr(writers, "ask", ask)
    planner.plan({"id": "z1", "brief": "A funny chase: a man runs from a pigeon", "seconds": 20, "aspect": "9:16", "language": "en", "crew": "builtin"})
    assert "all 14 fields" in seen["prompt"] and "false hope" in seen["prompt"] and "low_angle" in seen["prompt"]
    planner.plan({"id": "z2", "brief": "How a straw goes through a potato", "seconds": 20, "aspect": "9:16", "language": "en", "crew": "builtin"})
    assert "all 14 fields" in seen["prompt"] and "false hope" not in seen["prompt"]


# ---------- cast memory, staged boards, key poses, the crew ----------
@needs_ffmpeg
def test_every_shot_gets_a_last_frame_level_boards_and_a_keypose_clip(standins):
    p = project()
    pipeline._cancel[p["id"]] = __import__("threading").Event()
    pipeline._run(p["id"], "plan")
    q = store.load(p["id"])
    assert q["status"] == "done", q.get("error")
    shots = [s for s in q["plan"]["shots"] if s["shot_type"] != "establishing"]
    assert all(s.get("end_frame") for s in shots)
    assert all(s["info"].get("mode") == "keypose" for s in shots)
    b = q["boards"]
    assert set(b["cast"]) == {c["id"] for c in q["plan"]["characters"]} and b["world"] and b["scenes"] and set(b["clips"]) == {s["id"] for s in q["plan"]["shots"]}
    assert all((store.pdir(p["id"]) / r).is_file() for r in [*b["cast"].values(), b["world"], *b["scenes"].values(), *b["clips"].values()])
    assert all(q["assets"].get(f"ref:{c['id']}") for c in q["plan"]["characters"])          # a clean identity portrait per character


@needs_ffmpeg
def test_the_cast_is_remembered_and_reused_in_the_next_video(standins, monkeypatch):
    from studio.explainer import agents, memory
    p = project()
    pipeline._cancel[p["id"]] = __import__("threading").Event()
    pipeline._run(p["id"], "plan")
    q = store.load(p["id"])
    host = q["plan"]["characters"][0]
    m = memory.find(host["name"])
    assert m and m["look"] == host["look"] and m["portrait"] and m["sheet"] and p["id"] in m["projects"]
    drawn: list[str] = []
    real = media._t2i
    monkeypatch.setattr(media, "_t2i", lambda prompt, w, h, seed, prefer=None, s=None: (drawn.append(prompt), real(prompt, w, h, seed))[1])
    p2 = project()
    pipeline._cancel[p2["id"]] = __import__("threading").Event()
    pipeline._run(p2["id"], "plan")
    q2 = store.load(p2["id"])
    c2 = q2["plan"]["characters"][0]
    assert c2.get("memory") == m["id"] and c2["look"] == m["look"]
    assert not any(host["name"] in d and ("design sheet" in d or "Identity reference" in d) for d in drawn)   # copied from memory, not redrawn
    assert any("cast memory" in (l["text"] or "").lower() for l in q2["log"])
    view = {"agents": agents.status(q2, lambda rel: pipeline._have(p2["id"], rel))}
    names = [a["id"] for a in view["agents"]]
    assert {"writer", "director", "memory", "casting", "board", "keys", "continuity", "boards", "voice", "animator", "editor"} <= set(names)
    mem = next(a for a in view["agents"] if a["id"] == "memory")
    assert host["name"] in mem["output"]


def test_picture_prompt_leads_with_the_shot_and_locks_the_character():
    plan = spec.norm_plan({"characters": [{"name": "Mia", "look": "girl with a yellow raincoat and red boots"}], "props": [], "shots": [
        {"shot_type": "demonstration", "action": "Mia drops a magnet into a copper pipe", "end_state": "the magnet floats slowly inside the pipe", "seconds": 4, "characters": ["mia"]},
        {"shot_type": "result", "action": "the magnet lands", "seconds": 3}]}, 8)
    p = {"id": "a2", "plan": plan}
    first = engines.shot_prompt(p, plan["shots"][0])
    last, _ = engines.end_prompt(p, plan["shots"][0])
    assert first.startswith(engines.STYLE) and "Medium shot of Mia: Mia drops a magnet" in first[:400]      # the look survives a 900-character cut
    assert "exactly one, identical to the reference" in first
    assert "final moment of the shot: the magnet floats slowly" in last and "same camera position" in last
    mov = engines.animation_prompt(p, plan["shots"][0])
    assert mov.startswith("Slow push-in as Mia drops a magnet") and "real weight" in mov


@needs_ffmpeg
def test_shot_pack_out_and_your_clip_back_in(standins, tmp_path):
    import zipfile, io as _io
    p = project()
    pipeline._cancel[p["id"]] = __import__("threading").Event()
    pipeline._run(p["id"], "plan")
    z = zipfile.ZipFile(_io.BytesIO(pipeline.shot_pack(p["id"])))
    names = z.namelist()
    assert "README.txt" in names and any(n.endswith("/first.png") for n in names) and any(n.endswith("/motion.txt") for n in names)
    assert any(n.startswith("characters/") and n.endswith("_portrait.png") for n in names)
    clip = tmp_path / "mine.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=640x360:d=3", "-pix_fmt", "yuv420p", str(clip)], check=True)
    sid = store.load(p["id"])["plan"]["shots"][0]["id"]
    pipeline.use_clip(p["id"], sid, clip.read_bytes())
    pipeline._threads[p["id"]].join(120)
    q = store.load(p["id"])
    s = next(x for x in q["plan"]["shots"] if x["id"] == sid)
    assert s["engine"] == "upload" and s["clip"].endswith("_yours.mp4") and q["status"] == "done"


def test_free_pictures_send_the_seed_size_and_references(monkeypatch):
    from studio.render import images
    sent = {}
    class R:
        status_code = 200
        headers = {"content-type": "image/png"}
        content = b"PNG" * 1000
        text = ""
    def post(url, headers=None, files=None, timeout=None, **kw):
        sent.update(url=url, files=files)
        return R()
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "a"); monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "t")
    monkeypatch.setattr(images.httpx, "post", post)
    png = subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=red:s=900x900:d=1", "-frames:v", "1", "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True, check=True).stdout
    out = images.free_picture("a cat", 720, 1280, 1234, [png])
    assert out and "flux-2-klein" in sent["url"] and "input_image_0" in sent["files"]
    assert sent["files"]["seed"] == (None, "1234") and sent["files"]["width"] == (None, "720") and sent["files"]["height"] == (None, "1280")
