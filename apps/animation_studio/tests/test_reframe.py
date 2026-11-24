"""AI Reframe: scenes, face rules, smoothing, the filtergraph, a real render, the AI ranker and the clip's scene override."""
from __future__ import annotations

import re

import json
import shutil
import subprocess

import pytest

from studio.autoclip import cut, intake, pick, pipeline, reframe, store

needs = pytest.mark.skipif(not shutil.which("ffmpeg") or not reframe.status()["ready"], reason="ffmpeg/OpenCV face model missing")
try:
    import skimage.data as skd
    HAVE_FACE_IMG = True
except Exception:  # noqa: BLE001
    HAVE_FACE_IMG = False
face_img = pytest.mark.skipif(not HAVE_FACE_IMG, reason="scikit-image (a real face picture) missing")


@pytest.fixture(autouse=True)
def root(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "ROOT", tmp_path / "ac")
    monkeypatch.setattr(intake, "public_url", lambda u: u)


# ---------- a synthetic wide video with a real face ----------
def make_wide(path, secs=12, fps=25):
    import cv2
    import numpy as np
    a = skd.astronaut()[:, :, ::-1].copy()[10:250, 110:340]
    W, H = 1280, 720

    def paste(bg, x, y, wid):
        k = wid / 90.0
        im = cv2.resize(a, (int(230 * k), int(240 * k)))
        h, w = im.shape[:2]
        x0, y0 = int(x - w / 2), int(y - h / 2)
        xa, ya, xb, yb = max(0, x0), max(0, y0), min(W, x0 + w), min(H, y0 + h)
        bg[ya:yb, xa:xb] = im[ya - y0: yb - y0, xa - x0: xb - x0]
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}", "-r", str(fps), "-i", "-", "-f", "lavfi", "-i", f"sine=f=220:d={secs}",
                          "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(path)], stdin=subprocess.PIPE)
    rng = np.random.default_rng(1)
    for i in range(fps * secs):
        t = i / fps
        if t < 3:
            bg = np.full((H, W, 3), (60, 90, 40), np.uint8); paste(bg, 300 + t * 220, 360, 170)
        elif t < 6:
            bg = np.full((H, W, 3), (235, 235, 235), np.uint8); paste(bg, 330, 380, 170); paste(bg, 950, 380, 170)
        elif t < 9:
            bg = cv2.resize(rng.integers(0, 255, (H // 8, W // 8, 3)).astype(np.uint8), (W, H), interpolation=cv2.INTER_NEAREST)
            cv2.rectangle(bg, (384, 100), (896, 600), (30, 30, 200), -1); paste(bg, 1150, 600, 110)
        else:
            bg = np.full((H, W, 3), (30, 30, 30), np.uint8); cv2.circle(bg, (1000, 360), 150, (255, 255, 255), -1)
        p.stdin.write(bg.tobytes())
    p.stdin.close()
    p.wait()


@pytest.fixture(scope="module")
def wide(tmp_path_factory):
    p = tmp_path_factory.mktemp("rf") / "wide.mp4"
    make_wide(p)
    return p


# ---------- the rules, on made-up frames (no video needed) ----------
def fr(t, faces, col=None):
    return {"t": t, "faces": faces, "col": col or [1.0] * reframe.BINS}


def face(cx, w=0.15, cy=0.45, m=0.0):
    return {"cx": cx, "cy": cy, "w": w, "h": w * 1.6, "m": m}


def frames(n, faces_fn, fps=3.0):
    return [fr(i / fps, faces_fn(i)) for i in range(n)]


def plan_of(f, cuts=None, w=1920, h=1080, **kw):
    return reframe.plan_scenes(f, cuts or [0.0, f[-1]["t"] + 0.34], w, h, **kw)


def test_one_face_is_followed():
    s = plan_of(frames(12, lambda i: [face(0.3 + i * 0.01)]))[0]
    assert s["layout"] == "follow" and s["faces"] == 1 and "a" in s["tracks"]


def test_two_faces_apart_are_split():
    s = plan_of(frames(12, lambda i: [face(0.25), face(0.75)]))[0]
    assert s["layout"] == "split" and s["faces"] == 2


def test_two_faces_close_follow_the_one_talking():
    f = frames(12, lambda i: [face(0.42, m=0.5), face(0.55, m=9.0)])
    s = plan_of(f)[0]
    assert s["layout"] == "follow" and s["speaker"] == 1 and s["follow"] == "b"


def test_speaker_mode_follows_even_when_apart():
    f = frames(12, lambda i: [face(0.2, m=8.0), face(0.8, m=0.5)])
    s = plan_of(f, multi="speaker")[0]
    assert s["layout"] == "follow" and s["follow"] == "a"


def test_only_speaking_frames_decide_who_talks():
    words = [{"w": "x", "s": 0.0, "e": 2.0}]
    f = [fr(i / 3, [face(0.2, m=(1.0 if i < 6 else 20.0)), face(0.8, m=(5.0 if i < 6 else 0.0))]) for i in range(12)]
    s = plan_of(f, words=words, multi="speaker")[0]
    assert s["speaker"] == 1                                   # B moved most while words were being said (A's big motion came after the words ended)


def test_small_face_in_a_corner_is_a_face_cam():
    s = plan_of(frames(12, lambda i: [face(0.9, w=0.1, cy=0.85)]))[0]
    assert s["layout"] == "facecam"


def test_small_face_in_the_middle_is_still_followed():
    assert plan_of(frames(12, lambda i: [face(0.5, w=0.1, cy=0.5)]))[0]["layout"] == "follow"


def test_a_crowd_shows_the_whole_frame():
    s = plan_of(frames(12, lambda i: [face(0.2), face(0.4), face(0.6), face(0.8)]))[0]
    assert s["layout"] == "blur" and s["unclear"]


def test_no_faces_one_subject_is_followed_by_detail():
    col = [0.0] * reframe.BINS
    for j in range(40, 52):
        col[j] = 10.0
    s = plan_of([fr(i / 3, [], col) for i in range(12)])[0]
    assert s["layout"] == "salient" and s["tracks"]["sal"][0][1] > 0.6


def test_no_faces_detail_everywhere_is_blur():
    assert plan_of(frames(12, lambda i: []))[0]["layout"] == "blur"


def test_vertical_source_is_just_filled():
    assert plan_of(frames(12, lambda i: [face(0.5)]), w=1080, h=1920)[0]["layout"] == "fill"


def test_a_flicker_of_faces_does_not_make_a_face_scene():
    f = frames(12, lambda i: [face(0.5)] if i == 3 else [])
    assert plan_of(f)[0]["faces"] == 0


def test_scene_splits_when_the_number_of_faces_changes_and_stays():
    f = frames(24, lambda i: [face(0.3)] if i < 12 else [face(0.25), face(0.75)])
    cuts = reframe.refine_cuts(f, [0.0, 8.0])
    assert len(cuts) == 3 and 3.5 <= cuts[1] <= 4.5
    assert reframe.refine_cuts(frames(24, lambda i: [face(0.3)] if i != 5 else []), [0.0, 8.0]) == [0.0, 8.0]      # one dropped frame is not a scene


# ---------- smoothing ----------
def test_smoothing_holds_still_for_jitter_and_limits_speed():
    jitter = [0.5 + (0.01 if i % 2 else -0.01) for i in range(15)]
    assert len(set(round(v, 3) for v in reframe.smooth(jitter))) == 1
    jump = reframe.smooth([0.2] * 5 + [0.9] * 10)
    assert max(abs(b - a) for a, b in zip(jump, jump[1:])) <= 0.45 / 3 + 1e-9 and jump[-1] > 0.6


def test_simplify_keeps_the_bends_only():
    pts = [(i / 3, 0.5) for i in range(10)] + [(3 + i / 3, 0.5 + i * 0.05) for i in range(10)]
    s = reframe.simplify(pts)
    assert 3 <= len(s) <= 6 and s[0] == pts[0] and s[-1] == pts[-1]


def test_path_expression_holds_before_and_after():
    e = reframe._pl([[0.0, 0.2, 0.5, 0.1], [2.0, 0.6, 0.5, 0.1]], 1)
    assert e.startswith("(lt(t,0.000)*0.2000") and "gte(t,2.000)*0.6000" in e
    assert reframe._pl([[0.0, 0.5, 0.5, 0.1], [2.0, 0.5, 0.5, 0.1]], 1) == "0.5000"


# ---------- overrides ----------
def test_overrides_pin_and_unpin_and_unavailable_layouts_fall_back():
    plan = {"src": [1920, 1080], "scenes": plan_of(frames(12, lambda i: [face(0.3)]))}
    reframe.apply_overrides(plan, {"0": "blur"})
    sm = reframe.summary(plan)[0]
    assert sm["layout"] == "blur" and sm["pinned"] and "split" not in sm["can"]
    reframe.apply_overrides(plan, {"0": "split"})
    assert reframe.summary(plan)[0]["layout"] == "blur"                      # one face: a split can't be drawn
    reframe.apply_overrides(plan, {"0": "auto"})
    assert reframe.summary(plan)[0]["layout"] == "follow" and not reframe.summary(plan)[0]["pinned"]


def test_vision_label_is_applied_only_where_it_fits():
    sc = plan_of(frames(12, lambda i: [face(0.9, w=0.1, cy=0.85)]))[0]
    plan = {"src": [1920, 1080], "scenes": [sc]}
    assert sc["unclear"]
    asked = []

    def ask(system, prompt, imgs):
        asked.append(len(imgs))
        return {"kind": "gameplay", "people": 1, "layout": "facecam"}
    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg missing")
    # no real video: the frame grab fails quietly and nothing changes
    assert reframe.label_scenes(plan, "/nonexistent.mp4", 0, ask, lambda t: None) == 0 and sc["layout"] == "facecam"


# ---------- real video ----------
@needs
@face_img
def test_the_real_video_gets_the_right_layout_per_scene(wide):
    plan = reframe.analyse(str(wide), 0, 12)
    assert [s["layout"] for s in plan["scenes"]] == ["follow", "split", "facecam", "salient"]
    assert abs(plan["scenes"][1]["t0"] - 3.0) < 0.5 and plan["src"] == [1280, 720]
    follow = plan["scenes"][0]["tracks"]["a"]
    assert follow[-1][1] > follow[0][1] + 0.15                                # the crop moved right with the face


@needs
@face_img
def test_render_makes_a_vertical_video_with_every_layout(wide, tmp_path):
    plan = reframe.analyse(str(wide), 0, 12)
    out = tmp_path / "o.mp4"
    cut.cut(str(wide), str(out), 0, 12, "auto", "720p", None, plan)
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(out)], capture_output=True, text=True).stderr
    assert "720x1280" in r and "Audio" in r and "Duration: 00:00:12" in r
    for lay in reframe.LAYOUTS:                                              # every layout is valid ffmpeg on every scene that can draw it
        p2 = json.loads(json.dumps(plan))
        for s in p2["scenes"]:
            if reframe._can(s, lay):
                s["layout"] = lay
        cut.cut(str(wide), str(tmp_path / f"{lay}.mp4"), 0, 6, "auto", "720p", None, {**p2, "scenes": [s for s in p2["scenes"] if s["t1"] <= 6]})
        assert (tmp_path / f"{lay}.mp4").stat().st_size > 5000


@needs
@face_img
def test_captions_go_on_top_of_a_reframed_clip(wide, tmp_path):
    plan = reframe.analyse(str(wide), 0, 6)
    words = [{"w": "hello", "s": 0.5, "e": 1.0}, {"w": "there", "s": 1.0, "e": 1.6}]
    ass = cut.ass_for(words, 0, 6, "bounce", 720, 1280)
    cut.cut(str(wide), str(tmp_path / "c.mp4"), 0, 6, "auto", "720p", ass, plan)
    assert (tmp_path / "c.ass").is_file() and (tmp_path / "c.mp4").stat().st_size > 5000


# ---------- the AI ranker ----------
def fake_ask(rows):
    from studio.series import writers
    import pytest as _p
    return rows


def test_ai_rank_mixes_scores_and_returns_metadata(monkeypatch):
    from studio.series import writers
    moments = [{"start": i * 30, "end": i * 30 + 25, "score": sc} for i, sc in enumerate([9, 8, 1, 2])]
    texts = ["loud nothing", "calm but great story with a hook", "meh", "meh meh"]
    monkeypatch.setattr(writers, "ask", lambda s, who, system, prompt, log=None, **kw: {"clips": [
        {"n": 1, "score": 2, "title": "Nothing", "description": "d1", "hashtags": ["#a"]},
        {"n": 2, "score": 10, "title": "The big story", "description": "A story.", "hashtags": ["#story", "wow!"]},
        {"n": 3, "score": 3, "title": "T3"}, {"n": 4, "score": 4, "title": "T4"}]})
    keep, metas = pick.ai_rank({"id": "x", "crew": "ollama"}, moments, texts, 2)
    assert keep[0] == 1 and len(keep) == 2 and metas[0]["title"] == "The big story" and metas[0]["tags"] == ["story", "wow"]


def test_ai_rank_gives_up_on_junk_and_builtin():
    assert pick.ai_rank({"id": "x", "crew": "builtin"}, [{"start": 0, "end": 20, "score": 1}], ["words"], 1) is None


def test_ai_rank_needs_most_candidates_scored(monkeypatch):
    from studio.series import writers
    monkeypatch.setattr(writers, "ask", lambda *a, **k: {"clips": [{"n": 1, "score": 5, "title": "x"}]})
    ms = [{"start": i * 30, "end": i * 30 + 25, "score": 1} for i in range(6)]
    assert pick.ai_rank({"id": "x", "crew": "ollama"}, ms, ["t"] * 6, 2) is None


# ---------- the whole pipeline ----------
SRT = "1\n00:00:00,500 --> 00:00:02,500\nThis is the first thing we say\n\n2\n00:00:03,500 --> 00:00:05,500\nand here is a second thing\n\n3\n00:00:06,500 --> 00:00:08,500\nthe third part is here\n"


@needs
@face_img
def test_pipeline_with_auto_layout_and_ai_ranking(wide, monkeypatch):
    from studio.series import writers
    monkeypatch.setattr(writers, "ask", lambda s, who, system, prompt, log=None, **kw: {"clips": [
        {"n": i + 1, "score": 5 + (i % 3), "title": f"AI title {i + 1}", "description": f"About {i + 1}", "hashtags": ["tag"]} for i in range(30)]})
    monkeypatch.setattr(writers, "uses_ai", lambda s: True)
    monkeypatch.setattr("studio.autoclip.pipeline.writers", writers, raising=False)
    opts = pipeline.build_opts({"hype_only": "false", "count": 1, "min_seconds": 8, "max_seconds": 12, "layout": "auto", "crew": "ollama"})
    assert opts["layout"] == "auto"
    job = pipeline.new_job(opts, {"kind": "upload", "name": "x"})
    d = store.jdir(job["id"])
    shutil.copy(wide, d / "source.mp4")
    (d / "source.srt").write_text(SRT, "utf-8")
    pipeline._run(job["id"])
    j = store.load(job["id"])
    assert j["status"] == "done", j.get("error")
    c = j["clips"][0]
    assert c["title"].startswith("AI title") and "#tag" in c["description"] and c["ai_score"] >= 5
    assert c["reframe"] and {s["layout"] for s in c["reframe"]} & {"follow", "split", "facecam", "salient"}
    assert (d / "clips" / "clip-1.plan.json").is_file()


@needs
@face_img
def test_pipeline_falls_back_to_blur_when_face_tracking_is_missing(wide, monkeypatch):
    monkeypatch.setattr(reframe, "status", lambda: {"ready": False, "opencv": False, "model": True, "fix": "install opencv"})
    opts = pipeline.build_opts({"hype_only": "false", "count": 1, "min_seconds": 8, "max_seconds": 12, "layout": "auto"})
    job = pipeline.new_job(opts, {"kind": "upload", "name": "x"})
    d = store.jdir(job["id"])
    shutil.copy(wide, d / "source.mp4")
    pipeline._run(job["id"])
    j = store.load(job["id"])
    assert j["status"] == "done" and j["clips"][0]["file"] and not j["clips"][0].get("reframe")
    assert any("AI Reframe could not run" in x["text"] for x in j["log"])


@needs
@face_img
def test_http_scene_override_recuts_the_clip(wide, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from studio.autoclip import routes
    app = FastAPI()
    app.include_router(routes.router)
    c = TestClient(app)
    opts = pipeline.build_opts({"hype_only": "false", "count": 1, "min_seconds": 8, "max_seconds": 12, "layout": "auto"})
    job = pipeline.new_job(opts, {"kind": "upload", "name": "x"})
    d = store.jdir(job["id"])
    shutil.copy(wide, d / "source.mp4")
    pipeline._run(job["id"])
    cl = store.load(job["id"])["clips"][0]
    assert cl["reframe"]
    first = cl["reframe"][0]
    before = (d / "clips" / "clip-1.mp4").stat().st_size
    r = c.post(f"/api/autoclip/jobs/{job['id']}/clips/1/reframe", json={"scenes": {"0": "blur"}}).json()
    row = r["clips"][0]["reframe"][0]
    assert row["layout"] == "blur" and row["pinned"] and r["clips"][0]["rev"] == 1
    assert (d / "clips" / "clip-1.mp4").stat().st_size != before or first["layout"] == "blur"
    assert c.post(f"/api/autoclip/jobs/{job['id']}/clips/1/reframe", json={"scenes": {"0": "auto"}}).json()["clips"][0]["reframe"][0]["pinned"] is False
    assert c.post("/api/autoclip/jobs/nope/clips/1/reframe", json={}).status_code == 404


def test_overview_reports_whether_reframe_can_run():
    from studio.autoclip import routes
    cap = routes.capabilities()
    assert "ready" in cap["reframe"] and "auto" in cap["layouts"]


def test_gameplay_view_is_steady_and_detected(tmp_path):
    from studio.autoclip import pipeline
    frames = [{"t": i / 3, "faces": [{"cx": 0.5 + (i % 5) * 0.05, "cy": 0.5, "w": 0.2, "h": 0.3, "m": 1.0}], "col": [1.0] * reframe.BINS} for i in range(30)]
    plan = reframe.use_game({"scenes": [{"i": 0, "t0": 0, "t1": 5, "layout": "follow", "tracks": {}}]}, 4 / 3)
    assert plan["scenes"][0]["layout"] == "game" and reframe.resolve(plan["scenes"][0]) == "game"
    g = reframe.scene_graph(plan["scenes"][0], 0, 720, 1280, 1920, 1080)
    assert "crop=1440:1080" in g and "unsharp" in g and "(t" not in g.split("crop=")[1].split(",")[0]     # one fixed crop, no moving path
    assert reframe.stream_cam(frames, 1920, 1080) is None
    o = pipeline.build_opts({})
    assert pipeline.is_game(o, {"title": "IShowSpeed GTA 6 stream", "source": {}}) and not pipeline.is_game(o, {"title": "Stand-up comedy special", "source": {}})
    assert pipeline.is_game(pipeline.build_opts({"content": "game"}), {"title": "x", "source": {}}) and not pipeline.is_game(pipeline.build_opts({"content": "talk"}), {"title": "GTA 6", "source": {}})
    assert abs(pipeline.game_ar(pipeline.build_opts({"game_view": "close"})) - 1.0) < 1e-6 and pipeline.build_opts({"game_view": "bad"})["game_view"] == "auto"
    assert abs(pipeline.game_ar(pipeline.build_opts({}), cam=True) - 16 / 9) < 1e-6 and abs(pipeline.game_ar(pipeline.build_opts({})) - 4 / 3) < 1e-6


def test_close_shot_and_stream_stack():
    sc = {"i": 0, "t0": 0, "t1": 4, "layout": "follow", "follow": "a", "face_w": 0.06, "tracks": {"a": [[0, 0.5, 0.4, 0.06]]}}
    g = reframe.scene_graph(sc, 0, 720, 1280, 1920, 1080)
    cw = int(re.search(r"crop=(\d+):", g).group(1))
    assert cw < 607 * 0.7                                        # zoomed in from the full-height slice (607 px wide) to a close shot
    hb, gh = reframe.cam_split(16 / 9, 720, 1280)
    assert 0.3 <= hb <= 0.55 and abs(gh - 405 / 1280) < 0.01 and hb + gh <= 0.85
    cam = {"i": 0, "t0": 0, "t1": 4, "layout": "camtop", "face_w": 0.04, "ar": 16 / 9, "tracks": {"a": [[0, 0.1, 0.3, 0.04]]}}
    g2 = reframe.scene_graph(cam, 0, 720, 1280, 1920, 1080)
    assert "vstack=inputs=3" in g2 and "crop=1920:1080" in g2            # the whole game, not a crop of it
    from studio.autoclip import cut
    a = cut.ass_for([{"w": "go", "s": 0.5, "e": 0.9}], 0, 3, "bounce", 720, 1280, cam_top=hb)
    assert f"\\pos(360,{int(hb * 1280)})" in a
