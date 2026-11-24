"""One Skill Lab module for all 29 kit skills (4 story engines, 10 animation styles, 15 3D styles).

Stages (the same for every kit):
  script   the narration (your own script is kept word for word)
  voice    edge-tts narration with exact word timings
  build    the writer crew writes the file the engine plays; it is loaded in a real browser, drawn at three moments, and sent back
           for repair if the page throws (3 rounds). A preview still of each is kept.
  video    every frame is drawn and joined with the sound mix into an MP4 (software WebGL: minutes, not seconds)
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from ..series import writers
from ..skilllab import base, store
from . import author, catalog as C, engine, paths, render, voice as V

STAGES = ("script", "voice", "build", "video")
LABELS = {"script": "The script", "voice": "The voice", "build": "The animation", "video": "The video"}
LENGTHS = [15, 30, 45, 60]
DEFAULT_SECONDS = 30
FRAME_LIMIT: int | None = None          # tests only: stop after this many frames
KIND_OF: dict[str, tuple[str, str]] = {}      # skill id -> (kind, key)  kind: story | anim | style3d


# ---------- sizes ----------
def _hd() -> bool:
    return os.environ.get("KITS_QUALITY", "").lower() == "hd"


def story_size() -> tuple[int, int, int]:
    return (1080, 1920, 30) if _hd() else (540, 960, 24)


def anim_size(aspect: str) -> tuple[int, int, int]:
    k = {"9:16": (1080, 1920), "16:9": (1920, 1080), "1:1": (1080, 1080)}.get(aspect, (1080, 1920))
    return (k[0], k[1], 30) if _hd() else (k[0] // 2, k[1] // 2, 24)


def fmt3d(aspect: str) -> str:
    a = aspect if aspect in ("9:16", "16:9", "1:1") else "9:16"
    return a if _hd() else a + "d"


# ---------- plumbing ----------
def _spec(p: dict) -> tuple[str, str]:
    return KIND_OF[p["skill"]]


def _log(pid: str):
    return base.logger(pid)


def _ensure(pid: str) -> None:
    engine.ensure(lambda m: store.say(pid, m))


def _wd(pid: str) -> Path:
    d = store.pdir(pid) / "work"
    d.mkdir(exist_ok=True)
    return d


def _words(pid: str) -> list[dict]:
    return json.loads((store.pdir(pid) / "words.json").read_text("utf-8"))


def _kit_key(p: dict) -> str:
    kind, key = _spec(p)
    return {"story": C.STORY[key]["dir"] if kind == "story" else "", "anim": "anim", "style3d": "styles3d"}[kind]


def last_stage(p: dict) -> str:
    return "script" if p.get("media") == "prompts" else "video"


def outputs_of(p: dict) -> list[dict]:
    """Preview frames (the first carries the script, editable) and the finished video."""
    st = p.get("stills") or []
    if not st:
        out = [{"key": "script", "step": "script", "title": "The script", "kind": "image", "file": None, "prompt": "script"}]
    else:
        out = [{"key": f"still{i + 1}", "step": "build", "title": "Preview frames" if i == 0 else f"Preview {i + 1}", "kind": "image", "file": f,
                "prompt": "script" if i == 0 else None} for i, f in enumerate(st)]
    out.append({"key": "final", "step": "video", "title": "The video", "kind": "video", "file": p.get("video"), "prompt": None})
    return out


def reset(p: dict, step: str, n: int | None = None) -> None:
    order = STAGES[STAGES.index(step):]
    for st in order:
        p.setdefault("steps", {}).pop(st, None)
    if "script" in order:
        p.pop("kitScript", None)
        p.pop("prompts", None)
    if "build" in order:
        p.pop("stills", None)
        p.pop("html", None)
    if "video" in order:
        p.pop("video", None)


# ---------- stages ----------
def do_script(pid: str) -> None:
    p = store.load(pid)
    kind, key = _spec(p)
    s = base.sdict(p)
    base.step(pid, "script", status="working")
    kit_dir = paths.kit_dir(_kit_key(p) or "cartoon")
    if not writers.uses_ai(s) and len(p["subject"].split()) < 45:
        raise RuntimeError("This skill needs an AI writer (the crew writes the script and the animation code). Pick one in Models, "
                           "or paste your own script (45+ words) to use your words.")
    seconds = int(p.get("seconds") or DEFAULT_SECONDS)
    sc = author.write_script(s, kit_dir, p["subject"], seconds, _log(pid))
    base.put(pid, kitScript=sc, title=sc["title"], prompts={"script": sc["script"]})
    base.step(pid, "script", status="done", note="Your own script, kept word for word" if sc.get("own") else f"{len(sc['script'].split())} words written")


def do_voice(pid: str) -> None:
    p = store.load(pid)
    base.step(pid, "voice", status="working")
    base.put(pid, progress={"pct": None, "text": "Recording the narration and timing every word", "t": store.now()})
    _ensure(pid)
    kit_key = _kit_key(p)
    info = V.narrate(p["kitScript"]["script"], p.get("voice") or "male", store.pdir(pid), paths.kit_dir(kit_key) if kit_key and kit_key != "anim" else None)
    base.put(pid, voiceInfo=info)
    base.step(pid, "voice", status="done", model="edge-tts", note=f"{info['seconds']:.0f} s of narration, {info['words']} words timed")


def _blank(png: bytes) -> bool:
    try:
        import io

        from PIL import Image, ImageStat
        im = Image.open(io.BytesIO(png)).convert("L").resize((64, 64))
        return ImageStat.Stat(im).stddev[0] < 3
    except Exception:  # noqa: BLE001 - no PIL: trust the page errors only
        return False


def _check_session(sess: render.Session, kind: str, dur: float) -> str | None:
    """Draw three moments. Returns an error text, or None (and leaves the three stills on the session)."""
    shots = render.stills(sess, [dur * 0.12, dur * 0.5, dur * 0.88], "canvas" if kind == "style3d" else "png")
    sess.shots = shots
    bad = [i for i, b in enumerate(shots) if _blank(b)]
    if len(bad) == len(shots):
        return "every checked frame was blank (a flat single colour): nothing is being drawn"
    return None


def _try_story(kit: Path, w: Path, code: str, voice: Path, words: Path) -> tuple[str | None, render.Session | None]:
    (w / "story.js").write_text(code, "utf-8")
    r = subprocess.run([sys.executable, "-I", str(kit / "scripts" / "pack.py"), str(w / "story.js"), str(voice), "--words", str(words), "--offline", "-o", str(w / "short.html")],
                       capture_output=True, text=True, timeout=120)
    if r.returncode:
        return "pack.py: " + (r.stderr or r.stdout)[-300:], None
    try:
        sess = render.Session(w, "short.html").__enter__()
    except render.RenderError as e:
        return str(e), None
    try:
        err = _check_session(sess, "story", float(sess.cfg["duration"]))
    except render.RenderError as e:
        sess.close()
        return str(e), None
    if err:
        sess.close()
        return err, None
    return None, sess


def do_build(pid: str) -> None:
    p = store.load(pid)
    kind, key = _spec(p)
    s = base.sdict(p)
    log = _log(pid)
    base.step(pid, "build", status="working")
    base.put(pid, progress={"pct": None, "text": "The writer is writing the animation code and the page is being tested (a few minutes)", "t": store.now()})
    _ensure(pid)
    d = store.pdir(pid)
    w = _wd(pid)
    sc = p["kitScript"]
    words = _words(pid)
    voice_mp3 = d / "voice.mp3"
    dur = round(words[-1]["end"] + 0.9, 1)
    timing = author.timing_summary(words)
    aspect = p.get("aspect") or "9:16"
    holder: dict[str, Any] = {}

    def keep(sess: render.Session | None) -> None:
        old = holder.get("sess")
        if old is not None and old is not sess:
            old.close()
        holder["sess"] = sess

    try:
        if kind == "story":
            kit = paths.kit_dir(_kit_key(p))
            W, H, fps = story_size()
            size_js = f"\nwindow.SHORT.width = {W}; window.SHORT.height = {H}; window.SHORT.fps = {fps};\n"
            sysm = author.story_system(kit)

            def finish(code: str) -> str:
                return (author.pin_script(code, sc["script"]) + size_js) if code else ""

            def check(code: str) -> str | None:
                err, sess = _try_story(kit, w, code, voice_mp3, d / "words.json")
                keep(sess)
                return err
            author.build_with_repair(s, "kit-build", sysm, author.story_prompt(sc["title"], sc["script"], timing), finish, check, log)
            shutil.copyfile(w / "short.html", d / "short.html")
            base.put(pid, html="short.html")
        elif kind == "anim":
            kit = paths.kit_dir("anim")
            W, H, fps = anim_size(aspect)
            sysm = author.anim_system(kit, key)
            prompt = (f"Narration:\n{sc['script']}\n\nTiming of the narration: {timing}\nSize {W}x{H} at {fps} fps, total duration {dur} s. "
                      "Use these exact values in CONFIG. Show what is said, beat by beat, in the style's drawing language.")

            def finish(code: str) -> str:
                if not code:
                    return ""
                code = re.sub(r"width:\s*\d+\s*,\s*height:\s*\d+", f"width: {W}, height: {H}", code, count=1)
                code = re.sub(r"(\bfps:\s*)\d+", rf"\g<1>{fps}", code, count=1)
                return re.sub(r"(\bduration:\s*)[\d.]+", rf"\g<1>{dur}", code, count=1)

            def check(code: str) -> str | None:
                (w / "short.html").write_text(code, "utf-8")
                try:
                    sess = render.Session(w, "short.html").__enter__()
                except render.RenderError as e:
                    keep(None)
                    return str(e)
                try:
                    err = _check_session(sess, "anim", float(sess.cfg["duration"]))
                except render.RenderError as e:
                    sess.close()
                    return str(e)
                if err:
                    sess.close()
                    return err
                keep(sess)
                return None
            author.build_with_repair(s, "kit-build", sysm, prompt, finish, check, log)
            shutil.copyfile(w / "short.html", d / "short.html")
            base.put(pid, html="short.html")
        else:  # style3d
            kit = paths.kit_dir("styles3d")
            run_dir = w / "k3d"
            if run_dir.exists():
                shutil.rmtree(run_dir)
            shutil.copytree(kit, run_dir, ignore=shutil.ignore_patterns("three.min.js"))
            name = "run-" + author.slug_of(sc["title"])[:24]
            fmt = fmt3d(aspect)
            sysm = author.style3d_system(kit, key)
            overlay = {"engine/three.min.js": paths.THREE}

            def finish(code: str) -> str:
                return code

            def check(code: str) -> str | None:
                (run_dir / "styles" / f"{name}.js").write_text(code, "utf-8")
                try:
                    sess = render.Session(run_dir, "player.html", f"style={name}&render=1&fmt={fmt}&samples=6&vo=1", overlay).__enter__()
                except render.RenderError as e:
                    keep(None)
                    return str(e)
                try:
                    err = _check_session(sess, "style3d", float(sess.cfg["duration"]))
                except render.RenderError as e:
                    sess.close()
                    return str(e)
                if err:
                    sess.close()
                    return err
                keep(sess)
                return None
            author.build_with_repair(s, "kit-build", sysm, author.style3d_prompt(name, sc["title"], sc["script"], timing, dur), finish, check, log)
            shutil.copytree(run_dir, d / "k3d", dirs_exist_ok=True)
            base.put(pid, styleName=name, html="k3d/player.html")
        sess = holder.get("sess")
        stills = []
        for i, b in enumerate(getattr(sess, "shots", []) if sess else []):
            fn = f"preview{i + 1}.{'jpg' if kind == 'style3d' else 'png'}"
            (d / fn).write_bytes(b)
            stills.append(fn)
        base.put(pid, progress=None, stills=stills, **({"thumb": stills[len(stills) // 2]} if stills else {}))
        base.step(pid, "build", status="done", note=f"The page loaded and drew {len(stills)} test frames")
    finally:
        keep(None)
        old = holder.get("sess")
        if old is not None:
            old.close()


def do_video(pid: str) -> None:
    p = store.load(pid)
    kind, key = _spec(p)
    base.step(pid, "video", status="working")
    _ensure(pid)
    d = store.pdir(pid)
    w = _wd(pid)
    out = d / "final.mp4"
    say = _log(pid)
    state = {"last": -1.0}

    def prog(i: int, n: int, per: float) -> None:
        base.check(pid)
        mins = int((n - i) * per / 60) + 1
        base.put(pid, progress={"pct": round(100.0 * i / n, 1), "text": f"Drawing frame {i} of {n} · about {mins} min left", "t": store.now()})
        if i == n or i - state["last"] >= max(n // 8, 20):
            state["last"] = i
            say({"text": f"Drawing frame {i} of {n} ({per:.1f} s a frame, about {int((n - i) * per / 60) + 1} min left)."})

    if kind == "style3d":
        fmt = fmt3d(p.get("aspect") or "9:16")
        sess = render.Session(d / "k3d", "player.html", f"style={p['styleName']}&render=1&fmt={fmt}&samples=8&vo=1", {"engine/three.min.js": paths.THREE})
    else:
        sess = render.Session(d, "short.html")
    with sess as s0:
        info = render.video(s0, out, w, prog, frame_kind="canvas" if kind == "style3d" else "jpeg",
                            vo=d / "voice.mp3" if kind != "story" else None, cancel=lambda: base.check(pid), limit=FRAME_LIMIT)
    base.put(pid, video="final.mp4", finalSeconds=info["seconds"], progress=None)
    base.step(pid, "video", status="done", note=f"{info['frames']} frames, {info['width']}x{info['height']}")


RUN = {"script": do_script, "voice": do_voice, "build": do_build, "video": do_video}


# ---------- the skills ----------
class KitSkill:
    STAGES, LABELS, RUN = STAGES, LABELS, RUN
    last_stage = staticmethod(last_stage)
    reset = staticmethod(reset)
    outputs_of = staticmethod(outputs_of)

    def __init__(self, kind: str, key: str):
        self.kind, self.key = kind, key
        self.ID = f"{C.PREFIX}{kind}-{key}" if kind != "story" else f"{C.PREFIX}{key}"
        KIND_OF[self.ID] = (kind, key)
        if kind == "story":
            d = C.STORY[key]
            name, group, look, about, ex = d["name"], C.G_STORY, d["about"], d["about"], d["examples"]
            aspects = ["9:16"]
        elif kind == "anim":
            nm, look, uses = C.ANIM[key]
            name, group, about, ex = nm, C.G_ANIM, f"{look}. Good for: {uses}.", [f"{nm}: " + u for u in uses.split(", ")[:3]]
            aspects = ["9:16", "16:9", "1:1"]
        else:
            nm, look, uses = C.STYLES3D[key]
            name, group, about, ex = nm, C.G_3D, f"Real 3D: {look}. Good for: {uses}.", [f"{nm}: " + u for u in uses.split(", ")[:3]]
            aspects = ["9:16", "16:9", "1:1"]
        self.INFO = {
            "id": self.ID, "name": name, "group": group, "kind": "kit",
            "made_for": about.split(". ")[0][:140], "about": about[:420],
            "input": "A topic in one line, or paste your own script (45+ words) and it is used word for word",
            "outputs": ["The script", "Preview frames", "The video"],
            "aspect": "9:16", "aspects": aspects, "seconds": LENGTHS, "default_seconds": DEFAULT_SECONDS, "native_audio": True,
            "examples": ex,
            "make": [["media", "Write and render"], ["prompts", "The script only"]],
            "cta": ["Write the script", "Make the video"],
            "note": "Runs fully inside AVOS: your writer crew writes the script and the animation code, edge-tts speaks it, and a built-in browser draws "
                    "every frame with sound. Needs an AI writer that can write code well (Claude, Gemini, OpenAI or a large Ollama model; free small "
                    "models often can't) and internet for the voice. Frames are drawn in software, so a 30 s video takes roughly 10-40 minutes.",
            "credit": {"story": "Story engine from the Anylancer free shorts kits (free to use; three.js MIT).",
                       "anim": "Style recipe from Anylancer's free Animation Styles kit.",
                       "style3d": "3D style kit from Anylancer's free Claude 3D Styles (three.js MIT)."}[kind],
            "engine": True, "slow_label": "slow · best quality", "slow": "Takes a while (about 10-40 min) but gives the best output: every frame is drawn one by one with its own sound",
        }


def skills() -> dict[str, KitSkill]:
    out: dict[str, KitSkill] = {}
    for k in C.STORY:
        sk = KitSkill("story", k)
        out[sk.ID] = sk
    for k in C.ANIM:
        sk = KitSkill("anim", k)
        out[sk.ID] = sk
    for k in C.STYLES3D:
        sk = KitSkill("style3d", k)
        out[sk.ID] = sk
    return out
