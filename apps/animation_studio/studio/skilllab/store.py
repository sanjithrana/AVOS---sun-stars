"""Where a Skill Lab run lives: <STUDIO_SKILLS>/<id>/run.json plus its pictures and clip."""
from __future__ import annotations

import json
import os
import random
import re
import shutil
import string
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .. import config

ROOT = Path(os.environ.get("STUDIO_SKILLS") or (config.PROJECTS.parent / "skills")).resolve()
_LOCK = threading.RLock()
ID_RX = re.compile(r"^[a-z0-9][a-z0-9_-]{0,40}$")


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_id() -> str:
    return "k" + datetime.now().strftime("%Y%m%d") + "-" + "".join(random.choices(string.ascii_lowercase + string.digits, k=5))


def pdir(pid: str) -> Path:
    if not ID_RX.match(pid or ""):
        raise KeyError("bad run id")
    return ROOT / pid


def exists(pid: str) -> bool:
    try:
        return (pdir(pid) / "run.json").is_file()
    except KeyError:
        return False


def load(pid: str) -> dict:
    with _LOCK:
        return json.loads((pdir(pid) / "run.json").read_text("utf-8"))


def save(p: dict) -> dict:
    with _LOCK:
        d = pdir(p["id"])
        d.mkdir(parents=True, exist_ok=True)
        tmp = d / "run.json.tmp"
        tmp.write_text(json.dumps(p, ensure_ascii=False, indent=1), "utf-8")
        tmp.replace(d / "run.json")
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
        p["log"] = p["log"][-80:]
    update(pid, f)


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
                p = json.loads((d / "run.json").read_text("utf-8"))
            except Exception:  # noqa: BLE001 - half-written or foreign folder
                continue
            out.append({k: p.get(k) for k in ("id", "skill", "title", "subject", "status", "stage", "aspect", "createdAt", "updatedAt", "video", "thumb", "error", "media")})
    return sorted(out, key=lambda x: x.get("updatedAt") or "", reverse=True)


def delete(pid: str) -> None:
    shutil.rmtree(pdir(pid), ignore_errors=True)
