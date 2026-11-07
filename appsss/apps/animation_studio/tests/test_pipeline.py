"""The whole ReelMimic workflow through the HTTP API, exactly as the Animations tab drives it.

Built-in crew (no AI) and a stand-in Ollama server (tests/fake_ollama.py, same HTTP API as Ollama) that answers
like a local model would, including broken replies, so the AI path, retries and vision reviews are exercised
without downloading a model. Each test renders real videos with FFmpeg (a few minutes in total)."""
from __future__ import annotations

import json
import os
import socket
import subprocess
import threading
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from studio import config
from studio.server import app

from . import fake_ollama


def wait(c: TestClient, jid: str, stages: tuple[str, ...], timeout: float = 600) -> dict:
    t0 = time.time()
    while True:
        s = c.get(f"/api/projects/{jid}").json()
        if s["job"]["stage"] in stages:
            return s
        if s["job"]["stage"] == "error" and "error" not in stages:
            raise AssertionError(f"project failed: {s['job'].get('failed')}: {s['job'].get('error')}")
        if time.time() - t0 > timeout:
            raise AssertionError(f"timed out waiting for {stages}; now {s['job']['stage']}")
        time.sleep(1.0)


def duration(f: Path) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(f)], capture_output=True, text=True)
    return float(r.stdout.strip())


def create(c: TestClient, ref: Path, brief: str, agent: str, **extra) -> str:
    with open(ref, "rb") as f:
        r = c.post("/api/projects", files={"reference": ("reference.mp4", f, "video/mp4")},
                   data={"brief": brief, "agent": agent, "lang": "en", **extra})
    assert r.status_code == 200, r.text
    return r.json()["id"]


def test_builtin_crew_full_workflow(reference_video):
    with TestClient(app) as c:
        assert c.get("/api/health").json()["ok"]
        assert c.get("/api/agents").json()["builtin"]
        assert c.post("/api/projects", data={"brief": "x", "agent": "builtin"}).status_code == 400        # no reference
        jid = create(c, reference_video, "A 10-second story about a shy cat who learns to dance at a party", "builtin", chunkRounds="2")
        assert c.get(f"/api/projects/{jid}").json()["job"]["settings"] == {"chunkRounds": 2}

        # analysis → style → plan (with characters drafted in parallel and style frames)
        s = wait(c, jid, ("plan_review",))
        assert s["report"]["pacing"]["count"] >= 2 and s["route"]["engine"]
        plan = s["plan"]
        assert plan["title"].startswith("A shy cat") and 8 <= plan["format"]["duration_s"] <= 12
        assert all(s_.get("ref_shot") is not None and s_.get("camera") for s_ in plan["shots"])
        d = config.PROJECTS / jid
        assert (d / "analysis" / "STYLE.md").exists() and (d / "STORYBOARD.md").exists()
        assert plan["style_frames"] and all((d / f).exists() for f in plan["style_frames"])
        assert c.get(f"/files/{jid}/{plan['style_frames'][0]}").status_code == 200
        assert c.get(f"/files/{jid}/../../etc/passwd").status_code == 404

        # chat → replan
        assert c.post(f"/api/projects/{jid}/message", json={"text": ""}).status_code == 400
        c.post(f"/api/projects/{jid}/message", json={"text": "Make it vertical 9:16 please"})
        s = wait(c, jid, ("plan_review",)) if c.get(f"/api/projects/{jid}").json()["job"]["stage"] != "plan_review" else s
        for _ in range(60):
            s = c.get(f"/api/projects/{jid}").json()
            if (s["plan"] or {}).get("version", 1) > 1 and s["job"]["stage"] == "plan_review":
                break
            time.sleep(1)
        assert s["plan"]["version"] == 2 and s["plan"]["format"]["height"] > s["plan"]["format"]["width"]

        # review rounds can be changed any time
        r = c.post(f"/api/projects/{jid}/settings", json={"finalRounds": 1})
        assert r.json()["rounds"]["values"]["finalRounds"] == 1
        assert c.post(f"/api/projects/{jid}/settings", json={"finalRounds": 99}).status_code == 400

        # required inputs (a song, lyrics…) block approval until provided or skipped
        r = c.post(f"/api/projects/{jid}/approve")
        if r.status_code == 409:
            assert r.json()["error"].startswith("Still needs your input")
            for item in r.json()["open"]:
                snap = c.post(f"/api/projects/{jid}/waive", json={"input": item["id"]}).json()
                assert next(x for x in snap["requiredInputs"] if x["id"] == item["id"])["status"] == "waived"
            r = c.post(f"/api/projects/{jid}/approve")
        # approve → cast gate → shots (built, reviewed, fixed) → assembly → critic
        assert r.json() == {"ok": True}
        s = wait(c, jid, ("done", "needs_input"), 900)
        if s["job"]["stage"] == "needs_input":          # a part still failing after its rounds: accept it, like the UI button
            c.post(f"/api/projects/{jid}/accept")
            s = wait(c, jid, ("done",), 600)
        assert s["video"] == "out/video.mp4"
        planned = sum(x["end_s"] - x["start_s"] for x in s["plan"]["shots"])
        assert abs(duration(d / "out" / "video.mp4") - planned) < 0.3
        assert s["cast"]["sheets"] and s["shots"] and s["production"]["chunks"]
        assert s["job"]["pipeline"]["cast"]["pass"] and all(v["state"] == "passed" for v in s["job"]["pipeline"]["chunks"].values())
        crit = s["critique"]
        assert set(crit) >= {"pass", "scores", "must_fix", "summary"}
        log = [json.loads(x) for x in (d / "logs" / "events.jsonl").read_text("utf-8").splitlines()]
        assert {e.get("phase") for e in log if e["type"] == "turn"} >= {"style", "plan", "pre_cast", "plan_frames", "setup", "cast_qa",
                                                                       "build_chunk", "shot_qa", "assemble", "critique"}

        # a timed note on the video → that moment is revised (with before/after proof) → critic again
        c.post(f"/api/projects/{jid}/message", json={"text": "Please change these moments (1):\n1. [0:02.0] make it bigger",
                                                      "meta": {"notes": [{"t": 2.0, "text": "the cat is too small here, bigger"}]}})
        time.sleep(1)
        s = wait(c, jid, ("done", "needs_input"), 600)
        fixes = json.loads((d / "out" / "check" / "fixes.json").read_text("utf-8"))
        assert any(f["status"] == "fixed" and f.get("before") and f.get("after") for f in fixes)
        assert c.get("/api/projects").json()[0]["id"] in {jid, *[p["id"] for p in c.get("/api/projects").json()]}


def test_stop_and_continue(reference_video):
    with TestClient(app) as c:
        jid = create(c, reference_video, "A 6-second pixel art clip about a robot", "builtin")
        time.sleep(1.0)
        c.post(f"/api/projects/{jid}/cancel")
        s = wait(c, jid, ("error", "plan_review"), 120)
        if s["job"]["stage"] == "error":
            assert s["job"]["error"] == "Cancelled"
            assert c.post(f"/api/projects/{jid}/retry").json() == {"ok": True}
            s = wait(c, jid, ("plan_review",), 300)
        assert s["plan"]["shots"]


def _free_port() -> int:
    with socket.socket() as sk:
        sk.bind(("127.0.0.1", 0))
        return sk.getsockname()[1]


@pytest.fixture(scope="module")
def ollama_standin():
    import uvicorn
    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(fake_ollama.app, host="127.0.0.1", port=port, log_level="warning"))
    th = threading.Thread(target=server.run, daemon=True)
    th.start()
    for _ in range(50):
        try:
            socket.create_connection(("127.0.0.1", port), 0.2).close()
            break
        except OSError:
            time.sleep(0.1)
    os.environ["OLLAMA_URL"] = f"http://127.0.0.1:{port}"
    yield port
    server.should_exit = True
    os.environ.pop("OLLAMA_URL", None)
    os.environ.pop("STUDIO_OLLAMA_VISION_MODEL", None)


def test_local_ai_crew_via_ollama(reference_video, ollama_standin):
    with TestClient(app) as c:
        info = c.get("/api/agents/info").json()
        assert info["default"] == "ollama"
        oll = next(a for a in info["agents"] if a["id"] == "ollama")
        assert oll["ready"] and oll["tier"] == "local" and "qwen2.5vl:7b" in oll["models"]
        # AI settings: vision model so reviewers look at frames; a key for a free cloud crew
        info = c.post("/api/agents/settings", json={"agent": "ollama", "visionModel": "qwen2.5vl:7b"}).json()
        assert next(a for a in info["agents"] if a["id"] == "ollama")["vision"]
        info = c.post("/api/agents/settings", json={"agent": "groq", "key": "gsk_test"}).json()
        assert next(a for a in info["agents"] if a["id"] == "groq")["hasKey"]
        c.post("/api/agents/settings", json={"agent": "groq", "key": ""})
        assert c.post("/api/agents/settings", json={"agent": "nope"}).status_code == 400
        # model download with progress
        c.post("/api/agents/pull", json={"model": "llama3.2:3b"})
        for _ in range(40):
            p = c.get("/api/agents/info").json()["pulls"].get("llama3.2:3b") or {}
            if p.get("done"):
                break
            time.sleep(0.25)
        assert p.get("status") == "success"

        fake_ollama.CALLS.clear()
        jid = create(c, reference_video, "A 12-second whiteboard story about a girl who wants to touch the moon", "ollama")
        s = wait(c, jid, ("plan_review",))
        plan = s["plan"]
        assert plan["title"] == "Luna and the Moon"                          # the story came from the (stand-in) model
        assert {ch["id"] for ch in plan["characters"]} == {"luna", "pip"}
        assert any(a["cast"] == "pip" for sh in plan["shots"] for a in sh["scene"]["actors"])
        luna = json.loads((config.PROJECTS / jid / "build" / "assets" / "cast" / "luna.json").read_text("utf-8"))
        assert luna["hair"] == "long" and luna["top"] == "hoodie"           # the character designer's answer was used
        assert any(x["broken"] for x in fake_ollama.CALLS)                    # broken replies happened…
        events = (config.PROJECTS / jid / "logs" / "events.jsonl").read_text("utf-8")
        assert "wasn't valid JSON twice" not in events                         # …and were retried successfully

        c.post(f"/api/projects/{jid}/approve")
        s = wait(c, jid, ("done", "needs_input"), 900)
        if s["job"]["stage"] == "needs_input":
            c.post(f"/api/projects/{jid}/accept")
            s = wait(c, jid, ("done",), 600)
        assert s["video"] and s["critique"]["summary"].startswith("Pacing follows")
        vision = [x for x in fake_ollama.CALLS if x["images"]]
        assert vision and all(x["model"] == "qwen2.5vl:7b" for x in vision)     # reviewers looked at sheets and frames
        assert all(x["model"] == "qwen2.5:7b" for x in fake_ollama.CALLS if not x["images"])


def test_ollama_down_gives_a_clear_error(reference_video):
    os.environ["OLLAMA_URL"] = f"http://127.0.0.1:{_free_port()}"
    try:
        with TestClient(app) as c:
            oll = next(a for a in c.get("/api/agents/info").json()["agents"] if a["id"] == "ollama")
            assert not oll["ready"] and "ollama serve" in oll["fix"]
            jid = create(c, reference_video, "A 6-second clip about a fox", "ollama")
            s = wait(c, jid, ("error",), 300)
            assert s["job"]["failed"] == "styling" and "Ollama isn't reachable" in s["job"]["error"] and "ollama serve" in s["job"]["error"]
    finally:
        os.environ.pop("OLLAMA_URL", None)
