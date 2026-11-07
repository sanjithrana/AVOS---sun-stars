"""Films (prompt → animation) through the HTTP API on a real GPU worker process with the mock backend: the prompt read
into a timed breakdown, edited and approved; characters and world drawn and approved; one character saved to the
library and cast again in a second film; the storyboard drawn and approved before anything moves; a batch camera
change; the animated film with the prompt's own timing, camera, sounds and music; the project files."""
from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

from fastapi.testclient import TestClient

from studio.series import film, store, writers
from studio.server import app

from .conftest import needs_ffmpeg
from .test_models import gpu_worker_url  # noqa: F401 - the shared GPU worker fixture
from .test_series import idle, wait, worker  # noqa: F401 - fixtures

WOLF = """Create a 9-second cinematic 3D animated comedy, Pixar style, smooth 24fps.

SETTING
A lush forest road after rain, puddles, mist, golden sunlight.

CHARACTERS
Wolf: a cheerful grey wolf in a yellow tropical shirt, driving a small red convertible with cream seats.
Rabbit: a tiny white rabbit in blue overalls with a huge orange off-road truck.

0–3 SECONDS
Wide tracking shot: the wolf sings and bobs his head while driving, his tyre hits a puddle and splashes the rabbit. Wolf sings "La la la, what a day!"

3–5 SECONDS
Close-up, eye-level, static: the rabbit wipes water from his face. Rabbit says "Oh, you'll pay for that."

5–9 SECONDS
Low angle, wide lens, slow push-in: the rabbit's enormous truck rolls through a huge puddle; a wave of muddy water drenches the wolf. Final plop.

AUDIO
forest ambience, playful orchestral music, engine rumble, splashes, a final plop
"""

CHEF = """14-second 3D Pixar-style animated comedy short.
SHOT 1 (0.00–1.00s) – Wide establishing shot, eye-level, slow push-in: Elegant luxury restaurant. Tall male chef lifts a silver cloche.
SHOT 2 (1.00–2.00s) – Tight close-up, high angle, static: Beautifully plated gourmet steak dish.
SHOT 3 (2.00–3.00s) – Extreme close-up on elderly lady's face, eye-level: She takes a bite, eyes widen.
SHOT 7 (6.00–7.00s) – Same kitchen wide shot, dynamic camera tilt down: Blue flames erupt from the stovetop.
SHOT 15 (14.00s – end) – Final wide shot, eye-level, slow pull-back: The lady stands triumphantly.
"""


def test_reading_prompts_with_rules_and_json():
    sk = film.skeleton(WOLF)
    assert sk["duration"] == 9 and [(x["start"], x["end"]) for x in sk["shots"]] == [(0, 3), (3, 5), (5, 9)]
    assert set(sk["sections"]) == {"setting", "characters", "audio"}
    bd = film.normalize(film.builtin_breakdown(WOLF))
    assert [c["name"] for c in bd["characters"]] == ["Wolf", "Rabbit"] and "red convertible" in bd["characters"][0]["look"]
    s1, s2, s3 = bd["shots"]
    assert (s1["framing"], s1["camera"], s1["start"], s1["end"]) == ("wide", "truck_right", 0, 3)
    assert s1["dialogue"] == [{"character": "Wolf", "text": "La la la, what a day!", "emotion": "neutral"}]
    assert (s2["framing"], s2["camera"], s2["angle"]) == ("close-up", "static", "eye level") and s2["dialogue"][0]["character"] == "Rabbit"
    assert (s3["angle"], s3["camera"], s3["end"]) == ("low angle", "push_in", 9) and any("plop" in x["sound"] for x in s3["sfx"])
    assert bd["audio"]["music"] == "playful orchestral music" and bd["audio"]["ambience"] == "forest ambience"
    assert bd["style"].startswith("3D Pixar-style") and bd["detected"]["shots"] == 3 and bd["detected"]["dialogue"] == 2

    # "SHOT n (a–b s)" prompts, gaps closed, "(14.00s – end)" read as a start
    chef = film.normalize(film.builtin_breakdown(CHEF))
    assert [x["camera"] for x in chef["shots"]] == ["push_in", "static", "static", "tilt_down", "pull_out"]
    assert [x["framing"] for x in chef["shots"]][:2] == ["wide", "close-up"] and chef["shots"][1]["angle"] == "high angle"
    assert [x["start"] for x in chef["shots"]] == [0, 1, 2, 3, 4]                     # contiguous, each keeps its length
    assert "copper" not in json.dumps(chef) and film.detect_move("stirs a copper pan") is None

    # a JSON prompt maps straight in (per-object keys become timed events)
    j = film.from_json(json.dumps({"shot_id": "shot_01", "start": 0, "duration": 3,
                                   "camera": {"type": "tracking", "position": "side", "movement": "forward"},
                                   "wolf": {"action": "drive", "head_motion": "bob", "singing": True},
                                   "water": {"source": "front_tire", "action": "splash", "target": "rabbit"}}))
    bj = film.normalize(j)
    assert bj["shots"][0]["camera"] == "truck_right" and bj["shots"][0]["end"] == 3
    assert {e["action"] for e in bj["shots"][0]["events"]} == {"action drive, head motion bob, singing", "source front_tire, action splash, target rabbit"}
    assert [c["name"] for c in bj["characters"]] == ["Wolf"]
    assert film.from_json("just text") is None

    # repairs: unknown speakers dropped, overlapping times fixed, bad moves → read from the words
    bad = film.normalize({"characters": ["Ann"], "shots": [{"start": 0, "end": 2, "camera": "whip pan", "dialogue": [{"character": "Ghost", "text": "boo"}]},
                                                           {"start": 1, "end": 40, "camera": "nonsense", "action": "camera pans left over the hills"}]})
    assert bad["shots"][0]["camera"] == "pan_right" and bad["shots"][0]["dialogue"] == []
    assert bad["shots"][1]["start"] == 2 and bad["shots"][1]["end"] == 2 + film.MAX_SHOT and bad["shots"][1]["camera"] == "pan_left"


def test_breakdown_to_script_and_shots_keep_the_prompts_direction():
    bd = film.normalize(film.builtin_breakdown(WOLF))
    s = {"id": "f1", "title": "T", "language": "en", "crew": "builtin",
         "characters": [{"id": "wolf", "name": "Wolf", "status": "approved", "look": "wolf"}, {"id": "rabbit", "name": "Rabbit", "status": "approved", "look": "rabbit"}],
         "locations": [{"id": "road", "name": bd["locations"][0]["name"]}]}
    bd["shots"][2]["events"] = [{"t": 1.0, "who": "Rabbit", "action": "grins behind the wheel"}, {"t": 2.0, "who": None, "action": "a wave of mud rises"}]
    script = film.script_from(s, bd)
    beats = [b for sc in script["scenes"] for b in sc["beats"]]
    assert [b["type"] for b in beats] == ["line", "line", "action"] and all(b["fixed"] for b in beats)
    assert [writers.beat_seconds(b) for b in beats] == [3, 2, 4]
    shots = writers.plan_shots(s, writers.norm_script(s, script))       # an edit round-trip keeps the direction
    assert [x["seconds"] for x in shots] == [3, 2, 4] and [x["framing"] for x in shots] == ["wide", "close-up", "wide"]
    assert [x["blueprint"]["camera"]["move"] for x in shots] == ["truck_right", "static", "push_in"]
    assert shots[0]["lipsync"] is False and shots[1]["lipsync"] is True              # a wide singing shot isn't lip-synced
    low = shots[2]
    assert low["stage"]["camera"]["position"][1] < low["stage"]["camera"]["target"][1] and low["angle"] == "low angle"
    assert low["blueprint"]["tracks"] == [{"target": "rabbit", "keys": [{"t": 1.0, "action": "grins behind the wheel"}]}]
    assert low["blueprint"]["environment"] == [{"t": 2.0, "text": "a wave of mud rises"}] and "plop" in low["sfx"] and low["sfxLocked"]


def test_collage(tmp_path):
    from PIL import Image
    frames = []
    for i in range(5):
        p = tmp_path / f"{i}.png"
        Image.new("RGB", (320, 180), (40 * i, 80, 120)).save(p)
        frames.append((p, f"{i}–{i + 1}s · wide"))
    out = film.collage(frames + [(tmp_path / "missing.png", "x")], tmp_path / "board.png")
    im = Image.open(out)
    assert im.width == 1920 and im.height < 1080 and film.collage([], tmp_path / "none.png") is None


@needs_ffmpeg
def test_a_film_from_prompt_to_project_files(worker, tmp_path):  # noqa: F811
    with TestClient(app) as c:
        assert c.post("/api/series/films", data={"prompt": "short"}).status_code == 400
        r = c.post("/api/series/films", data={"prompt": WOLF, "language": "en", "aspect": "16:9", "crew": "builtin"})
        assert r.status_code == 200, r.text
        sid = r.json()["id"]

        # 1. breakdown → you edit it → approve
        snap = wait(c, sid, lambda s: idle(s) and s["series"]["breakdown"].get("status") == "review", "breakdown")
        bd = snap["series"]["breakdown"]
        assert len(bd["shots"]) == 3 and bd["duration"] == 9 and snap["series"]["dna"]
        assert [x["state"] for x in snap["film"]["stages"]][:2] == ["yours", "waiting"]
        assert c.post(f"/api/series/{sid}/film/storyboard").status_code == 409                      # breakdown first
        bd["shots"][1]["camera"] = "orbit_left"
        bd["shots"][1]["sfx"] = [{"t": 0.5, "sound": "water dripping"}]
        r = c.put(f"/api/series/{sid}/breakdown", json={"breakdown": bd})
        assert r.status_code == 200 and r.json()["series"]["breakdown"]["shots"][1]["camera"] == "orbit_left"
        assert c.post(f"/api/series/{sid}/breakdown/approve").status_code == 200

        # 2. the consistency lock: characters (sheet + voice) and the world reference → approve
        snap = wait(c, sid, lambda s: idle(s) and len(s["series"]["characters"]) == 2 and all(x["status"] == "review" for x in s["series"]["characters"]), "cast")
        assert [x["name"] for x in snap["series"]["characters"]] == ["Wolf", "Rabbit"] and snap["series"]["locations"][0]["plate"]
        wolf = snap["series"]["characters"][0]
        assert wolf["voice"]["sampleText"] == "La la la, what a day!" and "convertible" in wolf["look"]
        assert c.post(f"/api/series/{sid}/film/storyboard").status_code == 409                      # characters first
        assert c.post(f"/api/series/{sid}/characters/wolf/library").status_code == 409            # approve before saving
        for cid in ("wolf", "rabbit"):
            assert c.post(f"/api/series/{sid}/characters/{cid}/approve").status_code == 200
        assert c.post(f"/api/series/{sid}/characters/wolf/library").status_code == 200
        lib = c.get("/api/series/library/characters").json()
        assert [x["name"] for x in lib] == ["Wolf"] and c.get(f"/api/series/{lib[0]['sheetUrl']}").headers["content-type"] == "image/png"

        # 3. the storyboard: frames only, with the prompt's timing and camera; nothing moves yet
        assert c.post(f"/api/series/{sid}/film/storyboard").status_code == 200
        snap = wait(c, sid, lambda s: idle(s) and s["episodes"] and s["episodes"][0]["parts"][0]["status"] in ("board_review", "error"), "storyboard", 300)
        p = snap["episodes"][0]["parts"][0]
        assert p["status"] == "board_review", p.get("error")
        shots = p["shots"]
        secs = [x["seconds"] for x in shots]
        assert secs[0] == 3 and 2 <= secs[1] <= 2.6 and secs[2] == 4 and p["storyboard"].endswith("storyboard.png")   # a line is never cut
        assert [x["blueprint"]["camera"]["move"] for x in shots] == ["truck_right", "orbit_left", "push_in"]
        assert all(x["files"].get("key") and not x["files"].get("clip") for x in shots)
        assert {x["models"]["key"]["model"] for x in shots} == {"qwen-image-edit"}
        assert "exact visual reference" not in shots[0]["models"]["key"]["prompt"] and "low angle" in shots[2]["models"]["key"]["prompt"]
        assert next(x for x in snap["film"]["stages"] if x["key"] == "storyboard")["state"] == "yours"

        # batch camera: a new lens on every shot redraws the frames; a new move on one shot changes no frame
        pd = store.part_dir(sid, "ep1", 1) / "shots"
        keys = lambda: {x["id"]: (pd / x["id"] / "key.png").stat().st_mtime_ns for x in shots}  # noqa: E731
        before = keys()
        r = c.post(f"/api/series/{sid}/episodes/ep1/parts/1/camera", json={"lens": 50})
        assert r.status_code == 200 and sorted(r.json()["changed"]) == sorted(x["id"] for x in shots)
        snap = wait(c, sid, lambda s: idle(s) and s["episodes"][0]["parts"][0]["status"] == "board_review", "re-board", 300)
        after = keys()
        assert all(after[k] != before[k] for k in after)
        assert all(x["stage"]["camera"]["lens"] == 50 for x in snap["episodes"][0]["parts"][0]["shots"])
        first = shots[0]["id"]
        r = c.post(f"/api/series/{sid}/episodes/ep1/parts/1/camera", json={"shots": [first], "move": "handheld"})
        assert r.json()["changed"] == [first]
        snap = wait(c, sid, lambda s: idle(s) and s["episodes"][0]["parts"][0]["status"] == "board_review", "re-board 2", 300)
        assert keys() == after and snap["episodes"][0]["parts"][0]["shots"][0]["blueprint"]["camera"]["move"] == "handheld"

        # 4-6. approve the storyboard → every shot animated (the wide singing shot is an action shot with the line over it)
        assert c.post(f"/api/series/{sid}/episodes/ep1/parts/1/board/approve").status_code == 200
        snap = wait(c, sid, lambda s: idle(s) and s["episodes"][0]["parts"][0]["status"] in ("review", "error"), "animate", 300)
        p = snap["episodes"][0]["parts"][0]
        assert p["status"] == "review", p.get("error")
        shots = p["shots"]
        assert [x["models"]["clip"]["model"] for x in shots] == ["wan-2.2", "infinitetalk", "wan-2.2"]
        assert after == keys()                                            # the approved frames were not redrawn
        assert "Use the first frame as the exact visual reference" in shots[0]["models"]["clip"]["prompt"]
        assert shots[1]["sfx"].startswith("water dripping at 0.5s") and shots[1]["models"]["sfx"]["model"] == "hunyuan-foley"
        assert p["sound"]["music"] == "playful orchestral music" and p["musicInfo"]["model"] == "ace-step"
        assert abs(p["seconds"] - 9) < 0.6

        # 7. approve → the film; the project files
        assert c.post(f"/api/series/{sid}/episodes/ep1/parts/1/approve").status_code == 200
        snap = wait(c, sid, lambda s: idle(s) and s["episodes"][0]["status"] == "done", "film")
        assert all(x["state"] == "done" for x in snap["film"]["stages"])
        r = c.get(f"/api/series/{sid}/episodes/ep1/export")
        assert r.status_code == 200 and r.headers["content-type"] == "application/zip"
        z = zipfile.ZipFile(io.BytesIO(r.content))
        names = set(z.namelist())
        for f in ("prompt.txt", "breakdown.json", "script.json", "consistency_manifest.json", "motion_blueprint.json", "README.txt",
                  "storyboard/collage_master.png", "storyboard/frames/frame_01.png", "storyboard/frames/frame_03.png",
                  "prompts/shot_01.txt", "renders/clip_03.mp4", "audio/line_01.wav", "final/final_master.mp4", "final/audio_mix.wav",
                  "assets/characters/wolf_sheet.png", "assets/characters/rabbit_voice.wav"):
            assert f in names, f
        mb = json.loads(z.read("motion_blueprint.json"))
        assert [round(x["start"]) for x in mb["shots"]] == [0, 3, 5] and mb["shots"][0]["blueprint"]["camera"]["move"] == "handheld"
        man = json.loads(z.read("consistency_manifest.json"))
        assert [x["name"] for x in man["characters"]] == ["Wolf", "Rabbit"] and man["design_dna"]["medium"]
        assert "Use the first frame as the exact visual reference" in z.read("prompts/shot_01.txt").decode()
        assert [x["kind"] for x in c.get("/api/series").json() if x["id"] == sid] == ["film"]

        # a second film casts the library's wolf: no drawing, already approved
        r = c.post("/api/series/films", data={"prompt": "0-2 sec: Wolf waves at the camera.\n2-4 sec: close-up, Wolf winks.",
                                              "crew": "builtin", "library": lib[0]["id"]})
        sid2 = r.json()["id"]
        snap = wait(c, sid2, lambda s: idle(s) and s["series"]["breakdown"].get("status") == "review", "breakdown 2")
        assert snap["series"]["breakdown"]["characters"][0]["library"] == lib[0]["id"]
        c.post(f"/api/series/{sid2}/breakdown/approve")
        snap = wait(c, sid2, lambda s: idle(s) and s["series"]["breakdown"].get("status") == "approved" and s["series"]["characters"], "cast 2")
        w2 = snap["series"]["characters"][0]
        assert w2["status"] == "approved" and w2["fromLibrary"] == lib[0]["id"] and w2["voice"]["sample"].endswith("voice_v1.wav")
        assert (store.sdir(sid2) / w2["sheet"]).read_bytes() == (store.sdir(sid) / next(x for x in c.get(f"/api/series/{sid}").json()["series"]["characters"] if x["id"] == "wolf")["sheet"]).read_bytes()
        assert c.delete(f"/api/series/library/characters/{lib[0]['id']}").json() == []
        assert Path(store.sdir(sid2)).is_dir()
