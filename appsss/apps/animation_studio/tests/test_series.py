"""Series, end to end through the HTTP API, on a real AVOS GPU worker in a thread (the mock backend: every model
answers like the real one, no GPU needed): characters drawn + voiced and approved one by one, an episode outlined in
parts, each part's script approved, rendered (voices → keyframes → lip-sync / action clips → sound effects → music →
mix), reviewed, a shot redone, approved, and the parts joined into the episode. Also your own script, and the AI
writers against a stand-in Ollama."""
from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from studio import avos_settings, gpu
from studio.series import languages, media, pipeline, store, writers
from studio.server import app

from .conftest import needs_ffmpeg
from .test_models import gpu_worker_url  # noqa: F401 - the shared GPU worker fixture

PNG_REF = None


def _png(path: Path) -> bytes:
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=320x180:d=1", "-frames:v", "1", str(path)], check=True)
    return path.read_bytes()


def _probe(p: Path) -> dict:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type", "-of", "json", str(p)],
                       capture_output=True, text=True)
    return json.loads(r.stdout)


def wait(c: TestClient, sid: str, ok, what: str, timeout: float = 240) -> dict:
    t0 = time.time()
    while True:
        snap = c.get(f"/api/series/{sid}").json()
        if ok(snap):
            return snap
        w = snap["series"].get("work") or {}
        if w.get("state") == "error":
            raise AssertionError(f"waiting for {what}: {w.get('error')}")
        if time.time() - t0 > timeout:
            raise AssertionError(f"timed out waiting for {what}: {json.dumps(w)[:400]}")
        time.sleep(0.3)


def idle(snap: dict) -> bool:
    return not snap["busy"]


def board(c: TestClient, sid: str, eid: str, n: int, ep_index: int = 0) -> dict:
    """The storyboard gate: the frames are drawn, nothing moves until it is approved."""
    snap = wait(c, sid, lambda s: idle(s) and s["episodes"][ep_index]["parts"][n - 1]["status"] in ("board_review", "error"), f"part {n} storyboard", 300)
    p = snap["episodes"][ep_index]["parts"][n - 1]
    assert p["status"] == "board_review", p.get("error")
    assert p["storyboard"] and (store.sdir(sid) / p["storyboard"]).is_file()
    assert all(x["files"].get("key") and not x["files"].get("clip") for x in p["shots"])        # frames, no clips yet
    assert c.post(f"/api/series/{sid}/episodes/{eid}/parts/{n}/approve").status_code == 409       # nothing to watch yet
    assert c.post(f"/api/series/{sid}/episodes/{eid}/parts/{n}/board/approve").status_code == 200
    return snap


@pytest.fixture
def worker(gpu_worker_url, monkeypatch):  # noqa: F811
    for k in ("FAL_KEY", "COMFYUI_URL", "MODEL_BACKEND", "CLOUDFLARE_ACCOUNT_ID"):
        monkeypatch.delenv(k, raising=False)
    gpu._cache.clear()
    avos_settings.set_env({"GPU_WORKER_TOKEN": "tok"})
    avos_settings.upsert_worker({"id": "home", "name": "Home 4090", "url": gpu_worker_url})
    monkeypatch.setenv("SERIES_CONCURRENCY", "3")
    yield gpu_worker_url
    avos_settings.delete_worker("home")          # later tests expect no GPU worker
    avos_settings.set_env({"GPU_WORKER_TOKEN": None})
    gpu._cache.clear()


def test_part_plan_and_languages():
    assert writers.part_plan(10, [1, 3]) == [1, 3, 3, 3]
    assert writers.part_plan(11, [1, 3]) == [1, 3, 3, 4]          # a short sliver joins the last part
    assert writers.part_plan(1.5, [1, 3]) == [1, 0.5]
    assert writers.part_plan(0.5, [0.25]) == [0.25, 0.25]
    assert languages.line_models("hi") == ["chatterbox", "indicf5", "indic-parler-tts"]
    assert languages.line_models("ta") == ["indicf5", "indic-parler-tts"]          # Chatterbox has no Tamil
    assert languages.line_models("es") == ["chatterbox"] and languages.design_models("es") == []
    assert languages.get("hinglish").tts == "hi"
    assert writers.line_seconds("नमस्ते, आज बहुत गर्मी है!") > 1.4


def test_screenplay_without_ai_and_split():
    s = {"characters": [{"id": "raju", "name": "Raju", "status": "approved"}, {"id": "amma", "name": "Amma", "status": "approved"}],
         "locations": [{"id": "kitchen", "name": "Kitchen"}]}
    text = ("INT. KITCHEN - MORNING\nRaju: (excited) Amma, look what I found!\n(Amma turns, holding a ladle)\n"
            "Amma: Put that down right now.\nGhost: I am not in the cast.\n\nSCENE 2\nRaju: But it's a real treasure map!\n")
    sc = writers.parse_screenplay(s, text)
    lines = [b for x in sc["scenes"] for b in x["beats"] if b["type"] == "line"]
    assert [b["character"] for b in lines] == ["raju", "amma", "raju"] and lines[0]["emotion"] == "excited"
    assert sc["scenes"][0]["location"] == "kitchen" and len(sc["scenes"]) == 2
    assert any(b["type"] == "action" and "Ghost" in b["text"] for b in sc["scenes"][0]["beats"])   # not a speaker
    parts = writers.split_script(sc, [0.05, 0.05])
    assert len(parts) == 2 and sum(len(x["beats"]) for p in parts for x in p["scenes"]) == sum(len(x["beats"]) for x in sc["scenes"])
    assert parts[1]["scenes"][0]["beats"][0]["id"] == "s1b1"


@needs_ffmpeg
def test_a_series_from_characters_to_a_finished_episode(worker, tmp_path):
    ref = _png(tmp_path / "style.png")
    with TestClient(app) as c:
        assert c.post("/api/series", data={"title": ""}).status_code == 400
        r = c.post("/api/series", data={"title": "Middle Class Diaries", "premise": "A noisy family in a small flat in Pune.",
                                        "language": "hi", "aspect": "16:9", "crew": "builtin", "partPlan": "0.25",
                                        "style": "flat 2D cartoon, thick outlines, warm colours",
                                        "cast": "Raju - a skinny 12-year-old boy, messy hair, green t-shirt\nAmma - his mother, purple saree, round glasses"},
                   files=[("refs", ("style.png", ref, "image/png"))])
        assert r.status_code == 200, r.text
        sid = r.json()["id"]

        # 1. characters: a sheet and a voice each, then they wait for you
        snap = wait(c, sid, lambda s: idle(s) and s["series"]["characters"] and all(x["status"] == "review" for x in s["series"]["characters"]), "characters")
        chars = {x["id"]: x for x in snap["series"]["characters"]}
        assert set(chars) == {"raju", "amma"} and chars["amma"]["gender"] == "female"
        for ch in chars.values():
            assert ch["sheetInfo"]["model"] == "qwen-image-edit" and not ch["sheetInfo"]["fallback"]
            assert ch["voice"]["model"] == "indic-parler-tts" and ch["voice"]["sampleText"].startswith("नमस्ते")
            assert c.get(f"/api/series/{sid}/files/{ch['sheet']}").headers["content-type"] == "image/png"
            assert c.get(f"/api/series/{sid}/files/{ch['voice']['sample']}").content[:4] == b"RIFF"
        assert snap["ready"]["lines"] == "chatterbox" and snap["ready"]["lipsync"] == "infinitetalk"
        assert c.get(f"/api/series/{sid}/files/../../secrets.json").status_code == 404
        assert all(x.get("plate") for x in snap["series"]["locations"])

        # nothing moves until a character is approved
        assert c.post(f"/api/series/{sid}/episodes", json={"minutes": 0.5}).status_code == 409
        # redo Amma's voice with a note → a new version, back to review
        r = c.post(f"/api/series/{sid}/characters/amma/redo", json={"what": "voice", "note": "older, slower, a bit strict"})
        assert r.status_code == 200
        snap = wait(c, sid, lambda s: idle(s) and next(x for x in s["series"]["characters"] if x["id"] == "amma")["status"] == "review", "amma redo")
        amma = next(x for x in snap["series"]["characters"] if x["id"] == "amma")
        assert amma["version"] == 2 and amma["voice"]["sample"].endswith("voice_v2.wav") and amma["sheet"].endswith("sheet_v1.png")
        assert "strict" in amma["voice"]["description"] and amma["notes"] == ["older, slower, a bit strict"]
        for cid in ("raju", "amma"):
            assert c.post(f"/api/series/{sid}/characters/{cid}/approve").status_code == 200

        # 2. an episode: outline in parts → approve
        r = c.post(f"/api/series/{sid}/episodes", json={"minutes": 0.5, "brief": "Raju breaks the TV remote before the big match"})
        assert r.status_code == 200, r.text
        eid = r.json()["episode"]
        assert c.post(f"/api/series/{sid}/episodes", json={"minutes": 1}).status_code == 409        # one at a time
        snap = wait(c, sid, lambda s: idle(s) and s["episodes"][0]["status"] == "outline_review", "outline")
        assert [p["minutes"] for p in snap["episodes"][0]["parts"]] == [0.25, 0.25]
        assert c.post(f"/api/series/{sid}/episodes/{eid}/parts/1/script/approve").status_code == 409   # outline first
        assert c.post(f"/api/series/{sid}/episodes/{eid}/outline/approve").status_code == 200

        # 3. part 1: script → your edit → approve → render
        snap = wait(c, sid, lambda s: idle(s) and s["episodes"][0]["parts"][0]["status"] == "script_review", "part 1 script")
        script = snap["episodes"][0]["parts"][0]["script"]
        beats = script["scenes"][0]["beats"]
        first_line = next(b for b in beats if b["type"] == "line")
        first_line["text"] = "रिमोट कहाँ है?"
        first_line["emotion"] = "angry"
        r = c.put(f"/api/series/{sid}/episodes/{eid}/parts/1/script", json={"script": script})
        assert r.status_code == 200
        assert c.post(f"/api/series/{sid}/episodes/{eid}/parts/2/script/approve").status_code == 409
        assert c.post(f"/api/series/{sid}/episodes/{eid}/parts/1/script/approve").status_code == 200
        board(c, sid, eid, 1)
        snap = wait(c, sid, lambda s: idle(s) and s["episodes"][0]["parts"][0]["status"] in ("review", "error"), "part 1 render", 300)
        p1 = snap["episodes"][0]["parts"][0]
        assert p1["status"] == "review", p1.get("error")
        shots = p1["shots"]
        talk = [x for x in shots if x["kind"] == "dialogue"]
        acts = [x for x in shots if x["kind"] == "action"]
        assert talk and acts
        assert {x["models"]["line"]["model"] for x in talk} == {"chatterbox"}
        assert {x["models"]["key"]["model"] for x in shots} == {"qwen-image-edit"}
        assert {x["models"]["clip"]["model"] for x in talk} == {"infinitetalk"}
        assert {x["models"]["clip"]["model"] for x in acts} == {"wan-2.2"}
        assert all(x["models"]["sfx"]["model"] == "hunyuan-foley" for x in acts if x.get("sfx"))
        assert p1["musicInfo"]["model"] == "ace-step"
        assert next(x for x in talk)["text"] == "रिमोट कहाँ है?"
        assert not any(w for x in shots for w in x["warnings"]), [x["warnings"] for x in shots]
        video = store.sdir(sid) / p1["video"]
        info = _probe(video)
        kinds = sorted(st["codec_type"] for st in info["streams"])
        assert kinds == ["audio", "subtitle", "video"]
        assert abs(float(info["format"]["duration"]) - sum(x["seconds"] for x in shots)) < 0.4
        assert "रिमोट कहाँ है?" in video.with_suffix(".srt").read_text("utf-8")

        # 4. redo one shot's picture: only that shot is drawn and animated again
        target = acts[0]["id"]
        others = {x["id"]: (store.part_dir(sid, eid, 1) / "shots" / x["id"] / "key.png").stat().st_mtime_ns for x in shots}
        r = c.post(f"/api/series/{sid}/episodes/{eid}/parts/1/redo", json={"shots": [target], "what": ["picture"], "note": "make it night"})
        assert r.status_code == 200
        snap = wait(c, sid, lambda s: idle(s) and s["episodes"][0]["parts"][0]["status"] == "review", "redo", 300)
        p1 = snap["episodes"][0]["parts"][0]
        after = {x["id"]: (store.part_dir(sid, eid, 1) / "shots" / x["id"] / "key.png").stat().st_mtime_ns for x in p1["shots"]}
        assert [k for k in after if after[k] != others[k]] == [target]
        assert next(x for x in p1["shots"] if x["id"] == target)["takes"]["picture"] == 2 and p1["renders"] == 2

        # 5. approve → story memory → part 2 is written, approved, rendered, approved → the episode is joined
        assert c.post(f"/api/series/{sid}/episodes/{eid}/parts/1/approve").status_code == 200
        snap = wait(c, sid, lambda s: idle(s) and s["episodes"][0]["parts"][1]["status"] == "script_review", "part 2 script")
        assert snap["episodes"][0]["parts"][0]["memory"]["summary"]
        assert c.post(f"/api/series/{sid}/episodes/{eid}/parts/2/script/approve").status_code == 200
        board(c, sid, eid, 2)
        snap = wait(c, sid, lambda s: idle(s) and s["episodes"][0]["parts"][1]["status"] == "review", "part 2 render", 300)
        assert c.post(f"/api/series/{sid}/episodes/{eid}/parts/2/approve").status_code == 200
        snap = wait(c, sid, lambda s: idle(s) and s["episodes"][0]["status"] == "done", "episode")
        ep = snap["episodes"][0]
        whole = store.sdir(sid) / ep["video"]
        parts_len = sum(media.probe_seconds(store.sdir(sid) / p["video"]) for p in ep["parts"])
        assert abs(media.probe_seconds(whole) - parts_len) < 0.5
        assert snap["series"]["story"]["episodes"][0]["episode"] == 1
        assert c.get("/api/series").json()[0]["episodes"] == 1

        # 6. your own script → split into parts, first part waiting for approval
        r = c.post(f"/api/series/{sid}/episodes", json={"script": "INT. KITCHEN\nRaju: Amma, chai?\nAmma: (angry) Homework first!\n"
                                                                  "(Raju sulks to his room)\nRaju: Fine.", "minutes": 1})
        assert r.status_code == 200
        snap = wait(c, sid, lambda s: idle(s) and s["episodes"][1]["status"] == "in_production", "imported script")
        ep2 = snap["episodes"][1]
        assert ep2["source"] == "script" and ep2["parts"][0]["status"] == "script_review"
        texts = [b["text"] for x in ep2["parts"][0]["script"]["scenes"] for b in x["beats"] if b["type"] == "line"]
        assert texts == ["Amma, chai?", "Homework first!", "Fine."]


def test_writers_with_an_ai_crew(monkeypatch, tmp_path):
    """The writers' prompts and the repairs: unknown speakers dropped, bad emotions fixed, ids added."""
    s = {"id": "x", "title": "T", "language": "hi", "crew": "groq",
         "characters": [{"id": "raju", "name": "Raju", "status": "approved", "look": "boy"},
                        {"id": "amma", "name": "Amma", "status": "review"}], "locations": [{"id": "home", "name": "Home"}]}
    seen = {}

    def fake_ask(s_, who, system, prompt, log=None, max_tokens=0, temperature=0, images=None):
        seen[who] = (system, prompt)
        if who == "scriptwriter":
            return {"scenes": [{"location": "Home", "beats": [
                {"type": "line", "character": "Raju", "text": "चलो!", "emotion": "furious"},
                {"type": "line", "character": "amma", "text": "not approved yet"},
                {"type": "line", "character": "nobody", "text": "x"},
                {"type": "action", "text": "Raju jumps on the sofa", "characters": ["raju"], "sfx": "springs creak", "seconds": 40}]}]}
        if who == "scene director":
            return {"shots": [{"beat": "s1b1", "framing": "close-up", "picture": "Raju shouts",
                               "camera": {"move": "dolly in", "ease": "power2.out"},
                               "tracks": [{"target": "raju", "keys": [{"t": 0, "action": "clenches his fists"}, {"t": 9, "action": "jumps"}]},
                                          {"target": "ghost", "keys": [{"t": 0, "action": "haunts"}]}]}]}
        return None
    monkeypatch.setattr(writers, "ask", fake_ask)
    ep = {"number": 1, "parts": [{"minutes": 1, "summary": "the start"}], "outline": {"title": "Ep"}}
    sc = writers.part_script(s, ep, 1)
    beats = sc["scenes"][0]["beats"]
    assert [b["type"] for b in beats] == ["line", "action"] and beats[0]["emotion"] == "neutral" and beats[1]["seconds"] == 6
    assert sc["scenes"][0]["location"] == "home" and beats[0]["id"] == "s1b1"
    assert "Devanagari" in seen["scriptwriter"][1] and "amma" not in seen["scriptwriter"][1].split("Approved characters:")[1].split("\n")[0]
    shots = writers.plan_shots(s, sc)
    assert shots[0]["framing"] == "close-up" and shots[0]["kind"] == "dialogue" and shots[1]["kind"] == "action"
    assert shots[1]["framing"] in writers.FRAMINGS and shots[1]["subjects"] == ["raju"] and shots[1]["sfx"] == "springs creak"
    # the scene graph and the motion blueprint: repaired, timed inside the shot, unknown actors dropped
    st, bp = shots[0]["stage"], shots[0]["blueprint"]
    assert st["framing"] == "close-up" and st["actors"][0]["id"] == "raju" and st["actors"][0]["speaking"] and st["camera"]["lens"] == 85
    assert bp["camera"]["move"] == "push_in" and bp["camera"]["ease"] == "power2.out" and bp["lipsync"] == "raju"
    assert [t["target"] for t in bp["tracks"]] == ["raju"] and bp["tracks"][0]["keys"][1]["t"] == bp["duration"]
    assert shots[1]["blueprint"]["tracks"][0]["keys"][0]["action"] == "Raju jumps on the sofa"      # a default track from the action
    assert seen["scene director"][0].startswith("[avos-scene-director]")       # the instructions come from its SKILL.md


@needs_ffmpeg
def test_the_ai_writers_room_through_a_local_model(worker, tmp_path):
    """The same flow with an AI crew (a stand-in Ollama that sometimes answers with chatter first): the bible, the
    outline, a part written in Hindi, the DoP's framings, and the story memory after approval."""
    import socket
    import threading

    import uvicorn

    from . import fake_ollama
    with socket.socket() as sk:
        sk.bind(("127.0.0.1", 0))
        port = sk.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(fake_ollama.app, host="127.0.0.1", port=port, log_level="warning"))
    threading.Thread(target=server.run, daemon=True).start()
    while not server.started:
        time.sleep(0.05)
    import os
    os.environ["OLLAMA_URL"] = f"http://127.0.0.1:{port}"
    try:
        with TestClient(app) as c:
            sid = c.post("/api/series", data={"title": "Remote War", "premise": "A noisy family.", "language": "hi", "crew": "ollama",
                                              "partPlan": "0.25"}).json()["id"]
            snap = wait(c, sid, lambda s: idle(s) and len(s["series"]["characters"]) == 2 and all(x["status"] == "review" for x in s["series"]["characters"]), "cast")
            s = snap["series"]
            assert s["logline"].startswith("A noisy family") and s["style"]["prompt"].startswith("flat 2D")
            assert [x["id"] for x in s["characters"]] == ["bunty", "mummy"] and s["characters"][0]["catchphrase"] == "Plan ready hai!"
            assert {x["id"] for x in s["locations"]} == {"living-room", "kitchen"}
            for cid in ("bunty", "mummy"):
                c.post(f"/api/series/{sid}/characters/{cid}/approve")
            eid = c.post(f"/api/series/{sid}/episodes", json={"minutes": 0.25, "brief": "the remote"}).json()["episode"]
            snap = wait(c, sid, lambda s: idle(s) and s["episodes"][0]["status"] == "outline_review", "outline")
            assert snap["episodes"][0]["title"] == "The Remote War"
            c.post(f"/api/series/{sid}/episodes/{eid}/outline/approve")
            snap = wait(c, sid, lambda s: idle(s) and s["episodes"][0]["parts"][0]["status"] == "script_review", "script")
            lines = [b for x in snap["episodes"][0]["parts"][0]["script"]["scenes"] for b in x["beats"] if b["type"] == "line"]
            assert lines[0]["text"] == "मम्मी, मैंने कुछ नहीं किया!" and lines[1]["emotion"] == "sarcastic"
            c.post(f"/api/series/{sid}/episodes/{eid}/parts/1/script/approve")
            board(c, sid, eid, 1)
            snap = wait(c, sid, lambda s: idle(s) and s["episodes"][0]["parts"][0]["status"] == "review", "render", 300)
            p1 = snap["episodes"][0]["parts"][0]
            shots = p1["shots"]
            assert [x["framing"] for x in shots] == ["wide", "close-up", "medium", "two-shot"]
            # the Design DNA (from the art-director skill, repaired) drives every prompt
            dna = snap["series"]["dna"]
            assert dna["line"] == "thick dark brown outlines" and dna["palette"] == ["#2B2D42", "#FFD166", "#EF476F"]
            assert all("thick dark brown outlines" in x["models"]["key"]["prompt"] for x in shots)
            # the scene director's blocking and motion: compiled into the prompts; moves outside the DNA's grammar → static
            assert [x["blueprint"]["camera"]["move"] for x in shots] == ["static", "push_in", "pan_right", "static"]
            assert shots[1]["stage"]["props"][0]["name"] == "TV remote" and "Prop: TV remote, held by" in shots[1]["models"]["key"]["prompt"]
            talk = next(x for x in shots if x["kind"] == "dialogue")
            assert talk["models"]["clip"]["prompt"].startswith(talk["models"]["clip"]["prompt"].split(" talks")[0] + " talks")
            assert abs(talk["blueprint"]["duration"] - talk["seconds"]) < 0.01          # retimed to the voiced line
            # the sound designer: ambience per scene (HunyuanVideo-Foley under the whole scene), the music cue
            assert p1["sound"]["music"].startswith("sneaky pizzicato") and p1["ambienceInfo"]["s1"]["model"] == "hunyuan-foley"
            assert p1["musicInfo"]["prompt"].startswith("sneaky pizzicato")
            c.post(f"/api/series/{sid}/episodes/{eid}/parts/1/approve")
            snap = wait(c, sid, lambda s: idle(s) and s["episodes"][0]["status"] == "done", "episode")
            assert snap["series"]["story"]["facts"] == ["the TV remote is broken"]
            assert "blamed the heat" in snap["series"]["story"]["episodes"][0]["summary"]
        assert any(x["broken"] for x in fake_ollama.CALLS)        # chatter instead of JSON happened, and was retried
    finally:
        os.environ.pop("OLLAMA_URL", None)
        server.should_exit = True


@needs_ffmpeg
def test_shot_tools_director_modify_animate_image_motion_transfer_and_qa(worker, tmp_path, monkeypatch):
    """Genjutsu-style controls on one rendered shot, each redoing only that shot; and the shot QA's retry."""
    calls = {"n": 0}

    def fake_qa(s, shot, images, stage, log=None):
        if stage == "key" and shot["id"] == "s1b2":
            calls["n"] += 1
            if calls["n"] == 1:
                return {"pass": False, "checks": {"character": {"ok": False, "why": "the shirt is red"}}, "fix": "Raju's shirt must be green"}
        return {"pass": True, "checks": {"character": {"ok": True, "why": ""}}, "fix": ""}
    monkeypatch.setattr(writers, "qa_shot", fake_qa)
    with TestClient(app) as c:
        sid = c.post("/api/series", data={"title": "Tools", "language": "en", "crew": "builtin", "partPlan": "0.25",
                                          "cast": "Raju - a boy\nAmma - his mother"}).json()["id"]
        wait(c, sid, lambda s: idle(s) and len(s["series"]["characters"]) == 2 and all(x["status"] == "review" for x in s["series"]["characters"]), "cast")
        for cid in ("raju", "amma"):
            c.post(f"/api/series/{sid}/characters/{cid}/approve")
        eid = c.post(f"/api/series/{sid}/episodes", json={"minutes": 0.25}).json()["episode"]
        wait(c, sid, lambda s: idle(s) and s["episodes"][0]["status"] == "outline_review", "outline")
        c.post(f"/api/series/{sid}/episodes/{eid}/outline/approve")
        wait(c, sid, lambda s: idle(s) and s["episodes"][0]["parts"][0]["status"] == "script_review", "script")
        c.post(f"/api/series/{sid}/episodes/{eid}/parts/1/script/approve")
        board(c, sid, eid, 1)
        snap = wait(c, sid, lambda s: idle(s) and s["episodes"][0]["parts"][0]["status"] == "review", "render", 300)
        shots = snap["episodes"][0]["parts"][0]["shots"]
        qa_shot = next(x for x in shots if x["id"] == "s1b2")
        assert qa_shot["qa"]["key"]["retried"] and qa_shot["qa"]["key"]["first"]["fix"] == "Raju's shirt must be green"
        assert "Change: Raju's shirt must be green" in qa_shot["models"]["key"]["prompt"] and qa_shot["models"]["key"]["qaRetry"]
        assert not qa_shot["warnings"]
        assert c.get(f"/api/series/skills").json()["skills"]

        pd = store.part_dir(sid, eid, 1) / "shots"
        mt = lambda: {x["id"]: ((pd / x["id"] / "key.png").stat().st_mtime_ns, (pd / x["id"] / "clip.mp4").stat().st_mtime_ns) for x in shots}  # noqa: E731
        act = next(x for x in shots if x["kind"] == "action")
        base = act["id"]
        url = f"/api/series/{sid}/episodes/{eid}/parts/1/shots/{base}"

        def settle() -> dict:
            return wait(c, sid, lambda s: idle(s) and s["episodes"][0]["parts"][0]["status"] == "review", "re-render", 300)

        def only_changed(before: dict) -> list[str]:
            after = mt()
            return sorted(k for k in after if after[k] != before[k])

        # Director: move the camera (a new move only redoes the clip) …
        before = mt()
        bp = dict(act["blueprint"], camera={**act["blueprint"]["camera"], "move": "orbit_right", "to": None})
        assert c.put(f"{url}/stage", json={"stage": act["stage"], "blueprint": bp}).status_code == 200
        snap = settle()
        after = mt()
        assert only_changed(before) == [base] and after[base][0] == before[base][0]                 # same picture, new clip
        act = next(x for x in snap["episodes"][0]["parts"][0]["shots"] if x["id"] == base)
        assert act["blueprint"]["camera"]["move"] == "orbit_right" and "arcs around to the right" in act["models"]["clip"]["prompt"]
        # … then move an actor (the layout changes: a new picture too)
        before = mt()
        stage = dict(act["stage"], actors=[{**a, "x": 1.2} for a in act["stage"]["actors"]])
        c.put(f"{url}/stage", json={"stage": stage, "blueprint": act["blueprint"]})
        settle()
        after = mt()
        assert only_changed(before) == [base] and after[base][0] != before[base][0]
        assert c.put(f"{url}/stage", json={"stage": stage, "blueprint": act["blueprint"]}).json()["busy"] is False   # nothing changed

        # Modify shot: one change, keep the rest, keep the motion (Wan VACE)
        before = mt()
        assert c.post(f"{url}/modify", json={"instruction": "make the sofa red", "keepMotion": True}).status_code == 200
        snap = settle()
        act = next(x for x in snap["episodes"][0]["parts"][0]["shots"] if x["id"] == base)
        assert only_changed(before) == [base]
        assert act["models"]["key"]["edit"] == "make the sofa red" and "Edit picture 1: make the sofa red" in act["models"]["key"]["prompt"]
        assert act["models"]["clip"]["model"] == "wan-vace" and act["keyOverride"]["history"] == ["make the sofa red"]

        # Animate image: your own picture is the first frame
        png = _png(tmp_path / "mine.png")
        r = c.post(f"{url}/image", files={"picture": ("mine.png", png, "image/png")}, data={"motion": "she waves slowly"})
        assert r.status_code == 200
        snap = settle()
        act = next(x for x in snap["episodes"][0]["parts"][0]["shots"] if x["id"] == base)
        assert (pd / base / "key.png").read_bytes() == png and act["keyOverride"]["source"] == "upload"
        assert "she waves slowly" in act["models"]["clip"]["prompt"]

        # Motion transfer: a reference video drives the character
        clip = (pd / shots[0]["id"] / "clip.mp4").read_bytes()
        assert c.post(f"{url}/driver", files={"video": ("me.mp4", clip, "video/mp4")}).status_code == 200
        snap = settle()
        act = next(x for x in snap["episodes"][0]["parts"][0]["shots"] if x["id"] == base)
        assert act["models"]["clip"]["model"] == "wan-2.2-animate" and act["models"]["clip"]["driver"]

        # back to the generated shot
        assert c.delete(f"{url}/override").status_code == 200
        snap = settle()
        act = next(x for x in snap["episodes"][0]["parts"][0]["shots"] if x["id"] == base)
        assert "keyOverride" not in act and "driver" not in act and act["models"]["clip"]["model"] == "wan-2.2"
        assert (pd / base / "key.png").read_bytes() != png

        # the Design DNA can be edited; it's repaired on the way in
        r = c.patch(f"/api/series/{sid}", json={"dna": {"line": "scratchy pencil", "palette": ["#123456", "bad"]}})
        assert r.json()["series"]["dna"]["line"] == "scratchy pencil" and r.json()["series"]["dna"]["palette"] == ["#123456"]
