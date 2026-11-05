"""Small helpers every Skill Lab skill uses (a run's files, steps and log)."""
from __future__ import annotations

import threading
from typing import Any

from . import store

SIZES = {"9:16": (720, 1280), "16:9": (1280, 720), "1:1": (1024, 1024)}
cancel_events: dict[str, threading.Event] = {}


class Stopped(Exception):
    pass


def sdict(p: dict) -> dict:
    w, h = SIZES.get(p.get("aspect") or "9:16", SIZES["9:16"])
    return {"id": p["id"], "crew": p.get("crew") or "builtin", "language": "en", "format": {"width": w, "height": h},
            "settings": {"models": p.get("models") or {}, "local_only": bool(p.get("local_only"))}}


def check(pid: str) -> None:
    ev = cancel_events.get(pid)
    if ev is not None and ev.is_set():
        raise Stopped()


def put(pid: str, **kw: Any) -> None:
    store.update(pid, lambda p: p.update(kw))


def step(pid: str, sid: str, **kw: Any) -> None:
    store.update(pid, lambda p: p.setdefault("steps", {}).setdefault(sid, {}).update(kw))


def write(pid: str, name: str, data: bytes) -> str:
    (store.pdir(pid) / name).write_bytes(data)
    return name


def read(pid: str, name: str | None) -> bytes | None:
    f = store.file_path(pid, name) if name else None
    return f.read_bytes() if f else None


def logger(pid: str):
    return lambda ev: store.say(pid, ev.get("text") or "", ev.get("type") or "info") if ev.get("text") else None
