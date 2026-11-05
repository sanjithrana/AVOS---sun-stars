"""Jobs: one folder per video under projects/<id>/, job.json is the state.

A Python port of ReelMimic's app/server/jobs.ts. The server owns the stage
machine; the crew (studio.director) only writes the files in CONTRACT.md, and
a step advances only when its output files were (re)written.

  new → analyzing → styling → planning → plan_review ⇄ replanning
      → [approve: required inputs must be provided or waived]
      → producing:  setup → CAST GATE (cast_qa ⇄ cast_fix) → SHOT LINE (builders in parallel; every
                    shot is reviewed by a fresh shot_qa as soon as it is built ⇄ fix_chunk) → assemble
      → critiquing: final panel (fresh critic: continuity/pacing/seams, verifies earlier fixes) ⇄ revising
      → done   (needs_user items never trigger a revise: they pause the job and ask the user)
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable

from . import config
from .config import CONFIG, PROJECTS, ROUND_KEYS, ROUND_RANGE, SCRIPTS

PRE_PLAN = ["new", "analyzing", "styling", "styled", "planning", "replanning"]
WORKING = ["analyzing", "styling", "planning", "replanning", "producing", "revising", "critiquing"]


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def dir_of(jid: str) -> Path:
    return PROJECTS / jid


def jpath(jid: str) -> Path:
    return dir_of(jid) / "job.json"


def read_json(p: Path) -> Any:
    try:
        return json.loads(Path(p).read_text("utf-8"))
    except Exception:
        return None


def read_text(p: Path) -> str | None:
    try:
        return Path(p).read_text("utf-8")
    except Exception:
        return None


def write_json(p: Path, data: Any) -> None:
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=1, ensure_ascii=False), "utf-8")
    os.replace(tmp, p)


def mtime(p: Path) -> float:
    try:
        return Path(p).stat().st_mtime
    except OSError:
        return 0.0


# ---------- job.json + events ----------
_LOCK = threading.RLock()


class Bus:
    """Fan-out of job/log events to SSE listeners (thread-safe: renders run in worker threads)."""

    def __init__(self) -> None:
        self.listeners: dict[str, list[tuple[asyncio.AbstractEventLoop, asyncio.Queue]]] = {}

    def subscribe(self, jid: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=2000)
        self.listeners.setdefault(jid, []).append((asyncio.get_running_loop(), q))
        return q

    def unsubscribe(self, jid: str, q: asyncio.Queue) -> None:
        self.listeners[jid] = [x for x in self.listeners.get(jid, []) if x[1] is not q]

    def emit(self, jid: str, ev: dict) -> None:
        for loop, q in list(self.listeners.get(jid, [])):
            try:
                loop.call_soon_threadsafe(_put, q, ev)
            except RuntimeError:
                pass


def _put(q: asyncio.Queue, ev: dict) -> None:
    try:
        q.put_nowait(ev)
    except asyncio.QueueFull:
        pass


bus = Bus()


def load(jid: str) -> dict:
    with _LOCK:
        return json.loads(jpath(jid).read_text("utf-8"))


def save(job: dict) -> dict:
    with _LOCK:
        job["updatedAt"] = now()
        write_json(jpath(job["id"]), job)
    bus.emit(job["id"], {"type": "job", "stage": job["stage"]})
    return job


def update(jid: str, fn: Callable[[dict], Any]) -> dict:
    with _LOCK:
        j = load(jid)
        fn(j)
        return save(j)


def L(jid: str, zh: str, en: str) -> str:
    """System messages in the project's language (Simplified Chinese is converted by the UI)."""
    try:
        return en if load(jid).get("lang") == "en" else zh
    except Exception:
        return en


def log(jid: str, ev: dict) -> None:
    e = {"ts": now(), **ev}
    bus.emit(jid, {"type": "log", "ev": e})
    try:
        def add(j: dict) -> None:
            j["log"] = (j.get("log") or [])[-600:] + [e]
        with _LOCK:
            j = load(jid)
            add(j)
            j["updatedAt"] = now()
            write_json(jpath(jid), j)
    except Exception:
        pass
    try:
        (dir_of(jid) / "logs").mkdir(parents=True, exist_ok=True)
        with open(dir_of(jid) / "logs" / "events.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
    except Exception:
        pass


def chat(jid: str, role: str, text: str, **extra: Any) -> None:
    update(jid, lambda j: j["chat"].append({"role": role, "text": text, "ts": now(), **extra}))


def set_stage(jid: str, stage: str, **extra: Any) -> dict:
    def fn(j: dict) -> None:
        j["stage"] = stage
        j.update(extra)
    return update(jid, fn)


def pipe(jid: str, fn: Callable[[dict], Any]) -> dict:
    def g(j: dict) -> None:
        j["pipeline"] = j.get("pipeline") or {}
        fn(j["pipeline"])
    return update(jid, g)


def recover_orphans() -> None:
    """On startup nothing is running, so a job still marked as working was cut off by a restart."""
    if not PROJECTS.exists():
        return
    for d in PROJECTS.iterdir():
        if not (d / "job.json").exists():
            continue
        j = load(d.name)
        if j.get("stage") not in WORKING:
            continue
        jid = d.name

        def fn(x: dict) -> None:
            x["failed"] = x["stage"]
            x["stage"] = "error"
            x["error"] = L(jid, "伺服器重新啟動，這一輪被中斷了（它可能已經改了部分檔案）。按「重試這一步」從目前的檔案繼續。",
                           "The server restarted and this turn was cut off (it may have changed some files). Click “Retry this step” to continue from the current files.")
            x["chat"].append({"role": "system", "text": L(jid, "這一輪因為伺服器重新啟動而中斷。", "This turn was cut off by a server restart."), "ts": now()})
        update(jid, fn)


# ---------- round limits ----------
def rounds(jid: str) -> dict:
    s = load(jid).get("settings") or {}
    return {k: s.get(k, CONFIG[k]) if s.get(k) is not None else CONFIG[k] for k in ROUND_KEYS}


def clean_rounds(inp: dict) -> dict:
    out: dict[str, int | None] = {}
    for k in ROUND_KEYS:
        if k not in inp:
            continue
        raw = inp[k]
        if raw in ("", None):
            out[k] = None
            continue
        try:
            v = float(raw)
        except (TypeError, ValueError):
            v = -1.0
        if not v.is_integer() or v < ROUND_RANGE["min"] or v > ROUND_RANGE["max"]:
            raise ValueError(f"{k} must be a whole number from {ROUND_RANGE['min']} to {ROUND_RANGE['max']}")
        out[k] = int(v)
    return out


def set_rounds(jid: str, inp: dict) -> dict:
    clean = clean_rounds(inp)

    def fn(x: dict) -> None:
        s = dict(x.get("settings") or {})
        for k, v in clean.items():
            if v is None:
                s.pop(k, None)
            else:
                s[k] = v
        x["settings"] = s
    update(jid, fn)
    return snapshot(jid)


# ---------- global agent slots (all projects share them) ----------
URGENT = {"cast_qa", "cast_fix", "shot_qa", "fix_chunk", "assemble", "critique", "revise", "replan", "plan", "style"}


class Slots:
    """Reviews and fixes jump the queue; new builds take whatever slots are left."""

    def __init__(self) -> None:
        self.active = 0
        self.waiters: list[tuple[asyncio.Future, bool]] = []

    async def acquire(self, phase: str) -> None:
        if self.active < CONFIG["maxAgentsGlobal"]:
            self.active += 1
            return
        fut = asyncio.get_running_loop().create_future()
        hi = phase in URGENT
        if hi:
            i = next((n for n, w in enumerate(self.waiters) if not w[1]), len(self.waiters))
            self.waiters.insert(i, (fut, hi))
        else:
            self.waiters.append((fut, hi))
        await fut
        self.active += 1

    def release(self) -> None:
        self.active -= 1
        while self.waiters:
            fut, _ = self.waiters.pop(0)
            if not fut.done():
                fut.set_result(None)
                break


slots = Slots()


class Abort:
    def __init__(self) -> None:
        self.aborted = False
        self.procs: list[subprocess.Popen] = []

    def abort(self) -> None:
        self.aborted = True
        for p in self.procs:
            try:
                p.kill()
            except Exception:
                pass


running: dict[str, set[Abort]] = {}


def stop_all() -> None:
    for s in running.values():
        for a in s:
            a.abort()


# ---------- listing / snapshot ----------
def _thumb(d: Path) -> str | None:
    if (d / "out" / "check" / "style_1.jpg").exists():
        return "out/check/style_1.jpg"
    if (d / "analysis" / "sheet_1fps.jpg").exists():
        return "analysis/sheet_1fps.jpg"
    return None


def list_jobs() -> list[dict]:
    if not PROJECTS.exists():
        return []
    out = []
    for d in PROJECTS.iterdir():
        if not (d / "job.json").exists():
            continue
        try:
            j = load(d.name)
        except Exception:
            continue
        plan = read_json(d / "plan.json") or {}
        out.append({"id": j["id"], "title": plan.get("title") or j["title"], "stage": j["stage"], "agent": j["agent"],
                    "updatedAt": j.get("updatedAt"), "needs": len(j.get("needs") or []), "thumb": _thumb(d)})
    return sorted(out, key=lambda x: x.get("updatedAt") or "", reverse=True)


def _list(d: Path, sub: str, pat: str) -> list[str]:
    p = d / sub
    if not p.is_dir():
        return []
    rx = re.compile(pat, re.I)
    items = [(f"{sub}/{f.name}", f.stat().st_mtime) for f in p.iterdir() if f.is_file() and rx.search(f.name)]
    return [x[0] for x in sorted(items, key=lambda x: -x[1])]


def snapshot(jid: str) -> dict:
    from .render.engines import engine_label
    d, job = dir_of(jid), load(jid)
    plan = read_json(d / "plan.json")
    route = read_json(d / "analysis" / "route.json")
    eng = (plan or {}).get("engine") or (route or {}).get("engine")
    return {
        "job": job, "brief": read_text(d / "brief.md"),
        "report": read_json(d / "analysis" / "report.json"), "styleMd": read_text(d / "analysis" / "STYLE.md"),
        "route": route, "plan": plan, "storyboard": read_text(d / "STORYBOARD.md"),
        "assetsMd": read_text(d / "assets" / "ASSETS.md"),
        "checks": _list(d, "out/check", r"\.(jpg|png)$")[:24],
        "video": "out/video.mp4" if (d / "out" / "video.mp4").exists() else None,
        "critique": read_json(d / "out" / "check" / "critique.json"),
        "cast": {"sheets": _list(d, "out/check/cast", r"sheet[^/]*\.(jpg|png)$")[:8],
                 "review": read_json(d / "out" / "check" / "cast" / "review.json")},
        "shots": _list(d, "out/check/shots", r"_sheet\.(jpg|png)$")[:60],
        "production": read_json(d / "build" / "production.json"),
        "lyrics": read_json(d / "analysis" / "lyrics" / "subs.json"),
        "requiredInputs": required_inputs(jid, plan, job),
        "rounds": {"values": rounds(jid), "defaults": {k: CONFIG[k] for k in ROUND_KEYS}, **ROUND_RANGE},
        "inputs": _list(d, "inputs", r"."),
        "engine": {"id": eng, "label": engine_label(eng)} if eng else None,
        "finish": _finish_status(d),
    }


def _finish_status(d: Path) -> dict | None:
    from . import finish
    st = finish.read_status(d)
    if st and st.get("state") == "running" and d.name not in finish.RUNNING:
        st = {**st, "state": "error", "error": "Interrupted (the service restarted). Start it again."}
    return st


def create_job(jid: str, title: str, agent: str, brief: str, reference: dict, lang: str = "en", settings: dict | None = None) -> dict:
    d = dir_of(jid)
    (d / "inputs").mkdir(parents=True, exist_ok=True)
    (d / "analysis").mkdir(parents=True, exist_ok=True)
    (d / "brief.md").write_text(brief or "", "utf-8")
    job = {"id": jid, "title": title, "agent": agent, "lang": lang, "reference": reference, "settings": settings or {},
           "stage": "new", "sessionId": None, "sessions": {}, "createdAt": now(), "chat": [], "log": [], "needs": [],
           "waived": [], "pipeline": {}}
    return save(job)


# ---------- required inputs ----------
def required_inputs(jid: str, plan: dict | None, job: dict) -> list[dict]:
    d = dir_of(jid)
    files = [f.name for f in (d / "inputs").iterdir()] if (d / "inputs").is_dir() else []
    out = []
    for r in (plan or {}).get("required_inputs") or []:
        if not isinstance(r, dict) or not r.get("id"):
            continue
        status = "missing"
        given = [f for f in ((job.get("provided") or {}).get(r["id"]) or []) if (d / f).exists()]
        if r["id"] in (job.get("waived") or []):
            status = "waived"
        elif given:
            status = "provided"
        elif r.get("kind") == "lyrics" and ((d / "inputs" / "lyrics.txt").exists() or (d / "analysis" / "lyrics" / "subs.lrc").exists()
                                            or any(f.lower().endswith(".lrc") for f in files)):
            status = "provided"
        elif r.get("file") and (d / r["file"]).exists():
            status = "provided"
        elif r.get("kind") != "lyrics" and any((r.get("match") or r["id"]).lower() in f.lower() for f in files):
            status = "provided"
        out.append({**r, "status": status, "files": given})
    return out


def open_inputs(jid: str) -> list[dict]:
    return [r for r in snapshot(jid)["requiredInputs"] if r["status"] == "missing"]


def waive(jid: str, input_id: str) -> None:
    def fn(j: dict) -> None:
        j["waived"] = sorted(set((j.get("waived") or []) + [input_id]))
        j["needs"] = [n for n in (j.get("needs") or []) if n.get("input") != input_id]
    update(jid, fn)


def unwaive(jid: str, input_id: str) -> None:
    update(jid, lambda j: j.__setitem__("waived", [x for x in (j.get("waived") or []) if x != input_id]))


def touch(jid: str) -> None:
    update(jid, lambda j: None)


AUD = re.compile(r"\.(mp3|m4a|wav|aac|flac|ogg|opus|mp4|mov|webm)$", re.I)


def music_file(jid: str) -> str | None:
    d, plan, job = dir_of(jid), read_json(dir_of(jid) / "plan.json") or {}, load(jid)
    m = plan.get("music") or {}
    if m.get("file") and (d / m["file"]).exists():
        return m["file"]
    audio_ids = [r["id"] for r in plan.get("required_inputs") or [] if isinstance(r, dict) and r.get("kind") == "audio"]
    for k in audio_ids:
        for f in (job.get("provided") or {}).get(k) or []:
            if AUD.search(f) and (d / f).exists():
                return f
    if (d / "inputs").is_dir():
        for f in sorted((d / "inputs").iterdir()):
            if f.is_file() and AUD.search(f.name) and not re.match(r"^reference\.", f.name, re.I):
                return f"inputs/{f.name}"
    return None


def provide_input(jid: str, input_id: str, saved: list[str]) -> bool:
    d = dir_of(jid)
    r = next((x for x in (read_json(d / "plan.json") or {}).get("required_inputs") or [] if isinstance(x, dict) and x.get("id") == input_id), None)
    if not r or not saved:
        return False

    def fn(j: dict) -> None:
        j["provided"] = {**(j.get("provided") or {}), input_id: saved}
        j["waived"] = [x for x in (j.get("waived") or []) if x != input_id]
    update(jid, fn)
    txt = next((f for f in saved if f.lower().endswith(".txt")), None) if r.get("kind") == "lyrics" else None
    text = read_text(d / txt) if txt and not re.search(r"(^|/)lyrics\.txt$", txt, re.I) else None
    spawn(save_lyrics(jid, text) if text and text.strip() else align_if_ready(jid))
    return True


async def align_if_ready(jid: str) -> dict | None:
    d = dir_of(jid)
    if not (d / "inputs" / "lyrics.txt").exists() or (d / "analysis" / "lyrics" / "subs.lrc").exists() or not music_file(jid):
        return None
    return await save_lyrics(jid, read_text(d / "inputs" / "lyrics.txt") or "")


async def save_lyrics(jid: str, text: str) -> dict:
    """The user pastes lyrics → inputs/lyrics.txt → timed against the music → analysis/lyrics/subs.lrc|json."""
    d = dir_of(jid)
    (d / "inputs").mkdir(exist_ok=True)
    (d / "inputs" / "lyrics.txt").write_text(text.strip() + "\n", "utf-8")
    plan = read_json(d / "plan.json") or {}
    m = plan.get("music") or {}
    song = music_file(jid)
    out = d / "analysis" / "lyrics"
    out.mkdir(parents=True, exist_ok=True)
    if not song:
        log(jid, {"type": "text", "text": L(jid, "歌詞已存，收到配樂後會自動對時", "Lyrics saved; they will be timed as soon as the music arrives")})
        return {"ok": True, "aligned": False}
    from .lyrics import align
    log(jid, {"type": "tool", "name": "align_lyrics.py", "detail": f"對時：{song}"})
    sec = m.get("section") or {}
    start = sec.get("start_s") if sec.get("start_s") is not None and "clip" not in song.lower() else None
    end = sec.get("end_s") if start is not None else None
    ok, report = await asyncio.to_thread(align, d / song, d / "inputs" / "lyrics.txt", out / "subs.lrc", start, end)
    log(jid, {"type": "text" if ok else "error",
              "text": (L(jid, "歌詞對時完成：", "Lyrics timed: ") + report) if ok else (L(jid, "歌詞對時失敗：", "Lyrics timing failed: ") + report)})
    if ok:
        update(jid, lambda j: j.__setitem__("needs", [n for n in (j.get("needs") or []) if n.get("kind") != "lyrics"]))
    return {"ok": ok, "aligned": ok, "report": report}


# ---------- analysis ----------
async def analyze(jid: str) -> bool:
    j, d = load(jid), dir_of(jid)
    src = j["reference"]["src"] if j["reference"]["type"] == "url" else str(d / j["reference"]["src"])
    set_stage(jid, "analyzing")
    log(jid, {"type": "tool", "name": "analyze.py", "detail": j["reference"]["src"]})
    ab = Abort()
    running.setdefault(jid, set()).add(ab)
    try:
        code, err = await run_script(jid, [config.PY, str(SCRIPTS / "analyze.py"), src, "--out", str(d / "analysis")], ab)
    finally:
        running[jid].discard(ab)
    ok = code == 0 and (d / "analysis" / "report.json").exists()
    if not ok:
        set_stage(jid, "error", failed="analyzing",
                  error=L(jid, "已取消", "Cancelled") if ab.aborted else (err or "analyze.py failed"))
    return ok


async def run_script(jid: str, cmd: list[str], ab: Abort, quiet: bool = False) -> tuple[int, str]:
    """Run a helper script, streaming stdout lines into the project log."""
    def go() -> tuple[int, str]:
        try:
            p = subprocess.Popen(cmd, cwd=str(config.WORK_DIR), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                 encoding="utf-8", errors="replace", env={**os.environ, "PYTHONIOENCODING": "utf-8"})
        except OSError as e:
            return 127, f"{cmd[0]} could not be started ({e}). Install Python 3.10+, or set PYTHON=/path/to/python"
        ab.procs.append(p)
        errs: list[str] = []

        def pump_err() -> None:
            for line in p.stderr:  # type: ignore[union-attr]
                if line.strip() and not re.search(r"Warning|warn\(", line, re.I):
                    errs.append(line.rstrip())
        t = threading.Thread(target=pump_err, daemon=True)
        t.start()
        for line in p.stdout:  # type: ignore[union-attr]
            if line.strip() and not quiet:
                log(jid, {"type": "text", "text": line.rstrip()[:400]})
        p.wait()
        t.join(timeout=2)
        if p.returncode and errs:
            log(jid, {"type": "error", "text": "\n".join(errs[-6:])[:600]})
        return p.returncode, "\n".join(errs[-6:])[-600:]
    return await asyncio.to_thread(go)


# ---------- one crew turn ----------
@dataclass
class TurnResult:
    ok: bool
    text: str | None = None
    missing: list[str] = field(default_factory=list)
    stderr: str | None = None
    last_error: str | None = None
    aborted: bool = False


async def turn(jid: str, phase: str, vars: dict, must: list[str], session: str = "director", who: str | None = None) -> TurnResult:
    from .director import run_phase
    j, d = load(jid), dir_of(jid)
    ab = Abort()
    running.setdefault(jid, set()).add(ab)
    before = [mtime(d / f) for f in must]
    label = who or ("reviewer" if session == "fresh" else session)
    await slots.acquire(phase)
    log(jid, {"type": "turn", "state": "start", "phase": phase, "who": label})
    t0 = time.time()
    try:
        r = await run_phase(phase=phase, jid=jid, vars=vars, session=session, who=label, abort=ab)
    except Exception as e:  # a crash in a step is a failed turn, never a dead server
        import traceback
        traceback.print_exc()
        r = {"ok": False, "text": None, "stderr": f"{type(e).__name__}: {e}", "lastError": str(e)}
        log(jid, {"type": "error", "text": f"{type(e).__name__}: {e}", "who": label})
    finally:
        slots.release()
        running.get(jid, set()).discard(ab)
    ok = bool(r.get("ok")) and not ab.aborted
    log(jid, {"type": "turn", "state": "end", "phase": phase, "who": label, "ok": ok})
    if ab.aborted:
        return TurnResult(ok=False, aborted=True)
    missing = [f for i, f in enumerate(must) if not mtime(d / f) > before[i]]
    if missing and r.get("ok") and load(jid).get("retryPending"):
        missing = [f for f in missing if not (d / f).exists()]
    if load(jid).get("retryPending"):
        update(jid, lambda x: x.pop("retryPending", None))
    if r.get("text"):
        role = "critic" if session == "fresh" else "agent" if session == "director" else "builder"
        chat(jid, role, r["text"], phase=phase, who=label)
    return TurnResult(ok=bool(r.get("ok")) and not missing, text=r.get("text"), missing=missing,
                      stderr=r.get("stderr"), last_error=r.get("lastError"))


LIMIT_RX = re.compile(r"usage limit|rate limit|hit your limit|limit reached|quota|credit balance|429", re.I)


def fail(jid: str, stage_name: str, res: TurnResult) -> bool:
    limit = next((t for t in (res.last_error, res.text, res.stderr) if t and LIMIT_RX.search(t)), None)
    if limit and not res.aborted:
        set_stage(jid, "error", failed=stage_name, error=L(jid, f"AI 帳號的用量到上限了，等額度恢復或換另一個 AI 導演再按「重試這一步」。原始訊息：{limit[-300:]}",
                                                            f"Your AI account hit its usage limit. Wait until it resets (or switch to another AI crew), then click “Retry this step”. Message: {limit[-300:]}"))
        return False
    if res.aborted:
        err = L(jid, "已取消", "Cancelled")
    elif res.last_error:   # the crew said what went wrong (Ollama not running, no key, model missing…): that's the cause
        err = L(jid, f"agent 回合失敗：{res.last_error[-400:]}", f"The agent turn failed: {res.last_error[-400:]}")
    elif not res.missing:
        err = L(jid, f"agent 回合失敗{'：' + res.stderr[-300:] if res.stderr else ''}", f"The agent turn failed{': ' + res.stderr[-300:] if res.stderr else ''}")
    else:
        err = L(jid, f"缺少輸出：{', '.join(res.missing)}", f"Missing output: {', '.join(res.missing)}")
    set_stage(jid, "error", failed=stage_name, error=err)
    return False


async def step(jid: str, stage_name: str, phase: str, vars: dict, must: list[str], next_stage: str | None = None,
               session: str = "director", who: str | None = None) -> bool:
    set_stage(jid, stage_name, error=None, failed=None)
    r = await turn(jid, phase, vars, must, session=session, who=who)
    if not r.ok:
        return fail(jid, stage_name, r)
    if next_stage:
        set_stage(jid, next_stage)
    return True


def collect_needs(jid: str, items: list | None, frm: str) -> int:
    add = [{**n, "from": frm, "at": now()} for n in (items or []) if isinstance(n, dict) and n.get("issue")]
    if not add:
        return 0

    def fn(j: dict) -> None:
        j["needs"] = [x for x in (j.get("needs") or []) if x.get("from") != frm and not any(a["issue"] == x.get("issue") for a in add)] + add
    update(jid, fn)
    chat(jid, "system", L(jid, "需要你提供：" + "；".join(n["issue"] for n in add), "Needs your input: " + "; ".join(n["issue"] for n in add)))
    return len(add)


def _passed(rv: dict) -> bool:
    issues = rv.get("issues") or []
    if issues and all(isinstance(x, dict) and x.get("severity") for x in issues):
        return not any(x.get("severity") != "polish" for x in issues)
    return bool(rv.get("pass"))


def _shot_passed(s: dict) -> bool:
    return _passed(s)


# ---------- background tasks ----------
_tasks: set[asyncio.Task] = set()


def spawn(coro: Awaitable) -> asyncio.Task:
    t = asyncio.ensure_future(coro)
    _tasks.add(t)

    def done(x: asyncio.Task) -> None:
        _tasks.discard(x)
        if not x.cancelled() and x.exception():
            import traceback
            traceback.print_exception(x.exception())
    t.add_done_callback(done)
    return t


# ---------- pre-production ----------
async def start(jid: str) -> None:
    if not await analyze(jid):
        return
    if not await step(jid, "styling", "style", {}, ["analysis/STYLE.md", "analysis/route.json"], "styled"):
        return
    await pre_production(jid)


async def pre_production(jid: str) -> bool:
    """The director writes the plan core, then every character (one agent each) and the assets are made at the same
    time, then the director merges them and paints the style frames with the real cast."""
    d = dir_of(jid)
    if not await step(jid, "planning", "plan", {}, ["plan.json", "STORYBOARD.md"]):
        return False
    plan = read_json(d / "plan.json") or {}
    chars = [c for c in plan.get("characters") or [] if isinstance(c, dict) and c.get("id") and str(c.get("file", "")).startswith("build/")]
    need_assets = any(isinstance(a, dict) and a.get("status") == "to_fetch" for a in plan.get("assets") or [])

    async def cast_one(c: dict) -> dict:
        r = await turn(jid, "pre_cast", {"character": c}, [c["file"]], session=f"cast-{c['id']}", who=f"cast-{c['id']}")
        return {"what": f"角色 {c.get('name') or c['id']}", "ok": r.ok}

    async def assets() -> dict:
        r = await turn(jid, "pre_assets", {}, ["assets/fetched.json"], session="fresh", who="assets")
        return {"what": "素材", "ok": r.ok}
    work = [cast_one(c) for c in chars] + ([assets()] if need_assets else [])
    if work:
        n = len(chars)
        chat(jid, "system", L(jid, f"企劃核心完成，{f'{n} 個角色' if n else ''}{'和' if n and need_assets else ''}{'素材' if need_assets else ''}同時製作中",
                              "Plan core done. Now drafting " + " and ".join(x for x in [f"{n} character{'s' if n > 1 else ''}" if n else "", "the assets" if need_assets else ""] if x) + " in parallel"))
    results = list(await asyncio.gather(*work)) if work else []
    if not await step(jid, "planning", "plan_frames", {"results": results}, ["plan.json"], "plan_review"):
        return False
    return await flush_notes(jid)


async def flush_notes(jid: str) -> bool:
    notes = load(jid).get("pendingNotes") or []
    if not notes:
        return True
    update(jid, lambda x: x.__setitem__("pendingNotes", []))
    chat(jid, "system", L(jid, "把企劃寫作期間你補充的意見修進企劃", "Adding the notes you sent while the plan was being written"))
    if not await step(jid, "replanning", "replan", {"message": "\n\n".join(notes)}, ["plan.json"], "plan_review"):
        return False
    return await flush_notes(jid)


def busy(jid: str) -> bool:
    return bool(running.get(jid)) or load(jid).get("stage") in WORKING


def _one_of(v: str | None, *opts: str) -> bool:
    return bool(v) and v in opts


async def message(jid: str, text: str, meta: dict | None = None) -> Any:
    meta = meta or {}
    j = load(jid)
    if meta.get("shot"):
        tagged = f"［鏡頭 {meta['shot']}］{text}"
    elif meta.get("time") is not None:
        tagged = f"［{float(meta['time']):.1f} 秒］{text}"
    else:
        tagged = text
    extra = {k: meta[k] for k in ("shot", "time", "attachments", "notes") if meta.get(k) is not None}
    chat(jid, "user", tagged, **extra)
    att = [p for p in meta.get("attachments") or [] if re.match(r"^inputs/attachments/[^/\\]+$", str(p))]
    if att:
        tagged += "\n\n使用者附上的檔案（圖片請打開來看，當成這則訊息的一部分）：\n" + "\n".join(f"- {p}" for p in att)
    if j["stage"] in PRE_PLAN:
        with open(dir_of(jid) / "brief.md", "a", encoding="utf-8") as f:
            f.write(f"\n\n補充（使用者在企劃完成前加的）：{tagged}\n")
        if j["stage"] in ("planning", "replanning"):
            update(jid, lambda x: x.__setitem__("pendingNotes", (x.get("pendingNotes") or []) + [tagged]))
        return None
    if j["stage"] == "plan_review" or (j["stage"] == "error" and _one_of(j.get("failed"), "planning", "replanning", "styling")):
        if not await step(jid, "replanning", "replan", {"message": tagged, "attachments": att}, ["plan.json"], "plan_review"):
            return False
        return await flush_notes(jid)
    pre_phase = _one_of((j.get("pipeline") or {}).get("phase"), "setup", "cast", "shots", "assemble")
    if pre_phase and (j["stage"] == "needs_input" or (j["stage"] == "error" and _one_of(j.get("failed"), "producing", "revising"))):
        return await production_note(jid, tagged)
    if j["stage"] in ("done", "needs_input") or (j["stage"] == "error" and _one_of(j.get("failed"), "producing", "revising", "critiquing")):
        if await step(jid, "revising", "revise", {"message": tagged, "round": "user", "notes": meta.get("notes") or [], "attachments": att},
                      ["out/video.mp4", "out/check/fixes.json"]):
            await final_panel(jid)
    return None


async def production_note(jid: str, msg: str) -> None:
    j, d = load(jid), dir_of(jid)
    ph = (j.get("pipeline") or {}).get("phase")

    def clear(x: dict) -> None:
        x["needs"] = []
        x["error"] = None
        x["failed"] = None
    update(jid, clear)
    cast = (j.get("pipeline") or {}).get("cast")
    if ph == "cast" or (cast and not cast.get("pass")):
        rv = read_json(d / "out" / "check" / "cast" / "review.json") or {}
        pipe(jid, lambda p: p.__setitem__("cast", {"round": 0, "pass": False, **(p.get("cast") or {}), "state": "fixing"}))
        if not await step(jid, "producing", "cast_fix", {"issues": rv.get("issues") or [], "round": "user", "message": msg},
                          ["out/check/cast/sheet.jpg", "out/check/cast/fixes.json"]):
            return
        pipe(jid, lambda p: p.__setitem__("cast", {"round": 0, "pass": False}))
    elif ph == "shots":
        def fn(x: dict) -> None:
            x["userNote"] = msg
            for c in (x["pipeline"].get("chunks") or {}).values():
                if c.get("state") != "passed":
                    c.update({"state": "queued", "round": 0, "fixFirst": True})
        update(jid, fn)
    if await production(jid):
        await final_panel(jid)


def snapshot_engine(jid: str) -> dict | None:
    """Freeze the engine settings at approval so a later change never alters a job mid-flight."""
    from .render.engines import engine_snapshot
    route = read_json(dir_of(jid) / "analysis" / "route.json") or {}
    plan = read_json(dir_of(jid) / "plan.json") or {}
    eng = plan.get("engine") or route.get("engine")
    if not eng:
        return None
    dst = dir_of(jid) / "build" / "engine" / eng
    dst.mkdir(parents=True, exist_ok=True)
    src = config.SKILLS / eng
    if src.is_dir() and (src / "SKILL.md").exists():
        shutil.copyfile(src / "SKILL.md", dst / "SKILL.md")
    info = {"engine": eng, "frozenAt": now(), "path": f"build/engine/{eng}", "settings": engine_snapshot(eng)}
    write_json(dst / "SNAPSHOT.json", info)
    return {k: info[k] for k in ("engine", "frozenAt", "path")}


class ApproveBlocked(Exception):
    pass


async def approve(jid: str) -> None:
    open_ = open_inputs(jid)
    if open_:
        raise ApproveBlocked("還有需要你提供或略過的素材：" + "、".join(r.get("label") or r["id"] for r in open_))
    try:
        await align_if_ready(jid)
    except Exception:
        pass

    def fn(j: dict) -> None:
        j["approvedAt"] = now()
        j["approvedPlanVersion"] = (read_json(dir_of(jid) / "plan.json") or {}).get("version")
        j["engineSnapshot"] = snapshot_engine(jid)
        j["pipeline"] = {}
        j["sessions"] = {} if j.get("approvedAtPrev") else {k: v for k, v in (j.get("sessions") or {}).items() if k.startswith("cast-")}
        j["approvedAtPrev"] = True
        j["needs"] = []
        j["userNote"] = None
    update(jid, fn)
    chat(jid, "system", L(jid, "企劃已核准，開始生產：角色關 → 分段製作（每段做完立刻審）→ 組裝 → 最後評審",
                          "Plan approved. Production: characters → parts built and reviewed as they finish → assembly → final review"))
    if await production(jid, fresh=True):
        await final_panel(jid)


# ---------- production ----------
_shared_locks: dict[str, asyncio.Lock] = {}


async def production(jid: str, fresh: bool = False) -> bool:
    d = dir_of(jid)
    prev = {} if fresh else (load(jid).get("pipeline") or {})
    has_setup = not fresh and (d / "build" / "production.json").exists() and (d / "out" / "check" / "cast" / "sheet.jpg").exists()
    if not has_setup:
        pipe(jid, lambda p: p.__setitem__("phase", "setup"))
        if not await step(jid, "producing", "setup", {}, ["build/production.json", "out/check/cast/sheet.jpg"]):
            return False
    else:
        set_stage(jid, "producing", error=None, failed=None)
    cast_task = asyncio.ensure_future(cast_gate(jid, prev))
    prod = read_json(d / "build" / "production.json") or {}
    chunks = [c for c in prod.get("chunks") or [] if isinstance(c, dict) and c.get("id") and c.get("shots")]
    old = prev.get("chunks") or {}

    def init(p: dict) -> None:
        p["phase"] = "shots"
        p["chunks"] = {c["id"]: (old[c["id"]] if (old.get(c["id"]) or {}).get("state") == "passed" else
                                 {"shots": c["shots"], "state": "queued", "round": 0,
                                  "fixFirst": bool((old.get(c["id"]) or {}).get("fixFirst")) or (old.get(c["id"]) or {}).get("state") == "failed"})
                       for c in chunks}
    pipe(jid, init)
    SH = d / "out" / "check" / "shots"
    SH.mkdir(parents=True, exist_ok=True)

    async def run_chunk(c: dict) -> bool:
        key = f"builder-{c['id']}"

        def setc(**s: Any) -> None:
            pipe(jid, lambda p: p["chunks"][c["id"]].update(s))
        if ((load(jid).get("pipeline") or {}).get("chunks") or {}).get(c["id"], {}).get("state") == "passed":
            return True

        def shot_file(sid: str, kind: str) -> Path:
            return SH / f"{sid}.{kind}.json"
        reviews: dict[str, asyncio.Future] = {}
        results: dict[str, dict] = {}

        async def review_body(sid: str, rnd: int) -> bool:
            if not await cast_task:
                return False
            r = await turn(jid, "shot_qa", {"chunk": c, "shots": [sid], "round": rnd, "out": f"out/check/shots/{sid}.review.json"},
                           [f"out/check/shots/{sid}.review.json"], session="fresh", who=f"shot-qa-{sid}")
            if not r.ok:
                return False
            rv = read_json(shot_file(sid, "review")) or {}
            entry = next((x for x in rv.get("shots") or [] if x.get("id") == sid), None) or {"id": sid, "pass": bool(rv.get("pass")), "issues": rv.get("issues") or []}
            results[sid] = {"entry": entry, "needs": rv.get("needs_user") or [], "verified": rv.get("verified_fixes") or []}
            return True

        def review_shot(sid: str, rnd: int) -> None:
            reviews[sid] = asyncio.ensure_future(review_body(sid, rnd))

        def merge_review() -> None:
            alls = [x for x in c["shots"] if x in results]
            write_json(SH / f"{c['id']}.review.json", {"shots": [results[x]["entry"] for x in alls],
                                                       "verified_fixes": [v for x in alls for v in results[x]["verified"]],
                                                       "needs_user": [n for x in alls for n in results[x]["needs"]]})
        reuse = bool(((load(jid).get("pipeline") or {}).get("chunks") or {}).get(c["id"], {}).get("fixFirst")) and (SH / f"{c['id']}.review.json").exists()
        if reuse:
            setc(fixFirst=False)
        if fresh or not (SH / f"{c['id']}.done.json").exists():
            setc(state="building")
            t0 = time.time()
            seen: set[str] = set()
            stop = asyncio.Event()

            async def watch() -> None:
                while not stop.is_set():
                    for sid in c["shots"]:
                        f = shot_file(sid, "done")
                        if sid not in seen and f.exists() and f.stat().st_mtime > t0:
                            seen.add(sid)
                            review_shot(sid, 1)
                    try:
                        await asyncio.wait_for(stop.wait(), 2.0)
                    except asyncio.TimeoutError:
                        pass
            w = asyncio.ensure_future(watch())
            b = await turn(jid, "build_chunk", {"chunk": c}, [f"out/check/shots/{c['id']}.done.json"], session=key, who=key)
            stop.set()
            await w
            if not b.ok:
                setc(state="error")
                return False
        if not ((load(jid).get("pipeline") or {}).get("cast") or {}).get("pass"):
            setc(state="waiting_cast")
        if not await cast_task:
            setc(state="built")
            return False
        todo = list(c["shots"])
        rnd = 0
        while True:
            rnd += 1
            setc(state="reviewing", round=rnd)
            if reuse:
                rv = read_json(SH / f"{c['id']}.review.json") or {}
                for e in rv.get("shots") or []:
                    results[e["id"]] = {"entry": e, "needs": [], "verified": []}
                reuse = False
            else:
                for sid in todo:
                    if sid not in reviews or rnd > 1:
                        review_shot(sid, rnd)
                oks = await asyncio.gather(*(reviews[sid] for sid in todo))
                if False in oks:
                    setc(state="error")
                    return False
                merge_review()
            needs = [n for x in c["shots"] for n in (results.get(x) or {}).get("needs") or []]
            if collect_needs(jid, needs, f"shot-qa-{c['id']}"):
                setc(state="needs_user")
                return False
            bad = [results[x]["entry"] for x in c["shots"] if x in results and not _shot_passed(results[x]["entry"])]
            if not bad:
                setc(state="passed")
                return True
            if rnd >= rounds(jid)["chunkRounds"]:
                setc(state="failed", open=len(bad))
                return False
            setc(state="fixing")
            f = await turn(jid, "fix_chunk", {"chunk": c, "bad": bad, "round": rnd, "message": load(jid).get("userNote")},
                           [f"out/check/shots/{c['id']}.fixes.json"], session=key, who=key)
            if not f.ok:
                setc(state="error")
                return False
            fx = read_json(SH / f"{c['id']}.fixes.json")
            items = fx if isinstance(fx, list) else (fx or {}).get("fixes") or []
            shared = [x for x in items if isinstance(x, dict) and x.get("status") == "shared"]
            if shared:
                setc(state="shared_fix")
                lock = _shared_locks.setdefault(jid, asyncio.Lock())
                async with lock:
                    r = await turn(jid, "shared_fix", {"chunk": c, "items": shared}, [f"out/check/shots/{c['id']}.shared.json"], who="director")
                    if not r.ok:
                        log(jid, {"type": "error", "text": f"共用檔修正沒有完成（{c['id']}）"})
                if r.ok:
                    setc(state="fixing")
                    g = await turn(jid, "fix_chunk", {"chunk": c, "bad": [{"id": x.get("shot") or "", "issues": [{"issue": x.get("issue"), "fix": "導演已改好共用檔，照 shared.json 套用"}]} for x in shared],
                                                      "round": rnd, "message": load(jid).get("userNote")},
                                   [f"out/check/shots/{c['id']}.fixes.json"], session=key, who=key)
                    if not g.ok:
                        setc(state="error")
                        return False
            todo = []
            for x in [e.get("id") for e in bad] + [s.get("shot") for s in shared]:
                if x and x in c["shots"] and x not in todo:
                    todo.append(x)
            if not todo:
                todo = list(c["shots"])

    queue = list(chunks)

    async def worker() -> None:
        while queue:
            ch = queue.pop(0)
            await run_chunk(ch)
    await asyncio.gather(*(worker() for _ in range(max(1, min(CONFIG["builders"], len(chunks))))))
    if not await cast_task:
        return False
    j = load(jid)
    if j.get("needs"):
        return pause(jid)
    failed = [(k, v) for k, v in ((j.get("pipeline") or {}).get("chunks") or {}).items() if v.get("state") != "passed"]
    if failed:
        zh_parts = "、".join(k + "(" + str(v.get("state")) + ")" for k, v in failed)
        en_parts = ", ".join(k + " (" + str(v.get("state")) + ")" for k, v in failed)
        plural = "s" if len(failed) > 1 else ""
        chat(jid, "system", L(jid, f"有 {len(failed)} 段沒通過鏡頭審查：{zh_parts}，請你看這幾段決定",
                              f"{len(failed)} part{plural} didn't pass shot review: {en_parts}. Please take a look and decide"))
        set_stage(jid, "needs_input")
        return False
    pipe(jid, lambda p: p.__setitem__("phase", "assemble"))
    return await step(jid, "producing", "assemble", {}, ["out/video.mp4"], "done")


# ---------- cast gate ----------
async def cast_gate(jid: str, prev: dict) -> bool:
    d = dir_of(jid)
    prod = read_json(d / "build" / "production.json") or {}
    chars = [c for c in prod.get("characters") or [] if isinstance(c, dict) and c.get("id") and c.get("file") and c.get("sheet")]
    files = {c["file"] for c in chars}
    parallel = len(chars) > 1 and len(files) == len(chars) and all((d / c["sheet"]).exists() for c in chars)
    if (prev.get("cast") or {}).get("pass"):
        return True
    if not parallel:
        return await cast_serial(jid, prev)

    def setc(cid: str, **v: Any) -> None:
        def fn(p: dict) -> None:
            cast = p["cast"]
            cast["chars"] = cast.get("chars") or {}
            cast["chars"][cid] = {**(cast["chars"].get(cid) or {"state": "queued", "round": 0}), **v}
        pipe(jid, fn)
    keep = ((prev.get("cast") or {}).get("chars") or {}) if (prev.get("cast") or {}).get("mode") == "parallel" else {}
    pipe(jid, lambda p: p.__setitem__("cast", {"round": 0, "pass": False, "state": "reviewing", "mode": "parallel",
                                               "chars": {c["id"]: keep[c["id"]] if (keep.get(c["id"]) or {}).get("state") == "passed" else {"state": "queued", "round": 0} for c in chars}}))
    n = len(chars)
    chat(jid, "system", L(jid, f"角色關：{n} 個角色各自由一組審查＋修正同時進行", f"Characters: reviewing and fixing {n} character{'s' if n > 1 else ''} in parallel"))
    shared: list[dict] = []

    async def one(c: dict) -> str:
        reuse = (keep.get(c["id"]) or {}).get("state") == "failed" and (d / "out" / "check" / "cast" / f"review_{c['id']}.json").exists()
        rnd = 0
        while True:
            rnd += 1
            setc(c["id"], state="reviewing", round=rnd)
            if not (rnd == 1 and reuse):
                r = await turn(jid, "cast_qa", {"round": rnd, "character": c}, [f"out/check/cast/review_{c['id']}.json"], session="fresh", who=f"cast-qa-{c['id']}")
                if not r.ok:
                    setc(c["id"], state="error")
                    return "error"
            rv = read_json(d / "out" / "check" / "cast" / f"review_{c['id']}.json") or {}
            if collect_needs(jid, rv.get("needs_user"), f"cast-qa-{c['id']}"):
                setc(c["id"], state="needs_user")
                return "needs"
            if _passed(rv):
                setc(c["id"], state="passed")
                return "passed"
            if rnd >= rounds(jid)["castRounds"]:
                setc(c["id"], state="failed", issues=len(rv.get("issues") or []))
                return "failed"
            setc(c["id"], state="fixing")
            f = await turn(jid, "cast_fix", {"issues": rv.get("issues") or [], "round": rnd, "character": c, "rigFiles": prod.get("rig_files") or []},
                           [c["sheet"], f"out/check/cast/fixes_{c['id']}.json"], session=f"cast-{c['id']}", who=f"cast-{c['id']}")
            if not f.ok:
                setc(c["id"], state="error")
                return "error"
            fx = read_json(d / "out" / "check" / "cast" / f"fixes_{c['id']}.json") or []
            sh = [x for x in (fx if isinstance(fx, list) else fx.get("fixes") or []) if isinstance(x, dict) and x.get("status") == "shared"]
            if sh:
                shared.extend({**x, "character": c["id"]} for x in sh)
                setc(c["id"], state="waiting_shared")
                return "shared"

    async def keep_or_run(c: dict) -> str:
        return "passed" if (keep.get(c["id"]) or {}).get("state") == "passed" else await one(c)
    res = list(await asyncio.gather(*(keep_or_run(c) for c in chars)))
    if "needs" in res:
        return pause(jid)
    k = 0
    while shared and k < rounds(jid)["castRounds"]:
        k += 1
        pipe(jid, lambda p: p["cast"].__setitem__("state", "fixing"))
        f = await turn(jid, "cast_fix", {"issues": list(shared), "round": "shared", "shared": True}, ["out/check/cast/sheet.jpg"], who="director")
        if not f.ok:
            return fail(jid, "producing", f)
        shared.clear()

        async def again(i: int, c: dict) -> str:
            return await one(c) if res[i] in ("passed", "shared") else res[i]
        res = list(await asyncio.gather(*(again(i, c) for i, c in enumerate(chars))))
        if "needs" in res:
            return pause(jid)
    if any(x != "passed" for x in res):
        names = [c.get("name") or c["id"] for i, c in enumerate(chars) if res[i] != "passed"]
        cr = rounds(jid)["castRounds"]

        def fn(p: dict) -> None:
            p["cast"]["state"] = "failed"
            p["cast"]["round"] = cr
        pipe(jid, fn)
        chat(jid, "system", L(jid, f"角色關：{'、'.join(names)} 審了 {cr} 輪還沒通過，請你看設定圖決定",
                              f"Characters: {', '.join(names)} still not passing after {cr} rounds. Please check the character sheets and decide"))
        set_stage(jid, "needs_input")
        return False

    def lineup(p: dict) -> None:
        p["cast"]["state"] = "reviewing"
        p["cast"]["lineup"] = True
    pipe(jid, lineup)
    r = await turn(jid, "cast_qa", {"round": "lineup", "lineup": True}, ["out/check/cast/review.json"], session="fresh", who="cast-qa")
    if not r.ok:
        return fail(jid, "producing", r)
    rv = read_json(d / "out" / "check" / "cast" / "review.json") or {}
    if collect_needs(jid, rv.get("needs_user"), "cast-qa"):
        return pause(jid)
    if _passed(rv):
        def ok(p: dict) -> None:
            p["cast"]["pass"] = True
            p["cast"]["state"] = "passed"
        pipe(jid, ok)
        chat(jid, "system", L(jid, "角色關通過（每個角色各自通過＋並排檢查）", "Characters passed (each one on its own, then side by side)"))
        return True
    return await cast_serial(jid, {"cast": {"round": 0, "pass": False}}, rv)


async def cast_serial(jid: str, prev: dict, first_review: dict | None = None) -> bool:
    d = dir_of(jid)
    if not (prev.get("cast") or {}).get("pass"):
        pipe(jid, lambda p: p.__setitem__("cast", {"round": 0, "pass": False}))
    rnd = 0
    while not ((load(jid).get("pipeline") or {}).get("cast") or {}).get("pass"):
        rnd += 1

        def st(p: dict, r: int = rnd) -> None:
            p["cast"]["round"] = r
            p["cast"]["state"] = "reviewing"
        pipe(jid, st)
        rv = first_review
        if rv is not None:
            first_review = None
        else:
            r = await turn(jid, "cast_qa", {"round": rnd}, ["out/check/cast/review.json"], session="fresh", who="cast-qa")
            if not r.ok:
                return fail(jid, "producing", r)
            rv = read_json(d / "out" / "check" / "cast" / "review.json") or {}
        if collect_needs(jid, rv.get("needs_user"), "cast-qa"):
            return pause(jid)
        if _passed(rv):
            def ok(p: dict) -> None:
                p["cast"]["pass"] = True
                p["cast"]["state"] = "passed"
            pipe(jid, ok)
            chat(jid, "system", L(jid, f"角色關通過（第 {rnd} 輪）", f"Characters passed (round {rnd})"))
            break
        if rnd >= rounds(jid)["castRounds"]:
            pipe(jid, lambda p: p["cast"].__setitem__("state", "failed"))
            chat(jid, "system", L(jid, f"角色關 {rnd} 輪仍未通過，請你看角色設定圖決定", f"Characters still not passing after {rnd} rounds. Please check the character sheets and decide"))
            set_stage(jid, "needs_input")
            return False
        pipe(jid, lambda p: p["cast"].__setitem__("state", "fixing"))
        f = await turn(jid, "cast_fix", {"issues": rv.get("issues") or [], "round": rnd}, ["out/check/cast/sheet.jpg", "out/check/cast/fixes.json"], who="director")
        if not f.ok:
            return fail(jid, "producing", f)
    return True


def pause(jid: str) -> bool:
    set_stage(jid, "needs_input")
    return False


# ---------- final panel ----------
async def final_panel(jid: str) -> None:
    d = dir_of(jid)
    rnd = 0
    while True:
        rnd += 1

        def ph(p: dict, r: int = rnd) -> None:
            p["phase"] = "final"
            p["final"] = {"round": r}
        pipe(jid, ph)
        if not await step(jid, "critiquing", "critique", {"round": rnd}, ["out/check/critique.json"], None, session="fresh", who="critic"):
            return
        c = read_json(d / "out" / "check" / "critique.json") or {}
        must = [m for m in c.get("must_fix") or [] if m]

        def rec(j: dict, r: int = rnd) -> None:
            j["critiqueRounds"] = r
            j["lastCritique"] = {"pass": not must, "must": len(must), "at": now()}
        update(jid, rec)
        needs = collect_needs(jid, c.get("needs_user"), "critic")
        if not must:
            chat(jid, "system", L(jid, "評審：導演能修的都過了，剩下需要你提供的項目", "Final review: everything the director can fix is done. What is left needs your input")
                 if needs else L(jid, f"評審通過（第 {rnd} 輪）", f"Final review passed (round {rnd})"))
            set_stage(jid, "needs_input" if needs else "done")
            return
        if rnd > rounds(jid)["finalRounds"]:
            chat(jid, "system", L(jid, f"評審仍有 {len(must)} 項必修，已達自動修改上限，請你決定",
                                  f"The final review still has {len(must)} must-fix item{'s' if len(must) > 1 else ''} and the automatic fix limit is reached. Please decide"))
            set_stage(jid, "done")
            return
        msg = "\n".join(f"{i + 1}. [{m.get('shot') or '全片'}{' ' + str(m['time']) + 's' if m.get('time') is not None else ''}] {m.get('issue')}{' → 建議：' + m['fix'] if m.get('fix') else ''}"
                        for i, m in enumerate(must))
        chat(jid, "system", L(jid, f"評審第 {rnd} 輪：{len(must)} 項必修，交回導演（每項要附修改前後對照）",
                              f"Final review round {rnd}: {len(must)} must-fix item{'s' if len(must) > 1 else ''}, sent back to the director (each fix needs before/after proof)"))
        if not await step(jid, "revising", "revise", {"message": msg, "round": rnd, "must": must}, ["out/video.mp4", "out/check/fixes.json"]):
            return


async def retry(jid: str) -> Any:
    j = load(jid)
    f = j.get("failed")
    update(jid, lambda x: x.__setitem__("retryPending", True))
    if f == "analyzing":
        return await start(jid)
    if f == "styling":
        if await step(jid, "styling", "style", {}, ["analysis/STYLE.md", "analysis/route.json"], "styled"):
            await pre_production(jid)
        return None
    if f == "planning":
        return await pre_production(jid)
    if f == "replanning":
        last = next((c["text"] for c in reversed(j["chat"]) if c["role"] == "user"), "請重新整理企劃")
        return await step(jid, "replanning", "replan", {"message": last}, ["plan.json"], "plan_review")
    if f == "producing" or j["stage"] == "needs_input":
        if await production(jid):
            await final_panel(jid)
        return None
    if f in ("critiquing", "revising"):
        return await final_panel(jid)
    return None


async def resume(jid: str, *_: Any) -> None:
    j = load(jid)
    update(jid, lambda x: x.__setitem__("needs", []))
    if (dir_of(jid) / "out" / "video.mp4").exists() and (j.get("pipeline") or {}).get("phase") == "final":
        return await final_panel(jid)
    if await production(jid):
        await final_panel(jid)


async def accept(jid: str, *_: Any) -> None:
    j = load(jid)
    p = j.get("pipeline") or {}
    ph = "cast" if p.get("cast") and not p["cast"].get("pass") else p.get("phase")

    def fn(x: dict) -> None:
        x["needs"] = []
        x["error"] = None
        x["failed"] = None
        if ph == "cast":
            x["pipeline"]["cast"] = {"round": 0, **x["pipeline"]["cast"], "pass": True, "state": "passed", "acceptedByUser": True}
        if ph == "shots":
            for c in (x["pipeline"].get("chunks") or {}).values():
                if c.get("state") != "passed":
                    c.update({"state": "passed", "acceptedByUser": True})
        x["chat"].append({"role": "system", "ts": now(), "text": (L(jid, "你接受了目前的角色設定，繼續製作鏡頭。", "You accepted the characters as they are. Going on with the shots.")
                                                              if ph == "cast" else L(jid, "你接受了目前的鏡頭，繼續組裝。", "You accepted the shots as they are. Going on to assembly."))})
    update(jid, fn)
    if ph == "final" or j["stage"] == "done":
        return
    if await production(jid):
        await final_panel(jid)


def cancel(jid: str, *_: Any) -> None:
    for a in list(running.get(jid, set())):
        a.abort()


async def critique(jid: str, *_: Any) -> None:
    await final_panel(jid)
