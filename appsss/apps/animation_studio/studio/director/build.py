"""Turning plan shots into rendered files (used by builders, fixers, the director and the style frames)."""
from __future__ import annotations

import json
from pathlib import Path

from .. import config
from ..jobs import read_json, write_json
from ..render import engines, images, scene, shot as shotmod
from .common import P, engine_of, load_cast

HANDLE = 0.35   # extra seconds rendered after each shot so transitions have frames to blend


def shared(p: P) -> dict:
    return read_json(p.dir / "build" / "shared.json") or {}


def lyrics_lines(p: P) -> list:
    j = read_json(p.dir / "analysis" / "lyrics" / "subs.json") or {}
    return [ln for ln in j.get("lines") or [] if ln.get("start") is not None and ln.get("end") is not None]


def plate_for(p: P, setting: str, time: str, engine: str, palette: list[str], W: int, H: int):
    if config.render_settings()["images"] != "ai":
        return None
    f = p.dir / "build" / "plates" / f"{setting}_{time}.jpg"
    if not f.exists():
        prompt = images.plate_prompt(setting, time, engine, palette)
        p.tool("generate_image", f"{setting} · {time}")
        if not images.generate_plate(prompt, f, W, H):
            p.err(p.t(f"Couldn't get an AI background for {setting}; the engine draws it instead.", f"{setting} 的 AI 背景沒有取得，改由引擎自己畫。"))
            return None
    return images.load_plate(f)


def ctx_for(p: P, plan: dict | None = None, cast: dict | None = None, setting: str | None = None, time: str = "day"):
    plan = plan or p.plan()
    cast = cast if cast is not None else load_cast(p, plan)
    eng = engine_of(p)
    lk = engines.look(eng)
    sh = shared(p)
    if sh.get("line_weight"):
        lk = {**lk, "lw": lk["lw"] * float(sh["line_weight"])}
    W, H = shotmod.size_for(plan)
    pal = (plan.get("look") or {}).get("palette") or []
    plate = plate_for(p, setting, time, eng, pal, W, H) if setting else None
    ctx = scene.make_ctx(plan, cast, W, H, lk, lyrics_lines(p), plate)
    ctx.caption_style = sh.get("captions") or {}
    return ctx


def spec_path(sid: str) -> str:
    return f"build/shots/{sid}.json"


def load_spec(p: P, sid: str, plan: dict | None = None, cast_ids: list[str] | None = None) -> dict:
    plan = plan or p.plan()
    shot = next((s for s in plan.get("shots") or [] if s.get("id") == sid), None) or {"id": sid}
    cast_ids = cast_ids if cast_ids is not None else [c["id"] for c in plan.get("characters") or [] if isinstance(c, dict) and c.get("id")]
    draft = scene.draft_spec(shot, plan, cast_ids)
    saved = read_json(p.dir / spec_path(sid))
    spec = scene.normalize_spec(saved or draft, draft, cast_ids)
    spec["id"], spec["start"] = sid, float(shot.get("start_s") or 0)
    spec["duration"] = max(0.4, float(shot.get("end_s") or 0) - float(shot.get("start_s") or 0)) or spec["duration"]
    return spec


def save_spec(p: P, spec: dict) -> None:
    write_json(p.dir / spec_path(spec["id"]), spec)


def render_still(p: P, spec: dict, t: float, rel: str, plan: dict | None = None, cast: dict | None = None) -> dict:
    ctx = ctx_for(p, plan, cast, spec["setting"], spec["time"])
    p.tool("render", f"{spec.get('id')} @ {t:.2f}s → {rel}")
    return shotmod.still(spec, ctx, t, p.dir / rel)


def render_shot_files(p: P, spec: dict, last: bool, plan: dict | None = None, cast: dict | None = None) -> dict:
    """Video + review sheet + character crops + measurements for one shot. Returns the metrics."""
    sid = spec["id"]
    plan = plan or p.plan()
    ctx = ctx_for(p, plan, cast, spec["setting"], spec["time"])
    fps = int((plan.get("format") or {}).get("fps") or 24)
    fps = 24 if fps not in (12, 24, 25, 30) else fps
    # whiteboard: the marker draws a scene only when it's new (first shot, new setting or cast, or a designed transition)
    shots = plan.get("shots") or []
    idx = next((i for i, s in enumerate(shots) if s.get("id") == sid), 0)
    prev = (p.read(f"build/shots/{shots[idx - 1]['id']}.json") or {}) if idx else {}
    same = bool(prev) and prev.get("setting") == spec.get("setting") and \
        sorted(a.get("cast") for a in prev.get("actors") or []) == sorted(a.get("cast") for a in spec.get("actors") or [])
    spec["reveal"] = not same or str(spec.get("transition_in") or "cut") not in ("cut", "smash")
    p.tool("render", f"{sid} · {spec['duration']:.1f}s · {ctx.lk['label']} · {ctx.W}x{ctx.H}")
    m = shotmod.render_shot(spec, ctx, p.dir / "build" / "shots" / f"{sid}.mp4", fps=fps, handle=0.0 if last else HANDLE,
                            abort=lambda: p.aborted())
    sheet = f"out/check/shots/{sid}_sheet.jpg"
    shotmod.shot_sheet(spec, ctx, p.dir / sheet)
    crops = []
    mid = spec["duration"] / 2
    smp = min(m["samples"], key=lambda s: abs(s["t"] - mid)) if m["samples"] else None
    for a in (smp or {}).get("actors", [])[:3]:
        rel = f"out/check/shots/{sid}_crop_{a['cast']}.png"
        shotmod.crop(spec, ctx, smp["t"], a["box"], p.dir / rel)
        crops.append(rel)
    m["sheet"], m["crops"] = sheet, crops
    write_json(p.dir / "build" / "shots" / f"{sid}.metrics.json", m)
    p.look_at(sheet)
    return m


def metrics(p: P, sid: str) -> dict:
    return read_json(p.dir / "build" / "shots" / f"{sid}.metrics.json") or {}


def spec_json_for_prompt(spec: dict) -> str:
    keep = {k: spec.get(k) for k in ("setting", "time", "actors", "props", "text", "camera", "fx", "transition_in", "narration")}
    return json.dumps(keep, ensure_ascii=False)
