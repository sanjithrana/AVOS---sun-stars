"""Takes: every version of a shot is kept, so you can redo one shot and still go back.

AVOS could already redo a single shot (`POST /{pid}/redo` with `n`), but the redo overwrote the old picture, so a
second attempt that came out worse lost the first. That is the wrong way round when the common case is a run where
most shots are fine and three are not -- a measured eleven-shot cooking run had four shots the picture model had
collapsed into their own reference, and no way to keep the good seven while trying those four again.

Borrowed from Maestro's Director, which keeps "plans, prompts and takes together so you can revise individual shots".

The one design rule: `shot["picture"]` and `shot["video"]` always hold the CHOSEN take's file name, exactly as they
did before takes existed. Everything that reads a shot keeps working and knows nothing about any of this.

    takes.add(sh, "picture", "S03.png", model="flux")   # drawn; becomes the chosen take
    takes.add(sh, "picture", "S03-b.png", model="flux") # redrawn; the new one is chosen, the first is still there
    takes.pick(sh, "picture", first_id)                 # back to the first, and sh["picture"] follows
"""
from __future__ import annotations

import time
from typing import Any

KINDS = ("picture", "video")
LIMIT = 8                      # per shot, per kind; older unchosen takes fall off the end


def _list(shot: dict, kind: str) -> list[dict]:
    allt = shot.setdefault("takes", [])
    return [t for t in allt if t.get("kind") == kind]


def _seq(shot: dict) -> int:
    """A counter that only goes up, per shot.

    Ordering by the clock looked right until two takes landed in the same second -- which is normal, because a redo
    of a cached shot takes milliseconds -- and then "newest first" came back in whatever order the list happened to
    be in. The clock is kept for showing a person when a take was made; the order comes from this.
    """
    return max((int(t.get("seq") or 0) for t in shot.get("takes", [])), default=0) + 1


def _new_id(shot: dict, kind: str, seq: int) -> str:
    return f"{kind[0]}{seq}-{int(time.time() * 1000) % 100000}"


def add(shot: dict, kind: str, file: str, model: str = "", prompt: str = "", note: str = "") -> dict:
    """Records a freshly made picture or clip and makes it the chosen one."""
    if kind not in KINDS:
        raise ValueError(f"a take is a {' or a '.join(KINDS)}, not a {kind!r}")
    seq = _seq(shot)
    t = {"id": _new_id(shot, kind, seq), "seq": seq, "kind": kind, "file": file, "model": model,
         "prompt": prompt, "note": note, "at": round(time.time())}
    shot.setdefault("takes", []).append(t)
    _choose(shot, kind, t)
    prune(shot, kind)
    return t


def _choose(shot: dict, kind: str, take: dict) -> None:
    for other in _list(shot, kind):
        other["chosen"] = other is take
    shot[kind] = take["file"]


def chosen(shot: dict, kind: str) -> dict | None:
    return next((t for t in _list(shot, kind) if t.get("chosen")), None)


def pick(shot: dict, kind: str, take_id: str) -> bool:
    """Switches which take this shot uses. False when there is no such take, so a stale id cannot blank a shot.

    Picking by hand also marks the take kept, and a kept take is never pruned. Choosing a take is the one clear signal
    that it matters: without this, going back to an early take and then trying a few more would quietly delete the
    very one you went back to.
    """
    t = next((t for t in _list(shot, kind) if t.get("id") == take_id), None)
    if not t:
        return False
    t["kept"] = True
    _choose(shot, kind, t)
    return True


def listing(shot: dict, kind: str) -> list[dict]:
    """Newest first, which is the order a person wants to look through them in."""
    return sorted(_list(shot, kind), key=lambda t: int(t.get("seq") or 0), reverse=True)


def prune(shot: dict, kind: str, limit: int = LIMIT) -> list[str]:
    """Drops the oldest takes past the limit and returns their files, for the caller to delete.

    Never the chosen one and never one picked by hand. If every take has been kept deliberately the list simply grows,
    which is the right answer: a person who kept eight takes meant to keep eight takes.
    """
    old = [t for t in sorted(_list(shot, kind), key=lambda t: int(t.get("seq") or 0))
           if not t.get("chosen") and not t.get("kept")]
    drop = old[:max(0, len(_list(shot, kind)) - limit)]
    if not drop:
        return []
    ids = {id(t) for t in drop}
    shot["takes"] = [t for t in shot.get("takes", []) if id(t) not in ids]
    keep = keeps(shot)
    return [t["file"] for t in drop if t.get("file") and t["file"] not in keep]


def keeps(shot: dict) -> set[str]:
    """Every file this shot still refers to. Nothing in here may be deleted."""
    out = {t.get("file") for t in shot.get("takes", []) if t.get("file")}
    out |= {shot.get(k) for k in KINDS if shot.get(k)}
    return {f for f in out if f}


def clear_pointer(shot: dict, kind: str) -> None:
    """Readies a shot to be made again, WITHOUT throwing away what is already there.

    This is what a reset calls. The pointer goes, so the stage draws the shot again; the takes stay, so if the new one
    is worse the old one is one click away. Before takes existed, a reset simply deleted the picture.
    """
    shot[kind] = None
    for t in _list(shot, kind):
        t["chosen"] = False


def summary(shots: list[dict], kind: str = "picture") -> str:
    """One line for the step note: how much was made again and how much is still the first attempt."""
    n = sum(len(_list(sh, kind)) for sh in shots)
    extra = n - len(shots)
    return f"{len(shots)} shots, {n} takes" + (f" ({extra} redone)" if extra > 0 else "")
