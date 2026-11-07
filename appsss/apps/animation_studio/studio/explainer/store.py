"""Where an explainer project lives on disk, with safe read-modify-write of its JSON.

    <STUDIO_EXPLAINER>/<id>/project.json     brief, settings, plan, shots, status, log
    <id>/assets/                             presenter sheets, props, world plate, storyboard frames
    <id>/shots/<S01>/                        line.wav, clip.mp4, fit.mp4
    <id>/final.mp4  final.srt                the finished video
"""
from __future__ import annotations

import json
import os
import random
import re
import string
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .. import config

ROOT = Path(os.environ.get("STUDIO_EXPLAINER") or (config.PROJECTS.parent / "explainer")).resolve()
_LOCK = threading.RLock()
ID_RX = re.compile(r"^[a-z0-9][a-z0-9_-]{0,40}$")


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_id() -> str:
    return "x" + datetime.now().strftime("%Y%m%d") + "-" + "".join(random.choices(string.ascii_lowercase + string.digits, k=5))


def pdir(pid: str) -> Path:
    if not ID_RX.match(pid or ""):
        raise KeyError("bad project id")
    return ROOT / pid


def exists(pid: str) -> bool:
    try:
        return (pdir(pid) / "project.json").is_file()
    except KeyError:
        return False


def load(pid: str) -> dict:
    with _LOCK:
        return json.loads((pdir(pid) / "project.json").read_text("utf-8"))


def save(p: dict) -> dict:
    with _LOCK:
        d = pdir(p["id"])
        d.mkdir(parents=True, exist_ok=True)
        tmp = d / "project.json.tmp"
        tmp.write_text(json.dumps(p, ensure_ascii=False, indent=1), "utf-8")
        tmp.replace(d / "project.json")
        return p


def update(pid: str, fn: Callable[[dict], Any]) -> dict:
    with _LOCK:
        p = load(pid)
        fn(p)
        p["updatedAt"] = now()
        return save(p)


def say(pid: str, text: str, kind: str = "info") -> None:
    def f(p: dict) -> None:
        p.setdefault("log", []).append({"t": now(), "kind": kind, "text": str(text)[:600]})
        p["log"] = p["log"][-120:]
    update(pid, f)


def rel(pid: str, p: Path) -> str:
    return p.resolve().relative_to(pdir(pid).resolve()).as_posix()


def file_path(pid: str, rel_path: str) -> Path | None:
    try:
        base = pdir(pid).resolve()
        p = (base / rel_path).resolve()
        return p if p.is_file() and base in p.parents else None
    except (KeyError, OSError):
        return None


def listing() -> list[dict]:
    out = []
    if ROOT.is_dir():
        for d in ROOT.iterdir():
            try:
                p = json.loads((d / "project.json").read_text("utf-8"))
            except Exception:  # noqa: BLE001 - half-written or foreign folder
                continue
            out.append({k: p.get(k) for k in ("id", "title", "brief", "status", "stage", "seconds", "aspect", "createdAt", "updatedAt", "final", "thumb", "error")})
    return sorted(out, key=lambda x: x.get("updatedAt") or "", reverse=True)


def delete(pid: str) -> None:
    import shutil
    shutil.rmtree(pdir(pid), ignore_errors=True)
