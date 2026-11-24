"""Where Auto Clip keeps things: <STUDIO_AUTOCLIP>/settings.json, accounts.json (login tokens, owner-only), jobs/<id>/job.json plus the clips."""
from __future__ import annotations

import copy
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

ROOT = Path(os.environ.get("STUDIO_AUTOCLIP") or (config.PROJECTS.parent / "autoclip")).resolve()
_LOCK = threading.RLock()
ID_RX = re.compile(r"^[a-z0-9][a-z0-9_-]{0,40}$")

DEFAULT_SETTINGS: dict[str, Any] = {
    "rights_ack": False,            # "I own this content or have permission to clip it": nothing posts until this is true
    "autopilot": {
        "enabled": False,           # the master switch for hands-free posting
        "paused": False,            # the kill switch: stops posting at once, keeps everything else
        "review_first": True,       # True: clips wait for you to approve them. False: fully automatic
        "per_day": 3,               # most posts in 24 hours
        "min_gap_minutes": 120,     # at least this long between two posts
        "hours": [9, 21],           # post only from this local hour to that one
        "privacy": "private",       # private | unlisted | public
        "channel": "",              # which connected channel; empty = the first one
        "auto_make": False,         # watch the watch list and make clips from new uploads by itself
        "make_per_video": 3,
    },
    "defaults": {"count": 0, "min_seconds": 30, "max_seconds": 45, "layout": "blur", "caption": "bounce", "quality": "720p", "crew": "builtin",
                 "edit": "classic", "zoom": True, "stickers": True, "look": "clean", "fx": True, "sfx": True, "progress": False, "loudness": True, "music": "none", "music_volume": 0.14, "coach": False,
                 "hype_only": True, "hype_level": "balanced", "cap": {}, "brand": {}, "cap_lang": "auto", "whisper_model": "small"},
    "brands": [],
    "explore_channels": [],         # extra channels the Explore tab follows (@handles)                   # saved looks: [{"name", "caption", "cap", "brand", "layout", "music", "edit", "look"}]
    "experiments": {"enabled": False, "window_hours": 24, "thumbnails": False},   # title (and cover) tests: variant A, then B, then keep the better one
    "watch": [],                    # [{"channel_id": "UC...", "name": "", "seen": ["videoId", ...]}]
    "tz_offset_minutes": 330,       # your clock: used for posting hours (India +5:30 by default)
}


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_id() -> str:
    return "c" + datetime.now().strftime("%Y%m%d") + "-" + "".join(random.choices(string.ascii_lowercase + string.digits, k=5))


def jdir(jid: str) -> Path:
    if not ID_RX.match(jid or ""):
        raise KeyError("bad job id")
    return ROOT / "jobs" / jid


def exists(jid: str) -> bool:
    try:
        return (jdir(jid) / "job.json").is_file()
    except KeyError:
        return False


def _read(p: Path, default: Any) -> Any:
    try:
        return json.loads(p.read_text("utf-8"))
    except Exception:
        return default


def _write(p: Path, data: Any, private: bool = False) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=1, ensure_ascii=False), "utf-8")
    if private:
        try:
            os.chmod(tmp, 0o600)
        except OSError:
            pass
    os.replace(tmp, p)


def _merge(base: dict, new: dict) -> dict:
    out = dict(base)
    for k, v in new.items():
        out[k] = _merge(base[k], v) if isinstance(v, dict) and isinstance(base.get(k), dict) else v
    return out


# ---------- settings ----------
def settings() -> dict:
    s = _merge(copy.deepcopy(DEFAULT_SETTINGS), _read(ROOT / "settings.json", {}))
    d = s.get("defaults") or {}
    if d.get("count") == 3:                                             # the old fixed 3: now decided from the video's length
        d["count"] = 0
    if d.get("min_seconds") == 15 and d.get("max_seconds") == 60:       # the old 15-60 s default: Shorts that hold viewers run 30-45 s
        d["min_seconds"], d["max_seconds"] = 30, 45
    return s


def _caption_keys() -> list[str]:
    from .captions import LABELS
    return list(LABELS)


def clean_settings(new: dict) -> dict:
    """Only known keys, in range. Whatever the page sends, these limits hold."""
    cur = settings()
    ap, nap = cur["autopilot"], (new.get("autopilot") or {})
    for k in ("enabled", "paused", "review_first", "auto_make"):
        if k in nap:
            ap[k] = bool(nap[k])
    if "per_day" in nap:
        ap["per_day"] = max(1, min(20, int(nap["per_day"] or 1)))
    if "min_gap_minutes" in nap:
        ap["min_gap_minutes"] = max(10, min(1440, int(nap["min_gap_minutes"] or 10)))
    if "make_per_video" in nap:
        ap["make_per_video"] = max(1, min(10, int(nap["make_per_video"] or 1)))
    if isinstance(nap.get("hours"), list) and len(nap["hours"]) == 2:
        a, b = (max(0, min(23, int(x))) for x in nap["hours"])
        ap["hours"] = [a, b]
    if nap.get("privacy") in ("private", "unlisted", "public"):
        ap["privacy"] = nap["privacy"]
    if "channel" in nap:
        ap["channel"] = str(nap["channel"] or "")[:60]
    if "rights_ack" in new:
        cur["rights_ack"] = bool(new["rights_ack"])
    if "tz_offset_minutes" in new:
        cur["tz_offset_minutes"] = max(-720, min(840, int(new["tz_offset_minutes"] or 0)))
    ex, nex = cur.setdefault("experiments", {"enabled": False, "window_hours": 24, "thumbnails": False}), (new.get("experiments") or {})
    for k in ("enabled", "thumbnails"):
        if k in nex:
            ex[k] = bool(nex[k])
    if "window_hours" in nex:
        try:
            ex["window_hours"] = max(6, min(96, int(nex["window_hours"])))
        except (TypeError, ValueError):
            pass
    d, nd = cur["defaults"], (new.get("defaults") or {})
    for k, lo, hi in (("count", 0, 20), ("min_seconds", 5, 170), ("max_seconds", 10, 180)):
        if k in nd:
            d[k] = max(lo, min(hi, int(nd[k] or lo)))
    if d["max_seconds"] < d["min_seconds"]:
        d["max_seconds"] = d["min_seconds"]
    for k, ok in (("layout", ("blur", "zoom", "fill", "game", "auto", "centered", "wide", "split", "pip", "trio")), ("caption", tuple(_caption_keys())), ("quality", ("720p", "1080p"))):
        if nd.get(k) in ok:
            d[k] = nd[k]
    for k in ("zoom", "stickers", "fx", "sfx", "progress", "loudness", "coach", "hype_only"):
        if k in nd:
            d[k] = bool(nd[k])
    if nd.get("edit") in ("off", "classic", "punchy", "clean"):
        d["edit"] = nd["edit"]
    if nd.get("look") in ("none", "clean", "cinematic", "vivid", "warm", "cool", "mono", "film"):
        d["look"] = nd["look"]
    if nd.get("hype_level") in ("strict", "balanced", "more"):
        d["hype_level"] = nd["hype_level"]
    if "music" in nd:
        d["music"] = str(nd["music"] or "none")[:60]
    if "music_volume" in nd:
        try:
            d["music_volume"] = max(0.04, min(0.5, float(nd["music_volume"])))
        except (TypeError, ValueError):
            pass
    if "crew" in nd:
        d["crew"] = str(nd["crew"] or "builtin")[:30]
    if nd.get("cap_lang") in ("auto", "roman", "english"):
        d["cap_lang"] = nd["cap_lang"]
    if "whisper_model" in nd:
        from .pipeline import WHISPER_MODELS
        if nd["whisper_model"] in WHISPER_MODELS:
            d["whisper_model"] = nd["whisper_model"]
    if isinstance(nd.get("cap"), dict):
        from .pipeline import CAP_KEYS
        d["cap"] = {k: v for k, v in nd["cap"].items() if k in CAP_KEYS}
    if isinstance(nd.get("brand"), dict):
        from .pipeline import clean_brand
        d["brand"] = clean_brand(nd["brand"])
    if isinstance(new.get("watch"), list):
        old = {w["channel_id"]: w for w in cur["watch"]}
        cur["watch"] = [{"channel_id": str(w["channel_id"])[:40], "name": str(w.get("name") or "")[:80],
                         "seen": (old.get(w["channel_id"]) or {}).get("seen", [])[-200:]}
                        for w in new["watch"] if isinstance(w, dict) and re.match(r"^UC[\w-]{20,24}$", str(w.get("channel_id") or ""))][:20]
    _write(ROOT / "settings.json", cur)
    return cur


BRAND_KEYS = ("caption", "cap", "brand", "layout", "music", "edit", "look", "cap_lang")


def brands() -> list[dict]:
    return list(settings().get("brands") or [])


def save_brand(b: dict) -> list[dict]:
    """Add or replace a saved look by name (at most 30)."""
    from .pipeline import CAP_KEYS, clean_brand
    name = " ".join(str(b.get("name") or "").split())[:40]
    if not name:
        raise ValueError("Give the look a name.")
    item = {"name": name}
    for k in BRAND_KEYS:
        if k in b and b[k] not in (None, ""):
            item[k] = b[k]
    item["cap"] = {k: v for k, v in (item.get("cap") or {}).items() if k in CAP_KEYS} if isinstance(item.get("cap"), dict) else {}
    item["brand"] = clean_brand(item.get("brand"))
    cur = settings()
    lst = [x for x in (cur.get("brands") or []) if x.get("name", "").lower() != name.lower()]
    cur["brands"] = (lst + [item])[-30:]
    _write(ROOT / "settings.json", cur)
    return cur["brands"]


def delete_brand(name: str) -> list[dict]:
    cur = settings()
    cur["brands"] = [x for x in (cur.get("brands") or []) if x.get("name", "").lower() != str(name).lower()]
    _write(ROOT / "settings.json", cur)
    return cur["brands"]


def save_settings(cur: dict) -> None:
    _write(ROOT / "settings.json", cur)


# ---------- accounts (tokens never leave this file, and never reach the page) ----------
def accounts() -> dict:
    return _read(ROOT / "accounts.json", {"client": {}, "channels": {}, "pending": {}})


def save_accounts(a: dict) -> None:
    _write(ROOT / "accounts.json", a, private=True)


# ---------- jobs ----------
def load(jid: str) -> dict:
    return json.loads((jdir(jid) / "job.json").read_text("utf-8"))


def save(job: dict) -> None:
    with _LOCK:
        job["updatedAt"] = now()
        _write(jdir(job["id"]) / "job.json", job)


def update(jid: str, fn: Callable[[dict], None]) -> dict:
    with _LOCK:
        job = load(jid)
        fn(job)
        save(job)
        return job


def say(jid: str, text: str, kind: str = "info") -> None:
    def f(j: dict) -> None:
        j.setdefault("log", []).append({"t": now(), "kind": kind, "text": str(text)[:400]})
        j["log"] = j["log"][-80:]
    update(jid, f)


def listing() -> list[dict]:
    out = []
    for d in sorted((ROOT / "jobs").glob("*/job.json"), reverse=True) if (ROOT / "jobs").is_dir() else []:
        j = _read(d, None)
        if j:
            out.append({k: j.get(k) for k in ("id", "title", "status", "stage", "createdAt", "updatedAt", "source", "error")} |
                       {"preset": (j.get("opts") or {}).get("preset") or "", "clips": len(j.get("clips") or []), "posted": sum(1 for c in j.get("clips") or [] if c.get("youtube_id"))})
    return out
