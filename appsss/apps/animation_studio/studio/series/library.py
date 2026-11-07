"""Your character library: approved characters saved once (sheet, voice sample, description) and cast again in any
film or series without drawing them again.

    <STUDIO_LIBRARY>/characters/<id>/character.json   name, look, outfit, personality, voice (description, sample line)
                                    /sheet.png        the approved character sheet
                                    /voice.wav        the approved voice sample
"""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any

from . import store

ROOT = Path(os.environ.get("STUDIO_LIBRARY") or (store.ROOT.parent / "library")).resolve() / "characters"
FIELDS = ("name", "role", "age", "gender", "personality", "look", "outfit", "catchphrase", "actions")


def _dir(lid: str) -> Path:
    if not store.ID_RX.match(lid or ""):
        raise KeyError("bad library id")
    return ROOT / lid


def exists(lid: str) -> bool:
    try:
        return (_dir(lid) / "character.json").is_file()
    except KeyError:
        return False


def load(lid: str) -> dict:
    return json.loads((_dir(lid) / "character.json").read_text("utf-8"))


def list_all() -> list[dict]:
    out = []
    if ROOT.is_dir():
        for d in ROOT.iterdir():
            f = d / "character.json"
            if f.is_file():
                try:
                    out.append(json.loads(f.read_text("utf-8")))
                except ValueError:
                    continue
    return sorted(out, key=lambda c: c.get("savedAt") or "", reverse=True)


def save_from(sid: str, cid: str) -> dict:
    """An approved character of a film / series → the library (saving it again updates the same entry)."""
    s = store.load(sid)
    c = next((x for x in s.get("characters") or [] if x["id"] == cid), None)
    if c is None:
        raise KeyError("no such character")
    if c.get("status") != "approved" or not c.get("sheet"):
        raise ValueError(f"Approve {c['name']} first: the library keeps approved characters.")
    origin = f"{sid}/{cid}"
    lid = next((x["id"] for x in list_all() if x.get("origin") == origin), None) or c.get("fromLibrary") \
        or store.slug(c["name"], {x["id"] for x in list_all()})
    d = _dir(lid)
    d.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(store.sdir(sid) / c["sheet"], d / "sheet.png")
    voice = dict(c.get("voice") or {})
    if voice.get("sample") and (store.sdir(sid) / voice["sample"]).is_file():
        shutil.copyfile(store.sdir(sid) / voice["sample"], d / "voice.wav")
        voice["sample"] = "voice.wav"
    voice.pop("upload", None)
    row = {"id": lid, **{k: c.get(k) for k in FIELDS if c.get(k) is not None}, "voice": voice, "sheet": "sheet.png",
           "origin": origin, "from": s.get("title"), "savedAt": store.now(), "sheetInfo": c.get("sheetInfo")}
    (d / "character.json").write_text(json.dumps(row, ensure_ascii=False, indent=1), "utf-8")
    store.update(sid, lambda s: next(x for x in s["characters"] if x["id"] == cid).update(fromLibrary=lid))
    return row


def add_to(sid: str, lid: str, name: str | None = None) -> str:
    """Cast a library character: its sheet and voice are copied in and it starts approved (redo it if this film needs
    a variant)."""
    row = load(lid)
    s = store.load(sid)
    taken = {x["id"] for x in s.get("characters") or []}
    existing = next((x for x in s.get("characters") or [] if x.get("fromLibrary") == lid), None)
    if existing:
        return existing["id"]
    cid = store.slug(name or row["name"], taken)
    d = store.sdir(sid) / "characters" / cid
    d.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(_dir(lid) / "sheet.png", d / "sheet_v1.png")
    voice = dict(row.get("voice") or {})
    if (_dir(lid) / "voice.wav").is_file():
        shutil.copyfile(_dir(lid) / "voice.wav", d / "voice_v1.wav")
        voice["sample"] = store.rel(sid, d / "voice_v1.wav")
    c = {"id": cid, **{k: row.get(k) for k in FIELDS if row.get(k) is not None}, "name": name or row["name"], "voice": voice,
         "sheet": store.rel(sid, d / "sheet_v1.png"), "sheetInfo": {**(row.get("sheetInfo") or {}), "library": True},
         "status": "approved", "approvedAt": store.now(), "version": 1, "approvedVersion": 1, "fromLibrary": lid,
         "history": [{"version": 1, "sheet": store.rel(sid, d / "sheet_v1.png"), "voice": voice.get("sample"), "note": "from your library", "at": store.now()}],
         "notes": []}
    c.setdefault("gender", "other")
    store.update(sid, lambda s: s.setdefault("characters", []).append(c))
    return cid


def delete(lid: str) -> None:
    shutil.rmtree(_dir(lid), ignore_errors=True)


def file_path(lid: str, name: str) -> Path | None:
    if name not in ("sheet.png", "voice.wav") or not exists(lid):
        return None
    p = _dir(lid) / name
    return p if p.is_file() else None


def public(row: dict) -> dict[str, Any]:
    return {**row, "sheetUrl": f"library/files/{row['id']}/sheet.png",
            "voiceUrl": f"library/files/{row['id']}/voice.wav" if (row.get("voice") or {}).get("sample") else None}
