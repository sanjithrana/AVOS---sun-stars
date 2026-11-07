"""The creative core shared by Facts and Animations: Design DNA, scene graph, motion blueprint, prompt compiler, skills."""
from pathlib import Path

from agentic_core.creative import compiler as C, dna as D, scene as S, skills as K

ROOT = Path(__file__).resolve().parents[2]
NAMES = {"raju": "Raju", "amma": "Amma"}


def test_design_dna_is_repaired_and_compiled():
    d = D.normalize({"line": "thick dark outlines", "palette": ["#ff0000", "red", "#00FF00"], "camera": {"default_lens": 500, "angle": 3},
                     "motion": {"squash_stretch": 0, "pacing": "snappy", "unknown": 1}, "avoid": "not a list"})
    assert d["palette"] == ["#FF0000", "#00FF00"] and d["camera"]["default_lens"] == 135 and d["camera"]["angle"] == "eye level"
    assert d["motion"]["squash_stretch"] is False and d["motion"]["pacing"] == "snappy" and "unknown" not in d["motion"]
    assert d["avoid"] == D.DEFAULT["avoid"] and d["medium"] == D.DEFAULT["medium"]
    assert "line: thick dark outlines" in D.style_clause(d) and "#FF0000" in D.style_clause(d)
    assert "squash and stretch" not in D.motion_clause(d) and "snappy pacing" in D.motion_clause(d)
    assert D.normalize(None) == D.normalize({}) and "photorealism" in D.negative(d) and "extra fingers" in D.negative(d)


def test_scene_graph_blocks_people_and_frames_the_speaker():
    sc = S.normalize_scene({"actors": [{"id": "amma", "speaking": True, "expression": "furious"}],
                            "props": [{"name": "ladle", "held_by": "amma"}, {"name": "ghost prop", "held_by": "ghost"}]},
                           subjects=["raju", "amma"], framing="close-up", location="kitchen", time="night")
    assert [a["id"] for a in sc["actors"]] == ["raju", "amma"]
    assert S.normalize_scene({"actors": [{"id": "x", "x": 99}]})["actors"][0]["x"] == 6.0          # clamped to the stage
    raju, amma = sc["actors"][0], sc["actors"][1]
    assert raju["x"] < 0 < amma["x"] and raju["facing"] != "camera" and amma["speaking"]
    assert sc["camera"]["lens"] == 85 and sc["camera"]["target"][0] == amma["x"]            # close-up on the speaker
    assert sc["lighting"]["key"].startswith("cool moonlight") and sc["props"][0]["held_by"] == "amma" and sc["props"][1]["held_by"] is None
    wide = S.normalize_scene({}, subjects=["raju", "amma"], framing="wide")
    assert wide["camera"]["lens"] == 24 and wide["camera"]["position"][2] > 6
    assert S.normalize_scene({"framing": "fisheye"})["framing"] == "medium"
    # a prompt's "low angle" / "wide lens" when no exact camera is given
    low = S.normalize_scene({"angle": "dynamic low-angle", "lens": 18}, subjects=["raju"], framing="medium")
    assert low["camera"]["position"][1] < low["camera"]["target"][1] and low["camera"]["lens"] == 18
    assert C._angle(low["camera"]) == "low angle" and S.angle_of("bird's-eye view") == "overhead" and S.angle_of("") == "eye level"
    high = S.normalize_scene({"angle": "high angle"}, subjects=["raju"], framing="close-up")
    assert C._angle(high["camera"]) == "high angle"


def test_motion_blueprint_moves_eases_retime():
    sc = S.normalize_scene({}, subjects=["raju"], framing="medium")
    m = S.normalize_motion({"camera": {"move": "Dolly-In", "ease": "bounce"},
                            "tracks": [{"target": "raju", "keys": [{"t": 9, "action": "sits"}, {"t": 0, "action": "stands"}, {"t": 1, "action": ""}]},
                                       {"target": "ghost", "keys": [{"t": 0, "action": "boo"}]}]}, sc, duration=3.0, speaker="raju")
    assert m["camera"]["move"] == "push_in" and m["camera"]["ease"] == "power1.inOut"
    assert m["camera"]["to"]["position"][2] < m["camera"]["from"]["position"][2]               # it moved closer
    assert [k["action"] for k in m["tracks"][0]["keys"]] == ["stands", "sits"] and m["tracks"][0]["keys"][1]["t"] == 3.0
    assert len(m["tracks"]) == 1 and m["lipsync"] == "raju"
    r = S.retime(m, 6.0)
    assert r["duration"] == 6.0 and r["tracks"][0]["keys"][1]["t"] == 6.0
    half = S.camera_at(m, 1.5)
    assert m["camera"]["to"]["position"][2] < half["position"][2] < m["camera"]["from"]["position"][2]
    for mv in S.MOVES:
        out = S.move_camera(sc["camera"], mv)
        assert set(out) == {"position", "target", "lens"}
    assert S.move_camera(sc["camera"], "zoom_in")["lens"] > sc["camera"]["lens"]
    assert S.changed_parts(sc, sc, m, r) == {"motion"} and S.changed_parts(sc, {**sc, "time": "night"}, m, m) == {"picture", "motion"}


def test_compiler_is_deterministic_and_speaks_each_models_language():
    sc = S.normalize_scene({"actors": [{"id": "raju", "speaking": True, "pose": "hides the remote", "expression": "guilty"}],
                            "props": [{"name": "TV remote", "held_by": "raju"}]}, subjects=["raju", "amma"], framing="medium",
                           location="kitchen", time="evening")
    m = S.normalize_motion({"camera": {"move": "push_in", "ease": "power2.out"},
                            "tracks": [{"target": "raju", "keys": [{"t": 0, "action": "hides the remote"}, {"t": 1.5, "action": "backs away"}]}],
                            "environment": [{"t": 0.5, "text": "steam rises from the cooker"}]}, sc, duration=3.0, speaker="raju")
    dna = D.normalize({"line": "thick dark outlines"})
    a = C.compile_shot(sc, m, dna, NAMES, model="ltx-2.3", refs=["Raju's character sheet", "the kitchen"])
    b = C.compile_shot(sc, m, dna, NAMES, model="ltx-2.3", refs=["Raju's character sheet", "the kitchen"])
    assert a == b and len(a["params_hash"]) == 64
    kp = a["keyframe_prompt"]
    assert kp.startswith("picture 1 is Raju's character sheet; picture 2 is the kitchen.")
    assert "Raju on the left: hides the remote, guilty expression, facing Amma, mouth open mid-word" in kp
    assert "Everyone else keeps their mouth closed" in kp and "Prop: TV remote, held by Raju." in kp and "line: thick dark outlines" in kp
    ltx = a["motion_prompt"]
    assert ltx.startswith("Raju hides the remote. At 0.5s, steam rises from the cooker. At 1.5s, Raju backs away.")
    assert "The camera slowly pushes in with a smooth ease" in ltx and "exact visual reference" in ltx and ltx.endswith("no costume change.")
    wan = C.motion_prompt(m, sc, dna, NAMES, "wan-2.2")
    talk = C.motion_prompt(m, sc, dna, NAMES, "infinitetalk", emotion="scared")
    assert "The shot shows" not in wan and talk.startswith("Raju talks scared, lips in sync") and "no face change" in talk
    # the storyboard-frame template: reference first, then only this shot, the camera, the motion, keep the design
    assert wan.startswith("Use the first frame as the exact visual reference") and "Animate only this shot: Raju hides the remote." in wan
    assert "Camera movement: the camera slowly pushes in" in wan and wan.endswith("No character redesign, no face change, no costume change.")
    other = C.compile_shot(sc, S.normalize_motion({"camera": {"move": "static"}}, sc, duration=3.0), dna, NAMES, model="ltx-2.3")
    assert other["params_hash"] != a["params_hash"]


def test_skills_are_loaded_from_the_skills_folder():
    names = {k["name"] for k in K.catalog()}
    assert names >= {"avos-series-bible", "avos-design-dna", "avos-head-writer", "avos-scriptwriter", "avos-script-editor",
                     "avos-scene-director", "avos-sound-designer", "avos-shot-qa", "avos-continuity", "avos-prompt-compiler"}
    body = K.load("avos-scene-director")
    assert body.startswith("# Scene director") and "---" not in body.splitlines()[0]
    assert all(k["description"] and k["used_by"] for k in K.catalog())
    assert K.load("no-such-skill", "fallback") == "fallback"


def test_the_studio_has_an_identical_copy():
    for f in ("__init__.py", "dna.py", "scene.py", "compiler.py", "skills.py"):
        assert (ROOT / "agentic_core/creative" / f).read_text() == (ROOT / "animation_studio/studio/creative" / f).read_text(), f


def test_facts_clips_are_compiled_from_a_motion_blueprint():
    from agentic_core.pipelines.shot.motion import facts_motion
    from agentic_core.styles import VIRAL_3D
    from packages.contracts.shotspec import Camera, ShotContent, ShotType
    from packages.contracts.world_state import CharacterState

    content = ShotContent(beat_label="b1", start_time=0, end_time=4.0, description="A man punches a giant gorilla",
                          camera=Camera(shot_type=ShotType.CLOSE_UP, movement="slow dolly in", lens_mm=85),
                          characters={"man": CharacterState(emotion="determined", position="left")},
                          environment={"location": "blue grid studio", "time_of_day": "day", "weather": "rain"})
    plan = facts_motion(content, VIRAL_3D, model="ltx-2.3")
    bp, sc = plan["blueprint"], plan["scene"]
    assert bp["camera"]["move"] == "push_in" and bp["duration"] == 4.0 and sc["framing"] == "close-up" and sc["camera"]["lens"] == 85
    assert sc["actors"][0]["x"] < 0 and sc["actors"][0]["expression"] == "determined"
    assert plan["prompt"].startswith("A man punches a giant gorilla.")
    assert "rain weather moving in the background" in plan["prompt"] and "photorealistic 3D CGI render" in plan["prompt"]
    assert "smooth realistic 3D character animation" in plan["prompt"] and "The camera slowly pushes in" in plan["prompt"]
    assert facts_motion(content, VIRAL_3D, model="ltx-2.3") == plan                      # deterministic
    assert facts_motion(content, VIRAL_3D, model="wan-2.2")["prompt"] != plan["prompt"]  # phrased per model
