"""Cast memory: the studio remembers every character it has built, across videos.

Each remembered character keeps
  - one locked identity (the exact look words, pasted first into every picture prompt),
  - one seed (so a text-only picture model starts from the same face every time),
  - a clean identity portrait (front view, plain background: the reference a picture model looks at),
  - the design sheet and up to four approved frames (more references once an edit model is ready),
  - the voice and the videos it appeared in.

How it is used
  plan   : a character whose name you used before gets its remembered look back (the script writer is told the cast too)
  design : a remembered character is NOT redrawn; its portrait and sheet are copied in, so the face is the same video after video
  board  : the identity line, the seed and the portrait go into every shot; a vision model (when your crew has one) compares each
           frame with the portrait and redraws once if it is not the same character
  approve: what you approve is saved (or updated) in memory

Lives in <explainer root>/../cast_memory.json and <..>/cast_memory/<id>/."""
from __future__ import annotations

import json
import os
import re
import threading
from pathlib import Path
from typing import Any, Callable

from . import store

_LOCK = threading.RLock()
MAX_FRAMES = 4


def root() -> Path:
    return Path(os.environ.get("AVOS_CAST_MEMORY") or (store.ROOT.parent / "cast_memory"))


def _file() -> Path:
    return root().with_suffix(".json")


def key(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(name or "").lower()).strip("-")[:40] or "character"


def _load() -> dict:
    try:
        d = json.loads(_file().read_text("utf-8"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _save(d: dict) -> None:
    f = _file()
    f.parent.mkdir(parents=True, exist_ok=True)
    tmp = f.with_suffix(".tmp")
    tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1), "utf-8")
    os.replace(tmp, f)


def listing() -> list[dict]:
    with _LOCK:
        d = _load()
    return sorted(d.values(), key=lambda m: m.get("updated") or "", reverse=True)


def get(mid: str) -> dict | None:
    with _LOCK:
        return _load().get(mid)


def find(name: str) -> dict | None:
    """The remembered character with this name (case and spacing don't matter)."""
    return get(key(name))


def path(mid: str, rel: str | None) -> Path | None:
    if not rel:
        return None
    p = (root() / mid / rel).resolve()
    return p if p.is_file() and root().resolve() in p.parents else None


def read(mid: str, rel: str | None) -> bytes | None:
    p = path(mid, rel)
    return p.read_bytes() if p else None


def identity(c: dict) -> str:
    """The locked identity line: name, then the exact look. Pasted first into every picture prompt."""
    look = " ".join(str(c.get("look") or "").split()).rstrip(".")
    return f"{c['name']}: {look}" if look else c["name"]


def cast_block(brief: str, limit: int = 6) -> str:
    """Told to the script writer: the characters it already knows, so it reuses their exact look instead of inventing a new one."""
    known = listing()
    named = [m for m in known if re.search(rf"\b{re.escape(m['name'])}\b", brief or "", re.I)]
    if not named:
        return ""
    lines = "\n".join(f'- "{m["name"]}" (id "{m["id"]}"): {m["look"]}' for m in named[:limit])
    return ("Known cast (the studio has already built these characters; when the idea uses one, keep its name and copy its look word for word):\n"
            f"{lines}\n")


def apply(plan: dict) -> list[str]:
    """Characters of a new plan that the studio already knows get their remembered look, seed and id link. Returns their names."""
    used = []
    for c in plan.get("characters") or []:
        m = find(c["name"])
        if not m:
            continue
        c["look"] = m["look"]
        c["memory"] = m["id"]
        if m.get("voice"):
            c["voice"] = m["voice"]
        used.append(c["name"])
    return used


def seed(c: dict, fallback: int) -> int:
    m = get(c.get("memory") or "") if c.get("memory") else None
    return int(m["seed"]) if m and m.get("seed") is not None else fallback


def remember(pid: str, c: dict, portrait: bytes | None, sheet: bytes | None, seed_value: int, approved: bool) -> dict:
    """Save (or update) a character after its design. Its look becomes the locked identity."""
    mid = c.get("memory") or key(c["name"])
    d_dir = root() / mid
    d_dir.mkdir(parents=True, exist_ok=True)
    with _LOCK:
        d = _load()
        m = d.get(mid) or {"id": mid, "name": c["name"], "created": store.now(), "projects": [], "frames": [], "seed": seed_value}
        m.update({"name": c["name"], "look": c["look"], "identity": identity(c), "voice": c.get("voice") or m.get("voice") or "",
                  "updated": store.now(), "approved": bool(approved or m.get("approved"))})
        if portrait:
            (d_dir / "portrait.png").write_bytes(portrait)
            m["portrait"] = "portrait.png"
        if sheet:
            (d_dir / "sheet.png").write_bytes(sheet)
            m["sheet"] = "sheet.png"
        if pid not in m["projects"]:
            m["projects"] = (m["projects"] + [pid])[-30:]
        d[mid] = m
        _save(d)
    c["memory"] = mid
    return m


def add_frame(mid: str, data: bytes, tag: str) -> None:
    """A frame you approved becomes one more reference for this character (the newest four are kept)."""
    if not data:
        return
    d_dir = root() / mid
    if not d_dir.is_dir():
        return
    name = f"frame_{key(tag)}.png"
    (d_dir / name).write_bytes(data)
    with _LOCK:
        d = _load()
        m = d.get(mid)
        if not m:
            return
        frames = [f for f in m.get("frames") or [] if f != name] + [name]
        for old in frames[:-MAX_FRAMES]:
            try:
                (d_dir / old).unlink()
            except OSError:
                pass
        m["frames"] = frames[-MAX_FRAMES:]
        m["updated"] = store.now()
        _save(d)


def forget(mid: str) -> bool:
    with _LOCK:
        d = _load()
        if mid not in d:
            return False
        d.pop(mid)
        _save(d)
    import shutil
    shutil.rmtree(root() / mid, ignore_errors=True)
    return True


def refs(mid: str) -> list[bytes]:
    """The references for this character, cleanest first: portrait, then the newest approved frame."""
    m = get(mid)
    if not m:
        return []
    out = [b for b in (read(mid, m.get("portrait")), read(mid, (m.get("frames") or [None])[-1])) if b]
    return out


# ---------- the drift check ----------
CHECK_SYS = ("You are a continuity supervisor on an animated film. Picture 1 is the approved reference of a character. Picture 2 is a new frame. "
             "Decide only whether the character in picture 2 is the SAME character as picture 1: same face shape, hair, glasses, skin, outfit and colours. "
             "Pose, angle, expression and lighting may differ. Answer JSON only.")


def check(s: dict, portrait: bytes | None, frame: bytes, name: str, log: Callable[[dict], None] | None = None) -> dict | None:
    """{"same": bool, "fix": str} from a vision model, or None when no vision model is available (then nothing is judged)."""
    if not portrait or not frame:
        return None
    try:
        from ..series import writers
        c = writers.crew(s, "continuity check", log)
        if not c.enabled or not c.vision():
            return None
        import tempfile
        with tempfile.TemporaryDirectory() as t:
            a, b = Path(t) / "ref.png", Path(t) / "frame.png"
            a.write_bytes(portrait)
            b.write_bytes(frame)
            data: Any = writers.ask(s, "continuity check", writers.system("avos-continuity-check", CHECK_SYS),
                                    f'The character is {name}. Answer {{"same": true|false, "differences": "what differs, one sentence", '
                                    f'"fix": "one sentence to add to the picture prompt so the next try matches"}}',
                                    log, max_tokens=300, temperature=0.1, images=[a, b])
    except Exception as e:  # noqa: BLE001 - the check is a helper; it never stops a video
        return {"same": True, "skipped": str(e)[:160]}
    if not isinstance(data, dict):
        return None
    return {"same": bool(data.get("same", True)), "differences": str(data.get("differences") or "")[:240], "fix": str(data.get("fix") or "")[:240]}
