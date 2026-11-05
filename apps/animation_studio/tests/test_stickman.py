"""Stickman Studio: the contracts, the prompt compiler (identity paragraphs verbatim, word ranges, four timed beats), the continuity
checks, and the whole line (event → six ten-second clips → final.mp4 + the written package) with a stand-in AI writer and stand-in media."""
from __future__ import annotations

import copy
import json
import re
import subprocess
import threading
from pathlib import Path

import pytest

from studio.explainer import engines
from studio.series import media, writers
from studio.stickman import continuity, package, pipeline, planner, prompts, spec, store, styles

from .conftest import needs_ffmpeg

REAL_ASK = writers.ask

TOPICS = {"topics": [{"title": f"Event {i}", "date_place": f"{1800 + i}, Somewhere", "premise": "A thing happened.", "opening_visual": "a stickman stares",
                      "conflict": "x vs y", "ending": "it ended", "duration_s": 60, "clips": 6, "difficulty": "easy"} for i in range(8)], "recommended": 2, "why": "visual"}
BRIEF = {"event": "Event 2", "date": "1802", "location": "Somewhere", "people": ["A person"], "cause": "c", "turning_point": "t", "outcome": "o",
         "facts": [{"claim": "It happened in 1802.", "confidence": "well-established"}, {"claim": "A number is disputed.", "confidence": "check"}],
         "disputed": ["the count"], "sources_to_check": ["a national archive"], "dramatization_notes": ["the crowd is generic"]}
ROSTER = {"characters": [
    {"name": "Ada", "role": "lead", "age_presentation": "adult", "head_shape": "round", "height_heads": 5, "eyes": "dot eyes", "hair_or_headwear": "a tall red hat with a notch",
     "clothing": "long blue coat over a white shirt", "footwear": "black boots", "accents": [{"name": "coat blue", "hex": "#2a5db0"}, {"name": "hat red", "hex": "c0392b"}],
     "signature_prop": "a brass lantern", "distinguishing_feature": "notched hat"},
    {"name": "Bo", "role": "rival", "head_shape": "oval", "height_heads": 5.5, "hair_or_headwear": "flat cap", "clothing": "brown waistcoat", "accents": [{"name": "waistcoat brown", "hex": "#7b4a2a"}],
     "signature_prop": "a ledger", "distinguishing_feature": "one raised eyebrow"}]}


def story(n):
    return {"title": "Event Two", "hook": "h", "clips": [{"purpose": f"purpose {i}", "narration": " ".join(["word"] * 20), "main_action": f"action {i}"} for i in range(n)]}


def clip(n):
    holds = "a brass lantern" if n < 6 else "nothing"
    return {"location": "a river street", "time_of_day": "dusk", "scenery": "brick houses and a river", "framing": "medium wide", "camera_angle": "eye level",
            "foreground": "cobbles", "middle": "the characters", "background": "pale houses",
            "chars": [{"id": "CHAR_01", "position": "left third", "facing": "right", "pose": "standing", "expression": "worried", "clothing_state": "as designed", "prop_grip": "a brass lantern"},
                      {"id": "CHAR_02", "position": "right third", "facing": "left", "pose": "arms folded", "expression": "neutral", "clothing_state": "as designed", "prop_grip": "a ledger"}],
            "opening_setup": "Ada holds the lantern up while Bo waits by the wall.",
            "beats": {"setup": "Ada raises the lantern.", "escalation": "Bo steps forward and points at the river; Ada steps back, shocked.", "payoff": "They both look at the water."},
            "camera_move": "slow push in", "prop_interaction": "Ada holds the lantern in her left hand", "sfx": ["footsteps", "water"], "music": "quiet strings",
            "final_state": {"summary": "Both look at the water.", "chars": [{"id": "CHAR_01", "position": "left third", "facing": "right", "holds": holds, "emotion": "worried"},
                                                                      {"id": "CHAR_02", "position": "right third", "facing": "left", "holds": "a ledger", "emotion": "grim"}]},
            "transition": "match", "transition_note": ""}


def fake_ask(s, who, system, prompt, log=None, **kw):
    if "EIGHT specific" in system or "EIGHT specific video ideas" in system:
        return copy.deepcopy(TOPICS)
    if "fact brief" in system:
        return copy.deepcopy(BRIEF)
    if re.search(r"exactly \d+ clips", system):
        return story(int(re.search(r"exactly (\d+) clips", system).group(1)))
    if "smallest cast" in system:
        return copy.deepcopy(ROSTER)
    if "continuity bible" in system:
        return {"premise": "p", "theme": "t", "layout": "a narrow street; the alley opens on the right; a low streetlight behind three boxes",
                "props": [{"name": "lantern", "look": "one small hexagonal amber lantern", "rule": "always in the left hand"}],
                "visual_logic": ["the shadow stays connected to the cat and the boxes"], "music": "soft felt piano"}
    m = re.search(r"Direct clip (\d+) of", system)
    if m:
        return clip(int(m.group(1)))
    raise AssertionError("unexpected prompt: " + system[:80])


def roster():
    return spec.norm_roster(ROSTER)


def project(**kw):
    p = {"id": store.new_id(), "title": "Event Two", "event": "Event Two", "interest": "", "aspect": "9:16", "language": "en", "crew": "groq", "auto": True, "tone": "clear", "voice": "male",
         "models": {}, "status": "working", "stage": "topics", "clip_count": 6, "seconds": 60, "topics": None, "project": None, "brief": None, "story": None, "roster": None, "clips": [], "assets": {},
         "log": [], "createdAt": store.now(), "updatedAt": store.now()}
    p.update(kw)
    return p


# ---------- contracts ----------
def test_topics_are_cleaned_and_the_builtin_list_is_real():
    t = spec.norm_topics(TOPICS)
    assert len(t["topics"]) == 8 and t["recommended"] == 2
    with pytest.raises(ValueError):
        spec.norm_topics({"topics": [{"title": "a"}]})
    ex = planner.topics({"crew": "builtin", "id": "x1"})
    assert len(ex["topics"]) == 8 and len({x["title"] for x in ex["topics"]}) == 8 and all(x["date_place"] and x["opening_visual"] for x in ex["topics"])


def test_brief_never_claims_to_be_verified():
    b = spec.norm_brief(BRIEF)
    assert b["verification"] == "pending" and b["facts"][1]["confidence"] == "check" and not any("http" in x for x in b["sources_to_check"])
    with pytest.raises(ValueError):
        spec.norm_brief({"facts": []})


def test_roster_gets_ids_hex_and_defaults():
    r = roster()
    assert [c["id"] for c in r] == ["CHAR_01", "CHAR_02"] and r[0]["accents"][1]["hex"] == "#c0392b" and r[1]["eyes"] == "two black dot eyes"


def test_clip_plan_needs_three_timed_beats_and_a_known_character():
    ids = {"CHAR_01", "CHAR_02"}
    assert spec.norm_clip(clip(1), 1, ids, None)["t1"] == 10
    old = clip(1)                                         # a plan written with the older four beats still loads
    old["beats"] = {"hook": "a", "main": "b", "reaction": "c", "outcome": "d"}
    assert spec.norm_clip(old, 1, ids, None)["beats"] == {"setup": "a b", "escalation": "c", "payoff": "d"}
    bad = clip(1)
    bad["beats"]["escalation"] = ""
    with pytest.raises(ValueError):
        spec.norm_clip(bad, 1, ids, None)
    bad = clip(1)
    bad["chars"] = [{"id": "GHOST"}]
    with pytest.raises(ValueError):
        spec.norm_clip(bad, 1, ids, None)


# ---------- prompts ----------
def full_project():
    p = project(project={"title": "Event Two", "date_place": "1802, Somewhere", "premise": "", "tone": "clear"}, brief=spec.norm_brief(BRIEF),
                story=spec.norm_story(story(6), 6), roster=roster())
    prev = None
    for n in range(1, 7):
        c = pipeline.compile_clip(p, {**spec.norm_clip(clip(n), n, {"CHAR_01", "CHAR_02"}, prev)}) if False else spec.norm_clip(clip(n), n, {"CHAR_01", "CHAR_02"}, prev)
        p["clips"].append(c)
        prev = c["outgoing"]
    for c in p["clips"]:
        pipeline.compile_clip(p, c)
    return p


def test_prompts_follow_the_director_contract():
    p = full_project()
    c = p["clips"][2]
    for ch in p["roster"]:
        assert prompts.identity(ch, p) in c["scene_prompt"] and prompts.identity(ch, p) in c["animation_prompt"] and prompts.identity(ch, p) in prompts.sheet_prompt(p, ch)
    a = c["animation_prompt"]
    for window in ("[0-3s]", "[3-7s]", "[7-10s]"):
        assert window in a
    assert styles.voice_block(p) in a and styles.voice_block(p) in p["clips"][0]["animation_prompt"]                # the frozen voice, verbatim, in every clip
    assert "seamlessly continues the identical" in a and "seamlessly continues" not in p["clips"][0]["animation_prompt"]  # clip 1 sets the music, later clips continue it
    assert "strictly no speech bubbles" in a and f'"{p["story"]["clips"][2]["narration"]}"' in a
    assert not re.search(r"#[0-9a-fA-F]{6}", a + c["scene_prompt"])                                               # never hex in a generation prompt
    assert "FIRST FRAME" in c["scene_prompt"] and "BEFORE the main action" in c["scene_prompt"] and "FINAL FRAME at 10 s" in a
    assert "Row 2: expression studies - neutral, happy, worried, shocked, angry, determined" in prompts.sheet_prompt(p, p["roster"][0])
    pop = dict(p, style="a2-tech")                                                                                 # a fixed-character style: the lead IS the tested anchor
    assert "bright red beanie" in prompts.identity(p["roster"][0], pop) and "no circuit board textures" in prompts.animation_prompt(pop, c)


def test_the_consistency_agent_prompt_is_standalone_and_filled_in():
    p = full_project()
    t = prompts.consistency_prompt(p)
    assert t.startswith("CHARACTER CONSISTENCY AGENT INSTRUCTIONS") and "character and visual continuity supervisor" in t
    assert all(prompts.identity(c) in t for c in p["roster"]) and "Clip 6:" in t and "PASS or REVISE" in t and "OUTPUT CONTRACT" in t
    assert not re.search(r"\[[A-Z _]+\]|TODO|placeholder", t)


# ---------- continuity ----------
def test_continuity_catches_a_dropped_prop_and_a_silent_location_change():
    p = full_project()
    assert continuity.check(p) == []
    p["clips"][3]["chars"][0]["prop_grip"] = "empty hands"
    p["clips"][4]["location"] = "a harbour"
    msgs = [i["text"] for i in continuity.check(p)]
    assert any("CHAR_01 held 'a brass lantern'" in m for m in msgs) and any("location changes" in m for m in msgs)
    rec = continuity.record(p)
    assert rec[0]["clip"] == "C01" and rec[1]["incoming"] == p["clips"][0]["outgoing"]


def test_package_follows_the_sheets_delivery_order_with_full_prompts():
    p = full_project()
    md = package.build(p)
    order = [md.index(h) for h in ("## 1. Fact brief", "## 2. Story and narration", "## 3. Visual style", "## 4. Character reference sheet prompts",
                                   "## 5. Character consistency agent", "## 6. Clip packages", "## 7. Stitching guide", "## 8. Assembly guide")]
    assert order == sorted(order) and "Verification status: PENDING" in md
    assert all(c["scene_prompt"] in md and c["animation_prompt"] in md for c in p["clips"]) and "C06_scene, C06_video, C06_voice" in md


# ---------- the whole line ----------
def _png(path: Path) -> bytes:
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=360x640:d=1", "-frames:v", "1", str(path)], check=True)
    return path.read_bytes()


@pytest.fixture()
def standins(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "ROOT", tmp_path / "stickman")
    png = _png(tmp_path / "k.png")
    monkeypatch.setattr(writers, "ask", fake_ask)
    monkeypatch.setattr(media, "_t2i", lambda prompt, w, h, seed, prefer=None, s=None: (png, "standin"))
    monkeypatch.setattr(media, "picture", lambda prompt, refs, w, h, seed, tag, priority=5, s=None, negative=None: (png, {"model": "standin", "refs": len(refs)}))
    def say(text, voice, emotion="neutral"):
        out = tmp_path / "v.wav"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "sine=f=300:d=7", "-ar", "24000", "-ac", "1", str(out)], check=True)
        return out.read_bytes()
    monkeypatch.setattr(media, "edge_say", say)
    monkeypatch.setattr(media, "music", lambda s, cue, seconds, tag: (None, {}))
    monkeypatch.setattr(engines, "capabilities", lambda s: {"ai_video": False, "blender": False})
    return tmp_path


@needs_ffmpeg
def test_event_to_six_ten_second_clips_and_the_package(standins):
    p = project(auto=True)
    store.save(p)
    pipeline._cancel[p["id"]] = threading.Event()
    pipeline._run(p["id"], "topics")
    q = store.load(p["id"])
    assert q["status"] == "done", q.get("error")
    assert q["event"] == "Event 2" and q["project"]["title"] == "Event 2" and q["clip_count"] == 6 and len(q["clips"]) == 6 and len(q["roster"]) == 2     # the recommended idea was picked
    d = store.pdir(p["id"])
    for n in range(1, 7):
        assert all((d / f"C{n:02d}_{k}").is_file() for k in ("scene.png", "video.mp4", "voice.wav"))
    assert all((d / f"{c['id']}_sheet.png").is_file() for c in q["roster"]) and all(c["engine"] == "still" for c in q["clips"])
    probe = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type,width,height", "-of", "json", str(d / "final.mp4")], capture_output=True, text=True).stdout)
    assert abs(float(probe["format"]["duration"]) - 60.0) < 1.5
    v = next(s for s in probe["streams"] if s["codec_type"] == "video")
    assert (v["width"], v["height"]) == (720, 1280)
    md = (d / "package.md").read_text("utf-8")
    assert "CHARACTER CONSISTENCY AGENT INSTRUCTIONS" in md and md.count("**10-second animation prompt**") == 6


@needs_ffmpeg
def test_you_pick_the_topic_approve_the_treatment_then_the_reference_sheets(standins):
    p = project(auto=False)
    store.save(p)
    pipeline._cancel[p["id"]] = threading.Event()
    pipeline._run(p["id"], "topics")
    q = store.load(p["id"])
    assert (q["status"], q["stage"]) == ("waiting", "topics") and len(q["topics"]["topics"]) == 8
    pipeline.pick(p["id"], 5)
    pipeline._run(p["id"], "brief")
    q = store.load(p["id"])
    assert (q["status"], q["stage"]) == ("waiting", "story") and q["story"] and not q.get("roster")      # the director's treatment is approved first
    pipeline._run(p["id"], pipeline.next_stage(q))
    q = store.load(p["id"])
    assert (q["status"], q["stage"]) == ("waiting", "refs") and q["event"] == "Event 5" and not any(c.get("scene") for c in q["clips"])
    assert all((store.pdir(p["id"]) / f"{c['id']}_sheet.png").is_file() for c in q["roster"])
    pipeline._run(p["id"], pipeline.next_stage(q))
    assert store.load(p["id"])["status"] == "done"


def test_the_builtin_crew_refuses_to_write_history(standins, monkeypatch):
    monkeypatch.setattr(writers, "ask", REAL_ASK)
    p = project(crew="builtin", event="Event Two", project={"title": "Event Two", "date_place": "", "premise": "", "tone": "clear"}, stage="brief")
    store.save(p)
    pipeline._cancel[p["id"]] = threading.Event()
    pipeline._run(p["id"], "brief")
    q = store.load(p["id"])
    assert q["status"] == "error" and "needs an AI writer" in q["error"]


@needs_ffmpeg
def test_amber_noir_proposal_layout_reference_and_native_audio_clips(standins, monkeypatch, tmp_path):
    from studio.stickman import video
    mp4 = tmp_path / "native.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=1280x720:d=10", "-f", "lavfi", "-i", "sine=f=440:d=10",
                    "-shortest", "-pix_fmt", "yuv420p", str(mp4)], check=True)
    sent = []
    monkeypatch.setattr(video, "ready", lambda s: True)
    monkeypatch.setattr(video, "clip", lambda prompt, images, prev, seconds, aspect, audio: (sent.append((prompt, len(images), prev is not None, audio)), mp4.read_bytes())[1])
    p = project(auto=True, style="a6-amber", aspect="16:9", event="Fear gets smaller", project={"title": "Fear gets smaller", "date_place": "", "premise": "", "tone": "warm"},
                stage="brief", clip_count=3, seconds=30, length_set=True)
    store.save(p)
    pipeline._cancel[p["id"]] = threading.Event()
    pipeline._run(p["id"], "brief")
    q = store.load(p["id"])
    assert q["status"] == "done", q.get("error")
    assert q["bible"]["layout"].startswith("a narrow street") and q["assets"]["layout"] == "layout.png"
    assert len(sent) == 3 and sent[0][1] == 3 and sent[1][2] and all(x[3] for x in sent)          # opening + identity + layout, previous clip from clip 2
    assert "@Image1 is the approved opening composition" in sent[1][0] and "@Video1" in sent[1][0] and "rust-orange hoodie" in sent[0][0]
    assert "Continue the same musical theme" in sent[1][0] and "LAYOUT: a narrow street" in sent[0][0]
    assert all(c.get("native_audio") for c in q["clips"]) and not any((store.pdir(p["id"]) / f"C{n:02d}_voice.wav").is_file() for n in (1, 2, 3))
    assert (store.pdir(p["id"]) / "final.srt").read_text("utf-8") == ""                                 # no captions: no on-screen text
    probe = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type", "-of", "json", str(store.pdir(p["id"]) / "final.mp4")],
                                      capture_output=True, text=True).stdout)
    assert {"audio", "video"} <= {s["codec_type"] for s in probe["streams"]} and abs(float(probe["format"]["duration"]) - 30) < 1.5
