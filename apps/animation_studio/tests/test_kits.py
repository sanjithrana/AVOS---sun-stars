"""The kits: 29 skills (story engines, animation styles, 3D styles) running through one Skill Lab module.
Registry and helpers always run; the browser tests run only where Playwright + Chromium + ffmpeg exist (the AI and the voice are faked)."""
from __future__ import annotations

import json
import re
import subprocess

import pytest

from studio.kits import author, catalog as C, engine, paths, skill as KS
from studio.series import writers
from studio.skilllab import pipeline, store

BROWSER = engine.status()["parts"]
needs_browser = pytest.mark.skipif(not (BROWSER["playwright"] and BROWSER["chromium"] and BROWSER["ffmpeg"]),
                                   reason="Playwright + Chromium + ffmpeg are not installed here")


def test_29_skills_in_three_groups():
    ks = {k: v for k, v in pipeline.SKILLS.items() if k.startswith(C.PREFIX)}
    assert len(ks) == 29
    groups = {}
    for v in ks.values():
        groups.setdefault(v.INFO["group"], []).append(v.INFO["name"])
    assert {g: len(n) for g, n in groups.items()} == {C.G_STORY: 4, C.G_ANIM: 10, C.G_3D: 15}
    assert len({v.INFO["name"] for v in ks.values()}) == 29
    assert all(v.INFO.get("engine") and v.INFO.get("slow") for v in ks.values())        # tagged slow + best quality in the grid
    # every skill that films many shots is tagged; only the two that are drawn in code in seconds are not
    assert {k for k, v in pipeline.SKILLS.items() if not v.INFO.get("slow")} == {"motion-graphics", "asmr-cutting"}
    assert all(v.INFO.get("slow_label") for v in pipeline.SKILLS.values() if v.INFO.get("slow"))


def test_every_skill_reaches_the_pipeline_with_its_four_stages():
    for sid in (k for k in pipeline.SKILLS if k.startswith(C.PREFIX)):
        sp = pipeline.spec_of({"skill": sid})
        assert sp["stages"] == KS.STAGES and set(sp["run"]) == set(KS.STAGES)


def test_every_kit_file_the_skills_rely_on_is_shipped():
    for k in C.ANIM:
        assert (paths.ASSETS / "anim" / "references" / "styles" / f"{k}.md").is_file(), k
    assert (paths.ASSETS / "anim" / "references" / "player-template.html").is_file()
    for k in C.STYLES3D:
        assert (paths.ASSETS / "styles3d" / "styles" / f"{k}.js").is_file(), k
    for k, d in C.STORY.items():
        base = paths.ASSETS / d["dir"]
        assert (base / "scripts" / "pack.py").is_file() and (base / "engine" / "player.html").is_file() and (base / "references" / "engine.md").is_file(), k
        assert list((base / "examples").glob("*/story.js")), k
    assert paths.THREE.stat().st_size > 500_000


def test_code_pinning_and_timing_helpers():
    assert author.code_of("Here:\n```js\nwindow.SHORT = {a:1}\n```\nbye") == "window.SHORT = {a:1}"
    assert author.code_of("plain code") == "plain code"
    out = author.pin_script("window.SHORT = { title: 'x', script: `old words`, tail: 1 }", "New `words` here")
    assert "old words" not in out and "New \\`words\\` here" in out
    assert "window.SHORT.script" in author.pin_script("window.SHORT = { title: 'x' }", "hello")
    words = [{"text": "Hi", "start": 0.0, "end": 0.3}, {"text": "there.", "start": 0.3, "end": 0.8}, {"text": "Next", "start": 1.0, "end": 1.4}]
    assert author.timing_summary(words).endswith("ends 1.4s")


def test_the_script_is_kept_when_you_bring_your_own(monkeypatch):
    own = " ".join(["word"] * 50)
    out = author.write_script({"crew": "builtin"}, paths.ASSETS / "cartoon", own, 30, lambda e: None)
    assert out["own"] and out["script"] == own
    monkeypatch.setattr(writers, "ask", lambda *a, **k: {"title": "Pig", "script": "Two big empires nearly went to war. Over one little pig. It sounds like a joke but it is true."})
    out = author.write_script({"crew": "groq"}, paths.ASSETS / "cartoon", "the pig war", 30, lambda e: None)
    assert out["title"] == "Pig" and "little pig" in out["script"]
    monkeypatch.setattr(writers, "ask", lambda *a, **k: None)
    with pytest.raises(writers.WriterError):
        author.write_script({"crew": "groq"}, paths.ASSETS / "cartoon", "x", 30, lambda e: None)


def test_repair_loop_sends_the_error_back_and_gives_up_after_three(monkeypatch):
    seen = []
    answers = iter(["bad1", "bad2", "good"])
    monkeypatch.setattr(author, "ask_text", lambda s, who, system, prompt, log=None, **k: (seen.append(prompt), next(answers))[1])
    code = author.build_with_repair({}, "w", "sys", "make it", lambda c: c, lambda c: None if c == "good" else f"boom {c}", lambda e: None)
    assert code == "good" and "boom bad1" in seen[1] and "boom bad2" in seen[2]
    monkeypatch.setattr(author, "ask_text", lambda *a, **k: "bad")
    with pytest.raises(writers.WriterError, match="after 3 repairs"):
        author.build_with_repair({}, "w", "sys", "make it", lambda c: c, lambda c: "boom", lambda e: None)


def test_a_run_without_an_ai_writer_says_what_to_do():
    pid = store.new_id()
    store.save({"id": pid, "skill": "kit-cartoon", "subject": "the pig war", "aspect": "9:16", "seconds": 30, "media": "media", "crew": "builtin",
                "status": "working", "stage": "script", "steps": {}, "log": []})
    pipeline._run(pid, "script")
    p = store.load(pid)
    assert p["status"] == "error" and "AI writer" in (p.get("error") or "")


def test_engine_status_names_what_is_missing():
    st = engine.status()
    assert set(st["parts"]) == {"ffmpeg", "playwright", "edge_tts", "chromium"}
    assert st["ready"] == all(st["parts"].values()) and (st["ready"] or st["fix"])


# ---------- real browser ----------
def _silent(path, seconds):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono", "-t", str(seconds), str(path)], check=True)


def _fake_voice(monkeypatch, words, seconds):
    from studio.kits import voice as V

    def narrate(script, who, out_dir, kit_dir=None):
        out_dir.mkdir(parents=True, exist_ok=True)
        _silent(out_dir / "voice.mp3", seconds)
        (out_dir / "words.json").write_text(json.dumps(words))
        return {"file": "voice.mp3", "words": len(words), "seconds": seconds}
    monkeypatch.setattr(V, "narrate", narrate)
    monkeypatch.setattr(engine, "ensure", lambda log=None: None)       # the tests must not install anything


def _run(kit_id, subject, **extra):
    pid = store.new_id()
    store.save({"id": pid, "skill": kit_id, "subject": subject, "aspect": "9:16", "seconds": 30, "media": "media", "crew": "groq", "voice": "male",
                "status": "working", "stage": "script", "steps": {}, "log": [], **extra})
    pipeline._run(pid, "script")
    return pid, store.load(pid)


@needs_browser
def test_story_engine_end_to_end_with_a_faked_writer(monkeypatch):
    ex = paths.ASSETS / "cartoon" / "examples" / "emu-war"
    script = (ex / "script.txt").read_text().strip()
    words = json.loads((ex / "words.json").read_text())
    story = (ex / "story.js").read_text()
    monkeypatch.setattr(writers, "ask", lambda *a, **k: {"title": "The Great Emu War", "script": script})
    monkeypatch.setattr(author, "ask_text", lambda *a, **k: "```js\n" + story + "\n```")
    _fake_voice(monkeypatch, words, words[-1]["end"] + 0.3)
    monkeypatch.setattr(KS, "FRAME_LIMIT", 12)
    pid, p = _run("kit-cartoon", "the emu war")
    assert p["status"] == "done", p.get("error")
    d = store.pdir(pid)
    assert (d / "final.mp4").stat().st_size > 5000 and len(p["stills"]) == 3 and (d / p["stills"][1]).stat().st_size > 5000
    info = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,width,height", "-of", "json", str(d / "final.mp4")],
                          capture_output=True, text=True).stdout
    assert '"width": 540' in info and "audio" in info
    assert {o["key"] for o in KS.outputs_of(p)} >= {"still1", "final"}


@needs_browser
def test_a_broken_file_is_repaired_from_the_browser_error(monkeypatch):
    ex = paths.ASSETS / "cartoon" / "examples" / "emu-war"
    script = (ex / "script.txt").read_text().strip()
    words = json.loads((ex / "words.json").read_text())
    good = (ex / "story.js").read_text()
    prompts = []
    replies = iter(["window.SHORT = { title: 'x', script: `a`, setup(T) { thisFunctionDoesNotExist(); }, frame() {} };", good])
    monkeypatch.setattr(writers, "ask", lambda *a, **k: {"title": "Emu", "script": script})
    monkeypatch.setattr(author, "ask_text", lambda s, who, system, prompt, *a, **k: (prompts.append(prompt), next(replies))[1])
    _fake_voice(monkeypatch, words, words[-1]["end"] + 0.3)
    monkeypatch.setattr(KS, "FRAME_LIMIT", 6)
    pid, p = _run("kit-cartoon", "emu")
    assert p["status"] == "done", p.get("error")
    assert len(prompts) == 2 and "thisFunctionDoesNotExist" in prompts[1]


@needs_browser
def test_a_3d_style_end_to_end_with_a_faked_writer(monkeypatch):
    ref = (paths.ASSETS / "styles3d" / "styles" / "blueprint.js").read_text()
    words = [{"text": w, "start": i * 0.4, "end": i * 0.4 + 0.35} for i, w in enumerate("A bridge hangs from two big towers and thick steel cables that carry every single car.".split())]
    monkeypatch.setattr(writers, "ask", lambda *a, **k: {"title": "Suspension bridge", "script": "A bridge hangs from two big towers and thick steel cables that carry every single car."})
    monkeypatch.setattr(author, "ask_text", lambda s, who, system, prompt, *a, **k: "```js\n" + re.sub(r'\["blueprint"\]', '["' + re.search(r'EXACTLY this key: .*?\["([^"]+)"\]', prompt).group(1) + '"]', ref) + "\n```")
    _fake_voice(monkeypatch, words, 4.0)
    monkeypatch.setattr(KS, "FRAME_LIMIT", 3)
    pid, p = _run("kit-style3d-blueprint", "how a suspension bridge holds up")
    assert p["status"] == "done", p.get("error")
    d = store.pdir(pid)
    assert (d / "final.mp4").stat().st_size > 3000 and len(p["stills"]) == 3 and p["styleName"].startswith("run-")


@needs_browser
def test_an_animation_style_end_to_end_with_a_faked_writer(monkeypatch):
    tpl = (paths.ASSETS / "anim" / "references" / "player-template.html").read_text()
    words = [{"text": w, "start": i * 0.4, "end": i * 0.4 + 0.35} for i, w in enumerate("Hello there little stick friend, today we learn how a very small idea can grow.".split())]
    monkeypatch.setattr(writers, "ask", lambda *a, **k: {"title": "Stick friend", "script": "Hello there little stick friend, today we learn how a very small idea can grow."})
    monkeypatch.setattr(author, "ask_text", lambda *a, **k: tpl)
    _fake_voice(monkeypatch, words, 3.0)
    monkeypatch.setattr(KS, "FRAME_LIMIT", 4)
    pid, p = _run("kit-anim-stickman", "a stick friend", aspect="16:9")
    assert p["status"] == "done", p.get("error")
    assert (store.pdir(pid) / "final.mp4").stat().st_size > 1500


def test_the_library_labels_kit_runs_with_their_style_and_a_ready_message():
    from studio import activity
    pid = store.new_id()
    store.save({"id": pid, "skill": "kit-style3d-toon-ink", "subject": "x", "title": "Moon landing", "status": "done", "stage": "video", "video": "final.mp4",
                "thumb": "preview2.jpg", "steps": {}, "log": [], "updatedAt": store.now()})
    d = activity.everything(500)
    item = next(x for x in d["items"] if x["id"] == pid)
    assert item["style"] == "Toon Ink" and item["stage"] == "Your video is ready" and item["thumb"].endswith("preview2.jpg")
    assert {"name": "Toon Ink", "count": 1} in d["by_style"]
