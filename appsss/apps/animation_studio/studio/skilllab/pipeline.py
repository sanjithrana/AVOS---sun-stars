"""A Skill Lab run. Each skill brings its own steps (STAGES, LABELS, RUN, last_stage, reset); this file runs them in order on a thread,
keeps finished steps on Continue, and can make one step (and what follows) again.

Mechanical Toy: design lock → three prompts → compact picture → transformed picture (from the compact one) → transformation clip.
Company Story: see company_story.py."""
from __future__ import annotations

import threading
from typing import Any

from ..series import media
from . import base, company_story as CS, mechanical_toy as MT
from . import store
from .base import SIZES, Stopped, sdict

_threads: dict[str, threading.Thread] = {}
_cancel = base.cancel_events
_set, _step, _write, _read, _log = base.put, base.step, base.write, base.read, base.logger
_check = base.check


def do_design(pid: str) -> None:
    p = store.load(pid)
    _step(pid, "design", status="working")
    lock = MT.design(sdict(p), p["subject"], _log(pid))
    pr = MT.prompts(lock, int(p.get("seconds") or 15))
    store.update(pid, lambda q: q.update(lock=lock, prompts=pr, title=f"{lock['subject'][:1].upper()}{lock['subject'][1:]} toy"))
    _step(pid, "design", status="done")
    store.say(pid, f"Design locked: a {lock['form']}, {lock['finish']}, {lock['palette']}.")


def do_compact(pid: str) -> None:
    p = store.load(pid)
    s = sdict(p)
    w, h = s["format"]["width"], s["format"]["height"]
    _step(pid, "compact", status="working")
    img, info = media.picture(p["prompts"]["compact"], [], w, h, media.seed_of(pid, "compact", p.get("version", 1)), f"{pid}-compact", s=s)
    name = _write(pid, "compact.png", img)
    _set(pid, compact=name, thumb=name)
    _step(pid, "compact", status="done", model=info.get("model"), note=info.get("note"))
    store.say(pid, f"Compact device drawn ({info.get('model')}).")


def do_transformed(pid: str) -> None:
    p = store.load(pid)
    s = sdict(p)
    w, h = s["format"]["width"], s["format"]["height"]
    _step(pid, "transformed", status="working")
    ref = _read(pid, p.get("compact"))
    img, info = media.picture(p["prompts"]["transformed"], [ref] if ref else [], w, h, media.seed_of(pid, "transformed", p.get("version", 1)), f"{pid}-transformed", s=s)
    name = _write(pid, "transformed.png", img)
    _set(pid, transformed=name, thumb=name)
    _step(pid, "transformed", status="done", model=info.get("model"), note=info.get("note"))
    store.say(pid, f"Fully transformed toy drawn from the compact picture ({info.get('model')}).")


def do_video(pid: str) -> None:
    from ..explainer import engines
    from ..stickman import video
    p = store.load(pid)
    s = sdict(p)
    a, b = _read(pid, p.get("compact")), _read(pid, p.get("transformed"))
    if not a or not b:
        raise RuntimeError("Both pictures are needed before the clip.")
    secs = int(p.get("seconds") or 15)
    _step(pid, "video", status="working")
    if video.ready(s):
        store.say(pid, f"Seedance 2.0 is making the {secs}-second transformation from both pictures (this can take several minutes).")
        clip = video.clip(p["prompts"]["video"], [a, b], None, secs, p.get("aspect") or "9:16", audio=True)
        engine, note = "Seedance 2.0 reference-to-video", "native mechanical sound"
    else:
        clip = engines.keypose(s, a, b, secs, "push")
        engine, note = "key-pose animatic", "No fal.ai key with credit (Settings), so this is the two pictures joined with a camera move, without sound. Add a key and press Make the clip again."
    name = _write(pid, "transformation.mp4", clip)
    _set(pid, video=name, engine=engine)
    _step(pid, "video", status="done", model=engine, note=note)
    store.say(pid, f"Transformation clip ready ({engine}).")


MT_STAGES = ("design", "compact", "transformed", "video")
MT_LABELS = {"design": "Design lock and prompts", "compact": "Compact device image", "transformed": "Fully transformed image", "video": "Transformation video"}
MT_RUN = {"design": do_design, "compact": do_compact, "transformed": do_transformed, "video": do_video}


def _mt_reset(p: dict, step: str, n: int | None = None) -> None:
    order = MT_STAGES[MT_STAGES.index(step):]
    for st in order:
        p.setdefault("steps", {}).pop(st, None)
        if st != "design":
            p.pop(st, None)
    p["version"] = int(p.get("version", 1)) + 1


SKILLS = {MT.ID: MT, CS.ID: CS}
SPEC: dict[str, dict[str, Any]] = {
    MT.ID: {"stages": MT_STAGES, "labels": MT_LABELS, "run": MT_RUN, "last": lambda p: "design" if p.get("media") == "prompts" else "video", "reset": _mt_reset},
    CS.ID: {"stages": CS.STAGES, "labels": CS.LABELS, "run": CS.RUN, "last": CS.last_stage, "reset": CS.reset},
}
STAGES, LABELS = MT_STAGES, MT_LABELS          # kept for older callers


def spec_of(p: dict) -> dict:
    return SPEC.get(p.get("skill") or MT.ID, SPEC[MT.ID])


def busy(pid: str) -> bool:
    t = _threads.get(pid)
    return bool(t and t.is_alive())


def _run(pid: str, start: str, only: bool = False) -> None:
    try:
        p = store.load(pid)
        sp = spec_of(p)
        stages, last = sp["stages"], sp["last"](p)
        todo = stages[stages.index(start): stages.index(last) + 1] if not only else (start,)
        for st in todo:
            _set(pid, status="working", stage=st, error=None)
            _check(pid)
            try:
                sp["run"][st](pid)
            except Exception:
                _step(pid, st, status="error")
                raise
        _set(pid, status="done")
        store.say(pid, "Ready." if last != stages[-1] else "Your finished media is ready.")
    except Stopped:
        _set(pid, status="stopped")
        store.say(pid, "Stopped.", "warn")
    except Exception as e:  # noqa: BLE001 - kept and shown; Continue picks up where it stopped
        _set(pid, status="error", error=str(e)[:600])
        store.say(pid, f"Stopped at {spec_of(store.load(pid))['labels'].get(store.load(pid).get('stage'), '')}: {str(e)[:300]}", "error")


def start(pid: str, stage: str | None = None, only: bool = False) -> bool:
    if busy(pid):
        return False
    p = store.load(pid)
    stage = stage or spec_of(p)["stages"][0]
    _cancel[pid] = threading.Event()
    _threads[pid] = threading.Thread(target=_run, args=(pid, stage, only), daemon=True, name=f"skill-{pid}")
    _threads[pid].start()
    return True


def redo(pid: str, step: str, n: int | None = None) -> bool:
    """Make `step` again (only scene n when given) and everything after it."""
    if busy(pid):
        return False
    sp = spec_of(store.load(pid))
    if step not in sp["stages"]:
        raise ValueError("no such step")
    def f(p: dict) -> None:
        sp["reset"](p, step, n)
        p["media"] = "media"
    store.update(pid, f)
    return start(pid, step)


def cancel(pid: str) -> None:
    if pid in _cancel:
        _cancel[pid].set()


def resume_stage(p: dict) -> str:
    sp = spec_of(p)
    for st in sp["stages"]:
        if (p.get("steps") or {}).get(st, {}).get("status") != "done":
            return st
    return sp["stages"][-1]


def recover() -> None:
    for row in store.listing():
        if row.get("status") == "working":
            try:
                store.update(row["id"], lambda p: p.update(status="error", error="The studio restarted while this was running. Press Continue; finished steps are kept."))
            except Exception:  # noqa: BLE001
                pass
