"""The Series production line, with a person approving at every gate.

    create ─▶ bible (AI) ─▶ each character: sheet + voice ─▶ YOU approve or redo each one
    new episode ─▶ outline in parts (1 min, 3 min, 3 min, …) ─▶ YOU approve        (or your own script, split in parts)
    each part:  script (AI, in the series' language) ─▶ YOU approve / edit / redo
                render: shot plan → voices → keyframes → lip-sync + action clips → sound effects → music → mix + QA
                ─▶ YOU watch it: approve (story memory updated, next part starts) or redo shots / rewrite
    last part approved ─▶ the parts are joined into the episode

One worker thread per series runs its queue of jobs in order, so you can keep approving while it works. Every
generated file is cached per shot with a fingerprint of what made it: a redo or a resume after a restart only
redoes what changed or is missing.
"""
from __future__ import annotations

import hashlib
import json
import threading
import traceback
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable

from .. import gpu
from ..creative import scene as SG
from . import assemble, film, languages, library, media, store, writers

# ---------- the per-series job queue ----------
_queues: dict[str, deque] = {}
_threads: dict[str, threading.Thread] = {}
_cancel: dict[str, threading.Event] = {}
_qlock = threading.Lock()


class Cancelled(Exception):
    pass


def enqueue(sid: str, label: str, fn: Callable[..., Any], *args: Any) -> None:
    with _qlock:
        q = _queues.setdefault(sid, deque())
        q.append((label, fn, args))
        _cancel.setdefault(sid, threading.Event())
        _set_queue(sid)
        t = _threads.get(sid)
        if t is None or not t.is_alive():
            t = threading.Thread(target=_loop, args=(sid,), daemon=True, name=f"series-{sid}")
            _threads[sid] = t
            t.start()


def _set_queue(sid: str) -> None:
    labels = [x[0] for x in _queues.get(sid, ())]
    store.update(sid, lambda s: s.setdefault("work", {}).update(queue=labels))


def _loop(sid: str) -> None:
    while True:
        with _qlock:
            q = _queues.get(sid)
            if not q:
                _threads.pop(sid, None)
                store.update(sid, lambda s: s.setdefault("work", {}).update(state="idle", queue=[], label=None, step=None))
                return
            label, fn, args = q.popleft()
            _cancel[sid].clear()
        _set_queue(sid)
        store.update(sid, lambda s: s.setdefault("work", {}).update(state="running", label=label, step=None, done=0, total=0,
                                                                   error=None, startedAt=store.now()))
        try:
            fn(sid, *args)
        except Cancelled:
            store.update(sid, lambda s: s["work"].update(state="stopped", error="Stopped."))
            with _qlock:
                _queues.get(sid, deque()).clear()
        except Exception as e:  # noqa: BLE001 - shown on the page; the job's own status says what failed
            msg = f"{e}" or type(e).__name__
            traceback.print_exc()
            store.update(sid, lambda s: s["work"].update(state="error", error=f"{label}: {msg}"[:800]))


def busy(sid: str) -> bool:
    t = _threads.get(sid)
    return bool(t and t.is_alive())


def cancel(sid: str) -> None:
    ev = _cancel.get(sid)
    if ev:
        ev.set()
    with _qlock:
        _queues.get(sid, deque()).clear()


def check(sid: str) -> None:
    if _cancel.get(sid) and _cancel[sid].is_set():
        raise Cancelled()


def progress(sid: str, step: str, done: int, total: int) -> None:
    store.update(sid, lambda s: s.setdefault("work", {}).update(step=step, done=done, total=total))


def log(sid: str) -> Callable[[dict], None]:
    def f(ev: dict) -> None:
        if ev.get("type") in ("error", "text"):
            store.update(sid, lambda s: s.setdefault("log", []).append({"t": store.now(), "who": ev.get("who"), "text": str(ev.get("text"))[:400]})
                         or s.__setitem__("log", s["log"][-80:]))
    return f


def recover() -> None:
    """After a restart: work that was running is marked stopped (Resume picks it up from the cached files)."""
    for row in store.list_series():
        sid = row["id"]

        def fix(s: dict) -> None:
            if (s.get("work") or {}).get("state") == "running":
                s["work"].update(state="stopped", error="Interrupted by a restart. Press Resume.", queue=[])
            for c in s.get("characters") or []:
                if c.get("status") in ("drafting", "redo"):
                    c.update(status="error", error="Interrupted by a restart. Press Redo.")
        s = store.update(sid, fix)

        def fix_ep(ep: dict) -> None:
            for p in ep.get("parts") or []:
                if p.get("status") in ("rendering", "writing", "queued"):
                    p.update(status="stopped", error="Interrupted by a restart. Press Resume.")
            if ep.get("status") in ("outlining", "joining"):
                ep.update(status="stopped", error="Interrupted by a restart. Press Resume.")
        for e in s.get("episodes") or []:
            try:
                store.update_ep(sid, e["id"], fix_ep)
            except FileNotFoundError:
                pass


# ---------- helpers ----------
def _fp(*parts: Any) -> str:
    return hashlib.sha1(json.dumps(parts, ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()[:16]


def _style_refs(s: dict) -> list[bytes]:
    out = []
    for r in (s.get("style") or {}).get("refs") or []:
        p = store.sdir(s["id"]) / r
        if p.is_file():
            out.append(p.read_bytes())
    return out[:3]


def _char(s: dict, cid: str) -> dict:
    c = next((c for c in s.get("characters") or [] if c["id"] == cid), None)
    if c is None:
        raise KeyError(f"no character {cid}")
    return c


def _set_char(sid: str, cid: str, **kw: Any) -> dict:
    return store.update(sid, lambda s: _char(s, cid).update(**kw))


def concurrency() -> int:
    import os
    raw = (os.environ.get("SERIES_CONCURRENCY") or "").strip()
    if raw.isdigit():
        return max(1, min(8, int(raw)))
    online = [w for w in gpu.workers() if gpu.status(w).get("online")]
    return max(1, min(8, 2 * len(online))) if online else 2


# ---------- 1. the bible and the cast ----------
def op_dna(sid: str) -> None:
    """The series' Design DNA from the style notes and (with a crew that can see) the style pictures."""
    s = store.load(sid)
    progress(sid, "writing the Design DNA", 0, 1)
    refs = [store.sdir(sid) / r for r in (s.get("style") or {}).get("refs") or [] if (store.sdir(sid) / r).is_file()][:3]
    dna = writers.design_dna(s, log(sid), images=refs or None)
    store.update(sid, lambda s: s.update(dna=dna, dnaAt=store.now()))


def op_bible(sid: str) -> None:
    s = store.load(sid)
    if not s.get("dna"):
        op_dna(sid)
        s = store.load(sid)
    progress(sid, "writing the series bible", 0, 1)
    b = writers.bible(s, log(sid))
    check(sid)

    def put(s: dict) -> None:
        s.update(logline=b["logline"] or s.get("logline"), world=b["world"])
        if b["style_prompt"] and not (s.get("style") or {}).get("prompt"):
            s.setdefault("style", {})["prompt"] = b["style_prompt"]
        have = {c["id"] for c in s.get("characters") or []}
        for c in b["characters"]:
            if c["id"] not in have:
                s.setdefault("characters", []).append({**c, "status": "drafting", "version": 0, "history": [], "notes": []})
        haveL = {x["id"] for x in s.get("locations") or []}
        for x in b["locations"]:
            if x["id"] not in haveL:
                s.setdefault("locations", []).append({**x, "status": "drafting", "version": 0})
    s = store.update(sid, put)
    failed = []
    for c in [c for c in s["characters"] if c["status"] == "drafting"]:
        try:
            op_character(sid, c["id"], "both", "")
        except Cancelled:
            raise
        except Exception:  # noqa: BLE001 - that character shows its error and a Redo button; carry on with the rest
            failed.append(c["name"])
    for x in [x for x in s.get("locations") or [] if x.get("status") == "drafting"]:
        check(sid)
        op_location(sid, x["id"], "")
    if failed:
        raise RuntimeError(f"Couldn't finish {', '.join(failed)} (see the character card).")


def op_character(sid: str, cid: str, what: str = "both", note: str = "") -> None:
    """Draw the character sheet and/or make the voice sample; then it waits for your approval."""
    s = store.load(sid)
    c = _char(s, cid)
    idx = [x["id"] for x in s["characters"]].index(cid)
    version = int(c.get("version") or 0) + 1
    _set_char(sid, cid, status="redo" if c.get("version") else "drafting", error=None)
    d = store.sdir(sid) / "characters" / cid
    d.mkdir(parents=True, exist_ok=True)
    upd: dict[str, Any] = {"version": version}
    try:
        if what in ("both", "look"):
            progress(sid, f"drawing {c['name']}", 0, 2)
            upload = (store.sdir(sid) / c["upload"]).read_bytes() if c.get("upload") and (store.sdir(sid) / c["upload"]).is_file() else None
            data, info = media.character_sheet(s, c, _style_refs(s), upload, version, note)
            out = d / f"sheet_v{version}.png"
            out.write_bytes(data)
            upd.update(sheet=store.rel(sid, out), sheetInfo=info)
        else:
            upd.update(sheet=c.get("sheet"), sheetInfo=c.get("sheetInfo"))
        check(sid)
        if what in ("both", "voice"):
            progress(sid, f"giving {c['name']} a voice", 1, 2)
            vup = (store.sdir(sid) / c["voice"]["upload"]).read_bytes() if (c.get("voice") or {}).get("upload") and \
                (store.sdir(sid) / c["voice"]["upload"]).is_file() else None
            desc = (c.get("voice") or {}).get("description", "")
            cv = {**c, "voice": {**(c.get("voice") or {}), **({"description": (f"{desc}. {note}" if desc else note)[:400]}
                                                             if note and what == "voice" else {})}}
            data, info = media.design_voice(s, cv, idx + version - 1, vup, f"{s['title']} · {c['name']} voice")
            out = d / f"voice_v{version}.wav"
            out.write_bytes(media.to_wav(data))
            voice = {**cv["voice"], "sample": store.rel(sid, out), "sampleText": info.get("sampleText") or media.sample_text(s, c),
                     "model": info.get("model"), "fallback": info.get("fallback"), "version": version}
            if info.get("edge"):
                voice.update(edge=info["edge"], pitch=info.get("pitch"), rate=info.get("rate"))
            elif not voice.get("edge"):
                voice.update(media.edge_voice(s, c, idx))        # the no-GPU voice for this character, kept for later
            upd["voice"] = voice
        hist = (c.get("history") or []) + [{"version": version, "sheet": upd.get("sheet"), "voice": (upd.get("voice") or c.get("voice") or {}).get("sample"),
                                            "note": note, "at": store.now()}]
        _set_char(sid, cid, **upd, status="review", history=hist[-12:], notes=(c.get("notes") or []) + ([note] if note else []))
    except Cancelled:
        _set_char(sid, cid, status="error", error="Stopped.")
        raise
    except Exception as e:  # noqa: BLE001
        _set_char(sid, cid, status="error", error=str(e)[:500], **{k: v for k, v in upd.items() if k != "version"})
        raise


def op_location(sid: str, lid: str, note: str = "") -> None:
    s = store.load(sid)
    loc = next(x for x in s.get("locations") or [] if x["id"] == lid)
    version = int(loc.get("version") or 0) + 1
    progress(sid, f"painting {loc['name']}", 0, 1)
    try:
        data, info = media.location_plate(s, loc, _style_refs(s), version, note)
    except Exception as e:  # noqa: BLE001 - shots can still be drawn without a plate
        store.update(sid, lambda s: next(x for x in s["locations"] if x["id"] == lid).update(status="error", error=str(e)[:300]))
        return
    out = store.sdir(sid) / "locations" / lid / f"plate_v{version}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(data)
    store.update(sid, lambda s: next(x for x in s["locations"] if x["id"] == lid).update(
        plate=store.rel(sid, out), version=version, status="ready", error=None, info=info))


def ensure_location(sid: str, name: str) -> str:
    """A location the writer named that isn't in the bible yet: add it (painted on first use)."""
    s = store.load(sid)
    for x in s.get("locations") or []:
        if x["id"] == name or x["name"].lower() == name.lower():
            return x["id"]
    lid = store.slug(name, {x["id"] for x in s.get("locations") or []})
    store.update(sid, lambda s: s.setdefault("locations", []).append(
        {"id": lid, "name": name[:40], "description": name, "status": "drafting", "version": 0}))
    return lid


# ---------- 2. episodes ----------
def new_episode(sid: str, brief: str, minutes: float, script_text: str | None, title: str | None) -> dict:
    s = store.load(sid)
    n = len(s.get("episodes") or []) + 1
    eid = f"ep{n}"
    sizes = writers.part_plan(minutes, s.get("partPlan"))
    ep = {"id": eid, "number": n, "title": title or f"Episode {n}", "brief": brief, "targetMinutes": minutes,
          "source": "script" if script_text else "ai", "status": "outlining", "createdAt": store.now(),
          "parts": [{"index": i + 1, "minutes": m, "status": "waiting", "version": 0} for i, m in enumerate(sizes)]}
    store.edir(sid, eid).mkdir(parents=True, exist_ok=True)
    if script_text:
        (store.edir(sid, eid) / "script.txt").write_text(script_text, "utf-8")
    store.save_ep(sid, ep)
    enqueue(sid, f"Episode {n}: outline", op_outline, eid, "")
    return ep


def op_outline(sid: str, eid: str, note: str = "") -> None:
    s = store.load(sid)
    ep = store.load_ep(sid, eid)
    store.update_ep(sid, eid, lambda e: e.update(status="outlining", error=None))
    progress(sid, "outlining the episode", 0, 1)
    try:
        if ep["source"] == "script":
            text = (store.edir(sid, eid) / "script.txt").read_text("utf-8")
            whole = writers.import_script(s, text, log(sid))
            total = writers.script_seconds(whole) / 60
            sizes = writers.part_plan(max(total, 0.5), s.get("partPlan"))
            scripts = writers.split_script(whole, sizes)

            def put(e: dict) -> None:
                e["outline"] = {"title": e.get("title"), "logline": e.get("brief") or "", "fromScript": True}
                e["targetMinutes"] = round(total, 1)
                e["parts"] = [{"index": i + 1, "minutes": m, "summary": "", "script": sc, "status": "script_review" if i == 0 else "waiting",
                               "version": 1, "scriptSeconds": writers.script_seconds(sc)} for i, (m, sc) in enumerate(zip(sizes, scripts))]
                e["status"] = "in_production"
            store.update_ep(sid, eid, put)
        else:
            o = writers.outline(s, ep, log(sid), note)

            def put(e: dict) -> None:
                e["outline"] = {"title": o["title"], "logline": o["logline"]}
                e["title"] = o["title"]
                for p, op in zip(e["parts"], o["parts"]):
                    p.update(summary=op["summary"], beats=op["beats"], endsWith=op["endsWith"])
                e["status"] = "outline_review"
            store.update_ep(sid, eid, put)
        for loc in {sc["location"] for p in store.load_ep(sid, eid)["parts"] for sc in (p.get("script") or {}).get("scenes") or []}:
            ensure_location(sid, loc)
    except Exception as e:
        store.update_ep(sid, eid, lambda x: x.update(status="error", error=str(e)[:500]))
        raise


def op_write_part(sid: str, eid: str, n: int, note: str = "") -> None:
    s = store.load(sid)
    ep = store.load_ep(sid, eid)
    store.update_ep(sid, eid, lambda e: e["parts"][n - 1].update(status="writing", error=None))
    progress(sid, f"writing part {n}", 0, 1)
    try:
        script = writers.part_script(s, ep, n, log(sid), note)
    except Exception as e:
        store.update_ep(sid, eid, lambda x: x["parts"][n - 1].update(status="error", error=str(e)[:500]))
        raise
    for sc in script["scenes"]:
        sc["location"] = ensure_location(sid, sc["location"])

    def put(e: dict) -> None:
        p = e["parts"][n - 1]
        p.update(script=script, status="script_review", version=int(p.get("version") or 0) + 1,
                 scriptSeconds=writers.script_seconds(script), notes=(p.get("notes") or []) + ([note] if note else []))
        p.pop("shots", None)
    store.update_ep(sid, eid, put)
    if (store.load(sid).get("settings") or {}).get("autoApproveScripts"):
        approve_script(sid, eid, n)


def approve_outline(sid: str, eid: str) -> None:
    store.update_ep(sid, eid, lambda e: e.update(status="in_production"))
    enqueue(sid, f"{eid}: write part 1", op_write_part, eid, 1, "")


def approve_script(sid: str, eid: str, n: int) -> None:
    store.update_ep(sid, eid, lambda e: e["parts"][n - 1].update(status="queued", scriptApprovedAt=store.now()))
    enqueue(sid, f"{eid}: render part {n}", op_render_part, eid, n)


def approve_part(sid: str, eid: str, n: int) -> None:
    store.update_ep(sid, eid, lambda e: e["parts"][n - 1].update(status="approved", approvedAt=store.now()))
    enqueue(sid, f"{eid}: after part {n}", op_after_part, eid, n)


def op_after_part(sid: str, eid: str, n: int) -> None:
    """Remember what happened, then start the next part (or join the episode)."""
    s = store.load(sid)
    ep = store.load_ep(sid, eid)
    mem = writers.remember(s, ep["parts"][n - 1].get("script") or {}, log(sid))
    store.update_ep(sid, eid, lambda e: e["parts"][n - 1].update(memory=mem))
    store.update(sid, lambda s: s.setdefault("story", {}).setdefault("facts", []).extend(
        f for f in mem["facts"] if f not in s["story"]["facts"]))
    ep = store.load_ep(sid, eid)
    if n < len(ep["parts"]):
        nxt = ep["parts"][n]
        if ep["source"] == "script" and nxt.get("script"):
            store.update_ep(sid, eid, lambda e: e["parts"][n].update(status="script_review"))
        else:
            op_write_part(sid, eid, n + 1, "")
        return
    op_join(sid, eid)


def op_join(sid: str, eid: str) -> None:
    ep = store.load_ep(sid, eid)
    store.update_ep(sid, eid, lambda e: e.update(status="joining"))
    progress(sid, "joining the parts", 0, 1)
    files, subs, t0 = [], [], 0.0
    for p in ep["parts"]:
        f = store.sdir(sid) / p["video"]
        files.append(f)
        for a, b, txt in p.get("subtitles") or []:
            subs.append((a + t0, b + t0, txt))
        t0 += media.probe_seconds(f)
    out = store.edir(sid, eid) / "episode.mp4"
    assemble.episode(files, out, subs)
    summary = " ".join((p.get("memory") or {}).get("summary", "") for p in ep["parts"]).strip()

    def put(e: dict) -> None:
        e.update(status="done", video=store.rel(sid, out), seconds=round(t0, 1), finishedAt=store.now())
    store.update_ep(sid, eid, put)
    store.update(sid, lambda s: s.setdefault("story", {}).setdefault("episodes", []).append(
        {"episode": ep["number"], "title": ep.get("title"), "summary": summary[:1200]}))


# ---------- 3. rendering one part ----------
def board_gate(s: dict) -> bool:
    """The storyboard is approved before anything moves (on by default; Settings can turn it off for a series)."""
    return bool((s.get("settings") or {}).get("storyboardGate", True))


def op_render_part(sid: str, eid: str, n: int, redo: list[str] | None = None, note: str = "",
                   what: list[str] | None = None, stage: str | None = None) -> None:
    """stage "board": shot plan, sound plan, voices, frames and the storyboard sheet, then it waits for you;
    "all": everything (frames already approved are cached). Without a stage: "board" until the storyboard is approved."""
    s = store.load(sid)
    ep = store.load_ep(sid, eid)
    part = ep["parts"][n - 1]
    if not (part.get("script") or {}).get("scenes"):
        raise RuntimeError(f"Part {n} has no script yet.")
    stage = stage or ("board" if board_gate(s) and not part.get("boardApprovedAt") else "all")
    pdir = store.part_dir(sid, eid, n)
    store.update_ep(sid, eid, lambda e: e["parts"][n - 1].update(status="rendering", error=None, startedAt=store.now(), stage=stage))
    try:
        _render(sid, s, eid, n, pdir, redo or [], note, what or ["picture", "motion"], stage)
    except Cancelled:
        store.update_ep(sid, eid, lambda e: e["parts"][n - 1].update(status="stopped", error="Stopped. Press Resume."))
        raise
    except Exception as e:
        store.update_ep(sid, eid, lambda x: x["parts"][n - 1].update(status="error", error=str(e)[:800]))
        raise


def _render(sid: str, s: dict, eid: str, n: int, pdir: Path, redo: list[str], note: str, what: list[str], stage: str = "all") -> None:
    ep = store.load_ep(sid, eid)
    part = ep["parts"][n - 1]
    script_fp = _fp(part["script"])
    shots = part.get("shots")
    if not shots or part.get("shotsFor") != script_fp:
        progress(sid, f"part {n}: planning shots", 0, 1)
        old = {x["id"]: x for x in shots or []}
        shots = writers.plan_shots(s, part["script"], log(sid))
        for sh in shots:
            sh.update(takes={"voice": 1, "picture": 1, "motion": 1}, files={}, models={}, warnings=[])
            prev = old.get(sh["id"])
            if prev:                     # same shot id: keep its files and fingerprints, so only what changed is redone
                sh.update({k: prev[k] for k in ("takes", "files", "models", "fp", "qa") if prev.get(k)})
        replanned_board = bool(part.get("boardApprovedAt")) and board_gate(s)
        store.update_ep(sid, eid, lambda e: e["parts"][n - 1].update(shots=shots, shotsFor=script_fp,
                                                                     **({"boardApprovedAt": None} if replanned_board else {})))
        if replanned_board and stage == "all":
            stage = "board"              # a new script means a new storyboard to approve
            store.update_ep(sid, eid, lambda e: e["parts"][n - 1].update(stage=stage))
    if redo:
        for sh in shots:
            if sh["id"] in redo:
                for w in what:
                    if w in ("voice", "picture", "motion"):
                        sh.setdefault("takes", {})[w] = int(sh["takes"].get(w) or 1) + 1
                if note:
                    sh["note"] = note
        store.update_ep(sid, eid, lambda e: e["parts"][n - 1].update(shots=shots))
    cast = {c["id"]: c for c in s.get("characters") or []}
    unapproved = sorted({sh["speaker"] for sh in shots if sh.get("speaker") and cast.get(sh["speaker"], {}).get("status") != "approved"})
    if unapproved:
        raise RuntimeError("These characters aren't approved yet: " + ", ".join(cast.get(c, {}).get("name", c) for c in unapproved))
    W, H = s["format"]["width"], s["format"]["height"]
    lock = threading.Lock()
    conc = concurrency()
    total = len(shots)

    def save_shot(sh: dict) -> None:
        with lock:
            store.update_ep(sid, eid, lambda e: _put_shot(e["parts"][n - 1], sh))

    def sdir_(sh: dict) -> Path:
        d = pdir / "shots" / sh["id"]
        d.mkdir(parents=True, exist_ok=True)
        return d

    def cached(sh: dict, key: str, name: str, fp: str) -> Path | None:
        f = sdir_(sh) / name
        return f if f.is_file() and (sh.get("fp") or {}).get(key) == fp else None

    def mark(sh: dict, key: str, name: str, fp: str, info: dict | None = None) -> None:
        sh.setdefault("fp", {})[key] = fp
        sh.setdefault("files", {})[key] = store.rel(sid, sdir_(sh) / name)
        if info:
            sh.setdefault("models", {})[key] = info

    def run_all(label: str, fn: Callable[[dict], None], items: list[dict]) -> None:
        done = [0]
        errors: list[str] = []
        progress(sid, f"part {n}: {label}", 0, len(items))

        def one(sh: dict) -> None:
            check(sid)
            try:
                fn(sh)
            except Cancelled:
                raise
            except Exception as e:  # noqa: BLE001 - one retry with a new seed, then report the shot
                try:
                    check(sid)
                    sh["retry"] = int(sh.get("retry") or 0) + 1
                    fn(sh)
                except Cancelled:
                    raise
                except Exception as e2:  # noqa: BLE001
                    errors.append(f"{sh['id']}: {e2 or e}")
            save_shot(sh)
            with lock:
                done[0] += 1
                progress(sid, f"part {n}: {label}", done[0], len(items))
        with ThreadPoolExecutor(max_workers=conc) as pool:
            for f in [pool.submit(one, sh) for sh in items]:
                f.result()
        if errors:
            raise RuntimeError(f"{label}: {len(errors)} shot(s) failed. " + " | ".join(errors[:4]))

    sheets = {cid: (store.sdir(sid) / c["sheet"]).read_bytes() for cid, c in cast.items()
              if c.get("status") == "approved" and c.get("sheet") and (store.sdir(sid) / c["sheet"]).is_file()}
    locs = {x["id"]: x for x in s.get("locations") or []}

    # the sound designer: ambience per scene, a sound for every action shot, the part's music cue
    part = store.load_ep(sid, eid)["parts"][n - 1]
    if not part.get("sound") or part.get("soundFor") != script_fp:
        progress(sid, f"part {n}: sound design", 0, 1)
        sound = writers.plan_sound(s, part["script"], shots, log(sid), part.get("summary") or "")
        audio = (s.get("breakdown") or {}).get("audio") or {}
        if audio.get("music"):
            sound["music"] = audio["music"]                       # the prompt's own audio direction wins
        if audio.get("ambience"):
            sound["ambience"] = {k: audio["ambience"] for k in sound["ambience"]}
        for sh in shots:
            if sh.get("sfxLocked"):
                sound["sfx"][sh["id"]] = sh.get("sfx") or ""
            elif sh["kind"] == "action" and sound["sfx"].get(sh["id"]):
                sh["sfx"] = sound["sfx"][sh["id"]]
        store.update_ep(sid, eid, lambda e: e["parts"][n - 1].update(sound=sound, soundFor=script_fp, shots=shots))
    else:
        sound = part["sound"]
    qa_on = bool((s.get("settings") or {}).get("shotQA", True))
    sheet_paths = {cid: store.sdir(sid) / c["sheet"] for cid, c in cast.items()
                   if c.get("status") == "approved" and c.get("sheet") and (store.sdir(sid) / c["sheet"]).is_file()}

    def qa(sh: dict, stage: str, frame: Path) -> dict | None:
        if not qa_on:
            return None
        imgs = [sheet_paths[c] for c in (sh.get("subjects") or []) if c in sheet_paths][:3] + [frame]
        res = writers.qa_shot(s, sh, imgs, stage, log(sid))
        if res is not None:
            sh.setdefault("qa", {})[stage] = res
        return res

    # 1) voices: every line, in the character's approved voice (also fixes each dialogue shot's length)
    def voice(sh: dict) -> None:
        if sh["kind"] != "dialogue":
            return
        c = cast[sh["speaker"]]
        fp = _fp(sh["text"], sh["emotion"], (c.get("voice") or {}).get("sample"), sh["takes"]["voice"], s.get("language"), media.choice(s, "lines"))
        if not cached(sh, "line", "line.wav", fp):
            data, info = media.say_line(s, c, sh["text"], sh["emotion"] or "neutral",
                                        media.seed_of(sid, eid, n, sh["id"], sh["takes"]["voice"], sh.get("retry", 0)),
                                        f"{s['title']} · E{ep['number']}P{n} · {sh['id']} voice")
            (sdir_(sh) / "line.wav").write_bytes(media.to_wav(data))
            mark(sh, "line", "line.wav", fp, info)
        secs = media.wav_seconds((sdir_(sh) / "line.wav").read_bytes())
        sh["seconds"] = round(max(float(sh.get("planned") or 0), min(14.0, secs + 0.35)), 2)   # a timed film shot keeps its length
        if isinstance(sh.get("blueprint"), dict) and abs(sh["blueprint"]["duration"] - sh["seconds"]) > 0.01:
            sh["blueprint"] = SG.retime(sh["blueprint"], sh["seconds"])      # the timeline follows the real line
    run_all("voices", voice, shots)

    # missing location plates (a place the writer added)
    for lid in sorted({sh["location"] for sh in shots}):
        if lid in locs and not locs[lid].get("plate"):
            op_location(sid, lid)
    s = store.load(sid)
    locs = {x["id"]: x for x in s.get("locations") or []}

    # 2) keyframes: compiled from the scene graph + Design DNA, drawn from the approved sheets + the place; QA'd
    def key(sh: dict) -> None:
        loc = locs.get(sh["location"]) or {}
        plate_p = store.sdir(sid) / loc["plate"] if loc.get("plate") else None
        plate = plate_p.read_bytes() if plate_p and plate_p.is_file() else None
        tag = f"{s['title']} · E{ep['number']}P{n} · {sh['id']} picture"
        ov = sh.get("keyOverride") or {}
        if ov.get("pending") == "modify":            # Modify shot: edit the current frame, keep the rest
            data, info = media.modify_keyframe(s, sh, (sdir_(sh) / "key.png").read_bytes(), ov["instruction"], sheets,
                                               media.seed_of(sid, eid, n, sh["id"], "mod", ov.get("n", 1)), tag)
            (sdir_(sh) / "key.png").write_bytes(data)
            sh["keyOverride"] = {**ov, "pending": None, "fp": _fp("override", ov)}
            mark(sh, "key", "key.png", sh["keyOverride"]["fp"], info)
            return
        if ov.get("fp") and (sdir_(sh) / "key.png").is_file():   # your own picture, or a modified frame: keep it
            sh.setdefault("fp", {})["key"] = ov["fp"]
            return
        note = sh.get("note") or ""
        fp = _fp(media.keyframe_prompt(s, sh, [], note), sh["subjects"], [cast[c].get("sheet") for c in sh["subjects"] if c in cast],
                 loc.get("plate"), sh["takes"]["picture"], media.choice(s, "pictures"))
        if cached(sh, "key", "key.png", fp):
            return
        seed = media.seed_of(sid, eid, n, sh["id"], sh["takes"]["picture"], sh.get("retry", 0))
        data, info = media.keyframe(s, sh, sheets, plate, seed, tag, note)
        (sdir_(sh) / "key.png").write_bytes(data)
        res = qa(sh, "key", sdir_(sh) / "key.png")
        if res is not None and not res.get("pass") and res.get("fix"):   # one regeneration with the supervisor's fix
            data, info = media.keyframe(s, sh, sheets, plate, seed + 7919, tag, (note + ". " if note else "") + res["fix"])
            (sdir_(sh) / "key.png").write_bytes(data)
            info["qaRetry"] = True
            res2 = qa(sh, "key", sdir_(sh) / "key.png")
            if res2 is not None:
                sh["qa"]["key"] = {**res2, "retried": True, "first": res}
        mark(sh, "key", "key.png", fp, info)
    run_all("keyframes", key, shots)

    if stage == "board":                 # the storyboard: every frame + the numbered sheet, then it waits for you
        t, frames = 0.0, []
        for sh in shots:
            sh["plan"] = media.planned_motion(s, sh, _lipsync(sh))
            save_shot(sh)
            frames.append((pdir / "shots" / sh["id"] / "key.png", f"{t:.1f}–{t + sh['seconds']:.1f}s · {sh['framing']} · {sh.get('camera', 'static').replace('_', ' ')}"))
            t += sh["seconds"]
        try:
            film.collage(frames, pdir / "storyboard.png", W / H)
        except Exception:  # noqa: BLE001 - the frames are still there to review
            traceback.print_exc()
        store.update_ep(sid, eid, lambda e: e["parts"][n - 1].update(
            status="board_review", storyboard=store.rel(sid, pdir / "storyboard.png") if (pdir / "storyboard.png").is_file() else None,
            boardAt=store.now(), boards=int(e["parts"][n - 1].get("boards") or 0) + 1, seconds=round(t, 1)))
        return

    # 3) motion: lip-synced talking shots, animated action shots, motion transfer, keep-the-motion restyles; QA'd
    def motion(sh: dict) -> None:
        kf = (sdir_(sh) / "key.png").read_bytes()
        driver = sdir_(sh) / "driver.mp4" if sh.get("driver") and (sdir_(sh) / "driver.mp4").is_file() else None
        fp = _fp(sh["fp"].get("key"), sh.get("fp", {}).get("line"), sh.get("blueprint") or sh["motion"], sh.get("note"),
                 sh["seconds"], sh["takes"]["motion"], bool(driver), s.get("dna"),
                 media.choice(s, "lipsync" if _lipsync(sh) else "motion"))
        if cached(sh, "clip", "clip.mp4", fp):
            return
        tag = f"{s['title']} · E{ep['number']}P{n} · {sh['id']} clip"
        seed = media.seed_of(sid, eid, n, sh["id"], "m", sh["takes"]["motion"], sh.get("retry", 0))
        note = sh.get("note") or ""
        old = sdir_(sh) / "clip.mp4"
        made = None
        if driver is not None:
            made = media.motion_transfer(s, sh, kf, driver.read_bytes(), sh["seconds"], seed, tag)
        elif (sh.get("keyOverride") or {}).get("keepMotion") and sh["kind"] == "action" and old.is_file():
            made = media.restyle_keep_motion(s, sh, old.read_bytes(), kf, sh["seconds"], seed, tag)
        if made is None:
            made = (media.talking(s, sh, kf, (sdir_(sh) / "line.wav").read_bytes(), sh["seconds"], seed, tag, note) if _lipsync(sh)
                    else media.action(s, sh, kf, sh["seconds"], seed, tag, note))
        data, info = made
        old.write_bytes(data)
        if qa_on and info.get("model") not in (None, "still"):
            res = qa(sh, "clip", media.strip(old, sdir_(sh) / "strip.png", sh["seconds"]))
            if res is not None and not res.get("pass") and res.get("fix") and driver is None:
                fix = (note + ". " if note else "") + res["fix"]
                data, info = (media.talking(s, sh, kf, (sdir_(sh) / "line.wav").read_bytes(), sh["seconds"], seed + 104729, tag, fix)
                              if _lipsync(sh) else media.action(s, sh, kf, sh["seconds"], seed + 104729, tag, fix))
                old.write_bytes(data)
                info["qaRetry"] = True
                res2 = qa(sh, "clip", media.strip(old, sdir_(sh) / "strip.png", sh["seconds"]))
                if res2 is not None:
                    sh["qa"]["clip"] = {**res2, "retried": True, "first": res}
        mark(sh, "clip", "clip.mp4", fp, info)
    run_all("animating", motion, shots)

    # 4) sound effects for action shots, then one ambience bed per scene
    def foley(sh: dict) -> None:
        if not sh.get("sfx"):
            return
        fp = _fp(sh["fp"].get("clip"), sh["sfx"], media.choice(s, "sfx"))
        if cached(sh, "sfx", "sfx.wav", fp):
            return
        data, info = media.sfx(sh, (sdir_(sh) / "clip.mp4").read_bytes(), sh["seconds"], f"{s['title']} · {sh['id']} sound", s)
        if data:
            (sdir_(sh) / "sfx.wav").write_bytes(data)
            mark(sh, "sfx", "sfx.wav", fp, info)
        else:
            sh.setdefault("models", {})["sfx"] = info
    run_all("sound effects", foley, shots)
    amb_files: dict[str, Path] = {}
    amb_info: dict[str, dict] = {}
    for scene_id in dict.fromkeys(sh["scene"] for sh in shots):
        first = next(sh for sh in shots if sh["scene"] == scene_id)
        text = (sound.get("ambience") or {}).get(scene_id) or ""
        f = pdir / f"ambience_{scene_id}.wav"
        afp = _fp(first["fp"].get("clip"), text)
        if f.is_file() and (part.get("ambienceFp") or {}).get(scene_id) == afp:
            amb_files[scene_id] = f
            continue
        check(sid)
        data, info = media.ambience((sdir_(first) / "clip.mp4").read_bytes(), text, first["seconds"], f"{s['title']} · {scene_id} ambience", s)
        amb_info[scene_id] = {**info, "fp": afp}
        if data:
            f.write_bytes(media.to_wav(data))
            amb_files[scene_id] = f
    if amb_info:
        store.update_ep(sid, eid, lambda e: e["parts"][n - 1].update(
            ambienceFp={**(e["parts"][n - 1].get("ambienceFp") or {}), **{k: v["fp"] for k, v in amb_info.items()}},
            ambienceInfo={**(e["parts"][n - 1].get("ambienceInfo") or {}), **amb_info}))

    # 5) fit every shot and build its audio (line + sound + the scene's ambience), check it
    scene_t: dict[str, float] = {}
    offsets: dict[str, float] = {}
    for sh in shots:
        offsets[sh["id"]] = scene_t.get(sh["scene"], 0.0)
        scene_t[sh["scene"]] = offsets[sh["id"]] + sh["seconds"]

    def finish_shot(sh: dict) -> None:
        d = sdir_(sh)
        line = d / "line.wav" if sh["kind"] == "dialogue" and (d / "line.wav").is_file() else None
        fx = d / "sfx.wav" if (sh.get("files") or {}).get("sfx") and (d / "sfx.wav").is_file() else None
        assemble.fit_shot(d / "clip.mp4", d / "fit.mp4", sh["seconds"], W, H)
        assemble.shot_audio(d / "shot.wav", sh["seconds"], line, fx, ambience=amb_files.get(sh["scene"]), ambience_at=offsets[sh["id"]])
        warn = []
        st = assemble.frame_stats(d / "fit.mp4", min(0.5, sh["seconds"] / 2))
        if st is None or st[1] < 3:
            warn.append("the picture looks blank")
        if line is not None and media.wav_rms(line.read_bytes()) < 0.003:
            warn.append("the line is silent")
        for k, inf in (sh.get("models") or {}).items():
            if inf and inf.get("fallback"):
                warn.append(f"{ {'line': 'voice', 'key': 'picture', 'clip': 'motion', 'sfx': 'sound'}.get(k, k)}: "
                            f"{inf.get('note') or 'fallback (' + str(inf.get('model')) + ')'}")
        for stage_name, res in (sh.get("qa") or {}).items():
            if res and not res.get("pass"):
                bad = [f"{k}: {v['why']}" for k, v in (res.get("checks") or {}).items() if not v.get("ok")]
                warn.append(f"QA ({'picture' if stage_name == 'key' else 'motion'}): " + ("; ".join(bad) or res.get("fix") or "failed"))
        sh["warnings"] = warn
    run_all("checking shots", finish_shot, shots)

    # 6) music for the part (the sound designer's cue), then the mix
    progress(sid, f"part {n}: music and mix", 0, 1)
    total_s = sum(sh["seconds"] for sh in shots)
    part = store.load_ep(sid, eid)["parts"][n - 1]
    cue = (part.get("sound") or {}).get("music") or part.get("summary") or ""
    mfp = _fp((s.get("music") or {}), cue, round(total_s))
    music_f = pdir / "music.wav"
    if not (music_f.is_file() and part.get("musicFp") == mfp):
        data, minfo = media.music(s, cue, total_s, f"{s['title']} · E{ep['number']}P{n} music")
        if data:
            music_f.write_bytes(data)
        elif music_f.exists():
            music_f.unlink()
        store.update_ep(sid, eid, lambda e: e["parts"][n - 1].update(musicFp=mfp, musicInfo=minfo))
    t, subs = 0.0, []
    for sh in shots:
        if sh["kind"] == "dialogue":
            name = cast.get(sh["speaker"], {}).get("name", "")
            subs.append((round(t + 0.12, 2), round(t + sh["seconds"] - 0.05, 2), f"{name}: {sh['text']}" if s.get("subtitleNames") else sh["text"]))
        t += sh["seconds"]
    out = pdir / "part.mp4"
    assemble.part([{"video": pdir / "shots" / sh["id"] / "fit.mp4", "audio": pdir / "shots" / sh["id"] / "shot.wav"} for sh in shots],
                  pdir / "mix", out, W, H, music_f if music_f.is_file() else None, subs)
    secs = media.probe_seconds(out)
    store.update_ep(sid, eid, lambda e: e["parts"][n - 1].update(
        status="review", video=store.rel(sid, out), seconds=round(secs, 1), subtitles=subs, renderedAt=store.now(),
        renders=int(e["parts"][n - 1].get("renders") or 0) + 1, warnings=sum(len(sh.get("warnings") or []) for sh in shots)))


def _lipsync(sh: dict) -> bool:
    """A line is lip-synced unless its shot is wide / busy (then the line plays over an animated action shot)."""
    return sh["kind"] == "dialogue" and sh.get("lipsync", True) is not False


def approve_board(sid: str, eid: str, n: int) -> None:
    store.update_ep(sid, eid, lambda e: e["parts"][n - 1].update(status="queued", boardApprovedAt=store.now()))
    enqueue(sid, f"{eid}: animate part {n}", op_render_part, eid, n, None, "", None, "all")


def batch_camera(sid: str, eid: str, n: int, ids: list[str], move: str | None, ease: str | None, lens: int | None, angle: str | None) -> list[str]:
    """One camera change on many shots (e.g. every shot: handheld, 35 mm): the scene graphs and blueprints are
    rewritten, the compiled prompts follow; returns the shots that changed."""
    s = store.load(sid)
    changed: list[str] = []

    def put(e: dict) -> None:
        for sh in e["parts"][n - 1].get("shots") or []:
            if ids and sh["id"] not in ids:
                continue
            st = media.stage_of(s, sh)
            bp = media.blueprint_of(s, sh)
            new_st = st
            if lens or angle:
                new_st = SG.normalize_scene({**st, "camera": None, **({"lens": lens} if lens else {}),
                                             "angle": SG.angle_of(angle or sh.get("angle") or "")},
                                            subjects=[a["id"] for a in st["actors"]], framing=st["framing"], location=st["location"], time=st["time"])
                if not lens:
                    new_st["camera"]["lens"] = st["camera"]["lens"]
            cam = {"move": move or bp["camera"]["move"], "ease": ease or bp["camera"]["ease"]}
            new_bp = SG.normalize_motion({**bp, "camera": cam}, new_st, duration=bp["duration"], speaker=sh.get("speaker"))
            if SG.changed_parts(st, new_st, bp, new_bp):
                sh.update(stage=new_st, blueprint=new_bp, camera=new_bp["camera"]["move"], directed=store.now())
                if new_st != st:
                    sh.pop("keyOverride", None)
                changed.append(sh["id"])
    store.update_ep(sid, eid, put)
    return changed


# ---------- films: prompt → breakdown → cast + world → storyboard → animation ----------
def op_analyze(sid: str, note: str = "") -> None:
    s = store.load(sid)
    store.update(sid, lambda s: s.setdefault("breakdown", {}).update(status="analyzing", error=None))
    progress(sid, "reading your prompt", 0, 1)
    try:
        bd = film.analyze(s, s.get("prompt") or "", note, log(sid))
    except Exception as e:
        store.update(sid, lambda s: s["breakdown"].update(status="error", error=str(e)[:500]))
        raise
    for lid in s.get("libraryPicks") or []:            # your library characters: matched by name, else added to the cast
        if not library.exists(lid):
            continue
        row = library.load(lid)
        hit = next((c for c in bd["characters"] if c["name"].lower() == row["name"].lower() or row["name"].lower() in c["name"].lower()), None)
        if hit:
            hit["library"] = lid
        else:
            bd["characters"].append({"name": row["name"], "look": row.get("look") or "", "outfit": row.get("outfit") or "", "props": "",
                                     "personality": row.get("personality") or "", "voice": (row.get("voice") or {}).get("description") or "",
                                     "gender": row.get("gender") or "other", "age": row.get("age") or "", "actions": [], "library": lid})
    if not bd["shots"]:
        store.update(sid, lambda s: s["breakdown"].update(status="error", error="No shots could be read from the prompt."))
        raise RuntimeError("No shots could be read from the prompt: describe what happens, ideally in timed sections (0–3 sec: …).")

    def put(s: dict) -> None:
        s["breakdown"] = {**bd, "status": "review", "at": store.now(), "notes": ((s.get("breakdown") or {}).get("notes") or []) + ([note] if note else [])}
        if not s.get("titleGiven") and bd["title"]:
            s["title"] = bd["title"]
        s["logline"] = bd["logline"] or s.get("logline")
        if not (s.get("style") or {}).get("given"):
            s.setdefault("style", {})["description"] = bd["style"] or (s.get("style") or {}).get("description") or ""
        if bd["tone"]:
            s["tone"] = bd["tone"]
        if (bd.get("audio") or {}).get("music") and not (s.get("music") or {}).get("style"):
            s.setdefault("music", {})["style"] = bd["audio"]["music"][:200]
    store.update(sid, put)
    check(sid)
    op_dna(sid)


def op_film_cast(sid: str) -> None:
    """The approved breakdown → characters (from your library, or drawn + voiced for your approval) and the world
    reference pictures."""
    s = store.load(sid)
    bd = s.get("breakdown") or {}
    if not s.get("dna"):
        op_dna(sid)

    def put(s: dict) -> None:
        taken = {c["id"] for c in s.get("characters") or []}
        have = {c["name"].lower() for c in s.get("characters") or []}
        for c in bd.get("characters") or []:
            if c["name"].lower() in have:
                continue
            if c.get("library") and library.exists(c["library"]):
                continue                                   # copied below (needs files)
            new = film.character_from(c, taken, film.first_line(bd, c["name"]))
            taken.add(new["id"])
            s.setdefault("characters", []).append(new)
        ltaken = {x["id"] for x in s.get("locations") or []}
        lhave = {x["name"].lower() for x in s.get("locations") or []}
        for x in bd.get("locations") or []:
            if x["name"].lower() in lhave:
                continue
            lid = store.slug(x["name"], ltaken)
            ltaken.add(lid)
            s.setdefault("locations", []).append({"id": lid, "name": x["name"], "description": x["description"], "status": "drafting", "version": 0})
        s["breakdown"]["status"] = "approved"
        s["breakdown"]["approvedAt"] = store.now()
    s = store.update(sid, put)
    for c in bd.get("characters") or []:
        if c.get("library") and library.exists(c["library"]) and c["name"].lower() not in {x["name"].lower() for x in store.load(sid)["characters"]}:
            library.add_to(sid, c["library"], name=c["name"])
    s = store.load(sid)
    failed = []
    for c in [c for c in s["characters"] if c["status"] == "drafting"]:
        try:
            op_character(sid, c["id"], "both", "")
        except Cancelled:
            raise
        except Exception:  # noqa: BLE001 - shown on the card with a Redo button
            failed.append(c["name"])
    for x in [x for x in s.get("locations") or [] if not x.get("plate")]:
        check(sid)
        op_location(sid, x["id"], "")
    if failed:
        raise RuntimeError(f"Couldn't finish {', '.join(failed)} (see the character card).")


def start_storyboard(sid: str) -> dict:
    """The film's one episode / part, scripted from the approved breakdown; its storyboard is drawn next."""
    s = store.load(sid)
    bd = s.get("breakdown") or {}
    script = film.script_from(s, bd)
    minutes = round(max(0.05, (bd.get("duration") or writers.script_seconds(script)) / 60), 3)
    for sc in script["scenes"]:
        sc["location"] = ensure_location(sid, sc["location"])
    if not s.get("episodes"):
        ep = {"id": "ep1", "number": 1, "title": s["title"], "brief": s.get("logline") or "", "targetMinutes": minutes, "source": "film",
              "status": "in_production", "createdAt": store.now(), "outline": {"title": s["title"], "logline": s.get("logline") or ""},
              "parts": [{"index": 1, "minutes": minutes, "summary": s.get("logline") or "", "script": script, "status": "queued", "version": 1,
                         "scriptSeconds": writers.script_seconds(script), "scriptApprovedAt": store.now()}]}
        store.edir(sid, "ep1").mkdir(parents=True, exist_ok=True)
        store.save_ep(sid, ep)
    else:
        def put(e: dict) -> None:
            p = e["parts"][0]
            if p.get("script") != script:
                p.update(script=script, version=int(p.get("version") or 0) + 1, scriptSeconds=writers.script_seconds(script), boardApprovedAt=None)
            p.update(status="queued", error=None)
            e.update(status="in_production", targetMinutes=minutes, error=None)
        store.update_ep(sid, "ep1", put)
    store.update(sid, lambda s: s["breakdown"].update(storyboardFor=_fp(bd.get("shots"))))
    enqueue(sid, "Storyboard", op_render_part, "ep1", 1, None, "", None, "board")
    return store.load_ep(sid, "ep1")


def _put_shot(part: dict, sh: dict) -> None:
    for i, x in enumerate(part.get("shots") or []):
        if x["id"] == sh["id"]:
            part["shots"][i] = sh
            return


# ---------- what the page shows ----------
def snapshot(sid: str) -> dict:
    s = store.load(sid)
    eps = []
    for e in s.get("episodes") or []:
        try:
            eps.append(store.load_ep(sid, e["id"]))
        except FileNotFoundError:
            continue
    lg = languages.get(s.get("language") or "en")
    out = {"series": s, "episodes": eps, "busy": busy(sid), "ready": media.ready_report(s.get("language") or "en"),
           "language": {"code": lg.code, "name": lg.name, "script": lg.script, "note": lg.note}}
    if s.get("kind") == "film":
        bd = s.get("breakdown") or {}
        out["film"] = {"stages": film.stages(s, eps),
                       "breakdownChanged": bool(eps) and bd.get("storyboardFor") not in (None, _fp(bd.get("shots")))}
    return out
