"""Where a Series lives on disk, and safe read-modify-write of its JSON.

    <STUDIO_SERIES>/<series id>/
        series.json                      title, language, style, characters, locations, story so far, episode index
        refs/                            style reference pictures you uploaded
        characters/<id>/                 sheet_v<n>.png (the character sheet), voice_v<n>.wav (the voice sample)
        locations/<id>/plate_v<n>.png
        episodes/<id>/episode.json       outline, parts, scripts, shots, review state
        episodes/<id>/parts/<n>/         shots/<shot>/{line.wav,key.png,clip.mp4,sfx.wav,fit.mp4}, music.wav, part.mp4
        episodes/<id>/episode.mp4        the approved parts joined
"""
from __future__ import annotations

import json
import os
import random
import re
import string
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .. import config

ROOT = Path(os.environ.get("STUDIO_SERIES") or (config.PROJECTS.parent / "series")).resolve()
_LOCK = threading.RLock()
ID_RX = re.compile(r"^[a-z0-9][a-z0-9_-]{0,40}$")


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_id(prefix: str = "") -> str:
    return prefix + datetime.now().strftime("%Y%m%d") + "-" + "".join(random.choices(string.ascii_lowercase + string.digits, k=5))


def slug(text: str, taken: set[str] | None = None) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")[:24] or "x"
    if not ID_RX.match(s):
        s = "c-" + s
    base, n = s, 2
    while taken and s in taken:
        s, n = f"{base}-{n}", n + 1
    return s


def sdir(sid: str) -> Path:
    if not ID_RX.match(sid or ""):
        raise KeyError("bad series id")
    return ROOT / sid


def exists(sid: str) -> bool:
    try:
        return (sdir(sid) / "series.json").is_file()
    except KeyError:
        return False


def _read(p: Path) -> Any:
    return json.loads(p.read_text("utf-8"))


def _write(p: Path, data: Any) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + f".{threading.get_ident()}.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), "utf-8")
    os.replace(tmp, p)


def load(sid: str) -> dict:
    with _LOCK:
        return _read(sdir(sid) / "series.json")


def save(s: dict) -> dict:
    with _LOCK:
        s["updatedAt"] = now()
        _write(sdir(s["id"]) / "series.json", s)
        return s


def update(sid: str, fn: Callable[[dict], Any]) -> dict:
    with _LOCK:
        s = load(sid)
        fn(s)
        return save(s)


def edir(sid: str, eid: str) -> Path:
    if not ID_RX.match(eid or ""):
        raise KeyError("bad episode id")
    return sdir(sid) / "episodes" / eid


def load_ep(sid: str, eid: str) -> dict:
    with _LOCK:
        return _read(edir(sid, eid) / "episode.json")


def save_ep(sid: str, ep: dict) -> dict:
    with _LOCK:
        ep["updatedAt"] = now()
        _write(edir(sid, ep["id"]) / "episode.json", ep)
        # keep the series' episode index in step (title, status, part count)
        s = load(sid)
        idx = next((e for e in s.setdefault("episodes", []) if e["id"] == ep["id"]), None)
        row = {"id": ep["id"], "number": ep["number"], "title": ep.get("title") or f"Episode {ep['number']}",
               "status": ep.get("status"), "parts": len(ep.get("parts") or []),
               "approvedParts": sum(1 for p in ep.get("parts") or [] if p.get("status") == "approved"),
               "minutes": ep.get("targetMinutes"), "video": ep.get("video")}
        if idx is None:
            s["episodes"].append(row)
        else:
            idx.update(row)
        save(s)
        return ep


def update_ep(sid: str, eid: str, fn: Callable[[dict], Any]) -> dict:
    with _LOCK:
        ep = load_ep(sid, eid)
        fn(ep)
        return save_ep(sid, ep)


def part_dir(sid: str, eid: str, n: int) -> Path:
    return edir(sid, eid) / "parts" / str(int(n))


def list_series() -> list[dict]:
    out = []
    if not ROOT.is_dir():
        return out
    for d in ROOT.iterdir():
        p = d / "series.json"
        if not p.is_file():
            continue
        try:
            s = _read(p)
        except Exception:  # noqa: BLE001 - a half-written file: skip it
            continue
        chars = s.get("characters") or []
        thumb = next((c.get("sheet") for c in chars if c.get("sheet")), None)
        kind = s.get("kind") or "series"
        if kind == "film":
            ep = next(iter(s.get("episodes") or []), None) or {}
            thumb = next((x.get("plate") for x in s.get("locations") or [] if x.get("plate")), thumb)
        out.append({"id": s["id"], "kind": kind, "title": s.get("title"), "stage": (s.get("breakdown") or {}).get("status") if kind == "film" else None,
                    "video": (ep.get("video") if kind == "film" else None), "status": (ep.get("status") if kind == "film" else None), "language": s.get("language"), "languageName": s.get("languageName"),
                    "characters": len(chars), "approved": sum(1 for c in chars if c.get("status") == "approved"),
                    "episodes": len(s.get("episodes") or []), "updatedAt": s.get("updatedAt"), "thumb": thumb,
                    "working": (s.get("work") or {}).get("state") == "running"})
    return sorted(out, key=lambda x: x.get("updatedAt") or "", reverse=True)


def rel(sid: str, p: Path) -> str:
    return p.resolve().relative_to(sdir(sid).resolve()).as_posix()


def file_path(sid: str, rel_path: str) -> Path | None:
    base = sdir(sid).resolve()
    p = (base / rel_path).resolve()
    if p != base and base not in p.parents:
        return None
    return p if p.is_file() else None


def stamp() -> float:
    return time.time()
