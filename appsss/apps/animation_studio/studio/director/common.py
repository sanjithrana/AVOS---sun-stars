"""Shared pieces for the crew's steps: the step context, plan helpers, cast loading, rendering helpers."""
from __future__ import annotations

import asyncio
import json
import math
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .. import config
from ..jobs import read_json, read_text, write_json
from ..llm import Crew
from ..render import engines, rig
from ..render.color import norm, palette_roles

LANG_NAME = {"en": "English", "zh-TW": "Traditional Chinese (繁體中文)", "zh-CN": "Simplified Chinese (简体中文)"}


@dataclass
class P:
    jid: str
    dir: Path
    job: dict
    vars: dict
    crew: Crew
    who: str
    log: Callable[[dict], None]
    abort: Any

    @property
    def lang(self) -> str:
        return self.job.get("lang") or "en"

    def t(self, en: str, zh: str) -> str:
        return en if self.lang == "en" else zh

    def tool(self, name: str, detail: str) -> None:
        self.log({"type": "tool", "name": name, "detail": detail, "who": self.who})

    def look_at(self, rel: str) -> None:
        """Shows as 'looked at frames' with a thumbnail in the chat (same event ReelMimic's agents produce)."""
        self.log({"type": "tool", "name": "Read", "detail": str(self.dir / rel).replace("\\", "/"), "who": self.who})

    def think(self, text: str) -> None:
        self.log({"type": "thinking", "text": text, "who": self.who})

    def say(self, text: str) -> None:
        self.log({"type": "text", "text": text, "who": self.who})

    def err(self, text: str) -> None:
        self.log({"type": "error", "text": text, "who": self.who})

    def path(self, rel: str) -> Path:
        return self.dir / rel

    def read(self, rel: str) -> Any:
        return read_json(self.dir / rel)

    def text(self, rel: str) -> str:
        return read_text(self.dir / rel) or ""

    def write(self, rel: str, data: Any) -> None:
        self.tool("Write", rel)
        write_json(self.dir / rel, data)

    def write_text(self, rel: str, s: str) -> None:
        self.tool("Write", rel)
        p = self.dir / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(s, "utf-8")

    @property
    def brief(self) -> str:
        return self.text("brief.md")

    def plan(self) -> dict:
        return self.read("plan.json") or {}

    def aborted(self) -> bool:
        return bool(self.abort.aborted)

    async def run(self, fn: Callable, *a: Any, **k: Any) -> Any:
        return await asyncio.to_thread(fn, *a, **k)

    def lang_rule(self) -> str:
        return (f"Write every human-facing text (titles, summaries, notes, replies) in {LANG_NAME.get(self.lang, 'English')}. "
                "On-screen captions use the language of the user's brief.")


def inputs(p: P) -> list[str]:
    d = p.dir / "inputs"
    return sorted(f"inputs/{f.name}" for f in d.iterdir() if f.is_file()) if d.is_dir() else []


def engine_of(p: P) -> str:
    plan = p.plan()
    route = p.read("analysis/route.json") or {}
    return engines.resolve(plan.get("engine") or route.get("engine"))


def load_cast(p: P, plan: dict | None = None) -> dict:
    plan = plan or p.plan()
    cast = {}
    for c in plan.get("characters") or []:
        if not isinstance(c, dict) or not c.get("id"):
            continue
        f = c.get("file") or f"build/assets/cast/{c['id']}.json"
        d = read_json(p.dir / f)
        cast[c["id"]] = rig.normalize(d, c["id"], c.get("name")) if d else rig.from_description(c["id"], c.get("name") or c["id"], c.get("design") or "")
    return cast


def shot_times(plan: dict) -> list[tuple[str, float, float]]:
    return [(s["id"], float(s.get("start_s") or 0), float(s.get("end_s") or 0)) for s in plan.get("shots") or [] if isinstance(s, dict) and s.get("id")]


def shot_at(plan: dict, t: float) -> str | None:
    for sid, a, b in shot_times(plan):
        if a <= t < b:
            return sid
    st = shot_times(plan)
    return st[-1][0] if st else None


def retime(plan: dict) -> None:
    """Keep start/end continuous after shots were added, removed or changed length."""
    t = 0.0
    bs = ((plan.get("music") or {}).get("bpm") or 0)
    beat = 60.0 / bs if bs else None
    for s in plan.get("shots") or []:
        d = max(0.5, float(s.get("end_s", 0)) - float(s.get("start_s", 0))) if s.get("end_s") is not None else float(s.get("duration") or 3)
        s["start_s"] = round(t, 3)
        s["end_s"] = round(t + d, 3)
        if beat:
            s["start_beat"] = round(s["start_s"] / beat, 2)
            s["end_beat"] = round(s["end_s"] / beat, 2)
        t += d
    plan.setdefault("format", {})["duration_s"] = round(t, 2)


def storyboard_md(plan: dict, lang: str) -> str:
    en = lang == "en"
    L = (lambda e, z: e if en else z)
    lines = [f"# {plan.get('title') or 'Storyboard'}", "", f"**{L('Logline', '一句話故事')}**: {plan.get('logline', '')}", ""]
    look = plan.get("look") or {}
    lines += [f"## {L('World and colour arc', '世界觀與色彩弧線')}", f"- {L('Medium', '媒材')}: {look.get('medium', '')}",
              f"- {L('Palette', '配色')}: {' '.join(look.get('palette') or [])}", f"- {L('Colour arc', '色彩弧線')}: {look.get('color_arc', '')}"]
    if plan.get("motif"):
        lines.append(f"- Motif: {plan['motif']}")
    lines += ["", f"## {L('Borrowed from the reference', '從參考片學到的手法')}"] + [f"- {b}" for b in plan.get("borrowed_from_reference") or []]
    lines += ["", f"## {L('Characters', '角色')}"] + [f"- **{c.get('name')}** ({c.get('id')}): {c.get('design', '')} — {c.get('arc', '')}" for c in plan.get("characters") or []]
    lines += ["", f"## {L('Shots', '鏡頭表')}", "", f"| # | {L('Time', '時間')} | {L('Beats', '拍')} | {L('In', '轉場進')} | {L('What happens', '事件')} | {L('Camera', '鏡頭')} | {L('Reference', '對照參考')} |",
              "|---|---|---|---|---|---|---|"]
    for s in plan.get("shots") or []:
        cam = s.get("camera") or {}
        beats = f"{s.get('start_beat', '')}–{s.get('end_beat', '')}" if s.get("start_beat") is not None else ""
        lines.append(f"| {s.get('id')} | {s.get('start_s', 0):.1f}–{s.get('end_s', 0):.1f}s | {beats} | {s.get('transition_in', '')} | "
                     f"{str(s.get('summary', '')).replace('|', '/')} | {s.get('camera_note') or cam.get('move', '')} | #{s.get('ref_shot', '')} {str(s.get('ref_what', '')).replace('|', '/')} |")
    if plan.get("open_questions"):
        lines += ["", f"## {L('Open questions', '需要你決定')}"] + [f"- {q}" for q in plan["open_questions"]]
    lines += ["", f"_{L('Changelog', '修改紀錄')}: {' → '.join(plan.get('changelog') or [])}_", ""]
    return "\n".join(lines)


def compact_plan(plan: dict, with_scene: bool = False) -> str:
    """A short JSON of the plan for prompts (small local models have small context windows)."""
    keep = {k: plan.get(k) for k in ("title", "logline", "style", "engine", "format", "look", "characters", "open_questions", "music") if plan.get(k)}
    keep["shots"] = [{k: s.get(k) for k in ("id", "start_s", "end_s", "summary", "action", "camera", "text_overlay", "transition_in", "narration") +
                      (("scene",) if with_scene else ()) if s.get(k) not in (None, "", [])} for s in plan.get("shots") or []]
    return json.dumps(keep, ensure_ascii=False)


def report_summary(report: dict, max_shots: int = 30) -> dict:
    sd = report.get("shot_details") or []
    shots = []
    for s in sd[:max_shots]:
        cam = s.get("camera") or {}
        look = s.get("look") or {}
        shots.append({"n": s.get("shot"), "start": round(s.get("start", 0), 2), "end": round(s.get("end", 0), 2),
                      "move": "+".join(cam.get("kind") or []) or "static", "pace": cam.get("pace"),
                      "brightness": look.get("brightness"), "colours": (look.get("dominant") or [])[:3]})
    v = report.get("video") or {}
    return {"duration": v.get("duration"), "size": [v.get("width"), v.get("height")], "crop": report.get("crop"),
            "pacing": report.get("pacing"), "audio": {k: (report.get("audio") or {}).get(k) for k in ("present", "silent", "bpm", "beat_seconds", "best_30s_starts")},
            "look": report.get("look_summary"), "shots": shots}


REF_MOVE = {"push_in": "dolly_in", "zoom_in": "dolly_in", "pull_out": "dolly_out", "zoom_out": "dolly_out", "pan_left": "pan_left",
            "pan_right": "pan_right", "tilt_up": "tilt_up", "tilt_down": "tilt_down", "orbit": "orbit", "rotate": "orbit",
            "static": "static", "shake": "shake", "handheld": "shake"}


def ref_camera(kinds: list[str], pace: str | None) -> dict:
    move = "static"
    for k in kinds or []:
        k = str(k).lower()
        for key, v in REF_MOVE.items():
            if key in k:
                move = v
                break
        if move != "static":
            break
    p = {"still": "slow", "slow": "slow", "medium": "medium", "fast": "fast"}.get(str(pace or "medium"), "medium")
    if move == "static" and pace in ("medium", "fast"):
        move = "shake" if pace == "fast" else "static"
    fill = {"dolly_in": (0.5, 0.72), "dolly_out": (0.72, 0.5)}.get(move, (0.55, 0.55))
    out = {"move": move, "pace": p, "from": {"fill": fill[0]}, "to": {"fill": fill[1]}}
    if move in ("pan_left", "pan_right"):
        out["move"], out["direction"] = "pan", move.split("_")[1]
    if move in ("tilt_up", "tilt_down"):
        out["move"], out["direction"] = "tilt", move.split("_")[1]
    return out


def default_palette(engine: str, report: dict) -> list[str]:
    dom: list[str] = []
    for s in (report.get("shot_details") or [])[:12]:
        for c in ((s.get("look") or {}).get("dominant") or [])[:2]:
            dom.append(norm(c))
    base = {"painted-animation": ["#2A2C52", "#FFD66B", "#F4A6A0", "#9CC9B8", "#F6F1E7"],
            "crayon-storybook": ["#3B3A6B", "#FFC857", "#E9724C", "#7FB685", "#FFF6E5"],
            "pixel-art": ["#1D2B53", "#FFEC27", "#FF004D", "#00E436", "#FFF1E8"],
            "paper-cutout": ["#2E4057", "#F6AE2D", "#F26419", "#86BBD8", "#F7F3E8"],
            "whiteboard": ["#232327", "#3D5AFE", "#E5484D", "#FFD54F", "#FFFFFF"],
            "anime-cel": ["#1F2D5C", "#FFD166", "#EF476F", "#06D6A0", "#F8F9FF"]}.get(engine, ["#24325F", "#FFD54F", "#FF7F6E", "#4DD0E1", "#F7F4EE"])
    if len(dom) >= 3:
        from ..render.color import luma
        uniq = []
        for c in dom:
            if all(abs(luma(c) - luma(u)) > 0.06 or c != u for u in uniq) and c not in uniq:
                uniq.append(c)
        # keep the engine's dark/light anchors, borrow the reference's colours for the accents
        return [base[0]] + uniq[:3] + [base[-1]]
    return base


def ensure_dir(p: Path) -> Path:
    p.mkdir(parents=True, exist_ok=True)
    return p


def copy(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)


def secs(x: Any, d: float = 0.0) -> float:
    try:
        v = float(x)
        return d if math.isnan(v) else v
    except (TypeError, ValueError):
        return d


def short(s: Any, n: int = 80) -> str:
    s = re.sub(r"\s+", " ", str(s or "")).strip()
    return s if len(s) <= n else s[: n - 1] + "…"


def roles_for(plan: dict) -> dict:
    return palette_roles((plan.get("look") or {}).get("palette"))
