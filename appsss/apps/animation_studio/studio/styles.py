"""ReelMimic's style registry (.claude/skills/video-clone/styles/*.md): one Markdown file per style."""
from __future__ import annotations

import re
from pathlib import Path

from . import config
from .render import engines as _engines


def _front(md: str) -> dict:
    m = re.match(r"^---\s*\n(.*?)\n---", md, re.S)
    out = {}
    if m:
        for ln in m.group(1).splitlines():
            if ":" in ln:
                k, v = ln.split(":", 1)
                out[k.strip()] = v.split("#")[0].strip()
    return out


def _section(md: str, names: tuple[str, ...]) -> str:
    for n in names:
        m = re.search(rf"^##\s*{n}.*?\n(.*?)(?=^##\s|\Z)", md, re.S | re.M)
        if m:
            return m.group(1).strip()
    return ""


def registry() -> list[dict]:
    out = []
    if not config.STYLES.is_dir():
        return out
    for f in sorted(config.STYLES.glob("*.md")):
        if f.name.startswith("_"):
            continue
        md = f.read_text("utf-8")
        fm = _front(md)
        title = re.search(r"^#\s+(.+)$", md, re.M)
        engine = fm.get("engine", "")
        out.append({
            "name": fm.get("name") or f.stem, "engine": engine, "medium": fm.get("medium", "2d-vector"),
            "priority": int(fm.get("priority") or 50), "title": title.group(1).strip() if title else f.stem,
            "features": _section(md, ("辨識特徵", "Recognition", "Features"))[:1200],
            "defaults": _section(md, ("製作預設", "Production defaults", "Defaults"))[:1500],
            "pitfalls": _section(md, ("已知的坑", "Known pitfalls", "Pitfalls"))[:1200],
            "installed": engine in _engines.ENGINES, "file": f"styles/{f.name}",
        })
    return out


def by_name(name: str | None) -> dict | None:
    return next((s for s in registry() if s["name"] == name), None)


KEYWORDS = {
    "painted-story-mv": r"watercolor|水彩|hand.?painted|手繪|painted|mv|music video|歌",
    "crayon-storybook": r"crayon|蠟筆|蜡笔|picture book|繪本|绘本|colored pencil|色鉛筆|kids|children",
    "pixel-story": r"pixel|像素|8.?bit|16.?bit|retro game|點陣",
    "paper-cutout": r"paper|剪紙|剪纸|cut.?out|stop.?motion|定格|craft",
    "whiteboard-explainer": r"whiteboard|白板|doodle|sketch|手繪線稿|explain|解說|教學|tutorial",
    "anime-cel": r"anime|動畫|动画|cel|賽璐璐|manga|日系|japanese",
    "narrated-comic-vlog": r"comic|漫畫|漫画|vlog|narrat|旁白|story of my|my story|第一人稱|chibi|q版",
    "music-kinetic": r"lyric|kinetic|typography|字卡|beat|節奏|節拍",
    "product-promo": r"product|產品|产品|app|launch|promo|廣告|广告|feature",
    "faceless-explainer": r"explainer|facts|知識|数据|data|stats",
    "motion-graphics": r"motion graphic|logo|infographic|動態圖像|title",
}
MEDIUM_WORDS = {"2d-painted": r"watercolor|水彩|painted|手繪", "2d-crayon": r"crayon|蠟筆|picture book|繪本", "2d-pixel": r"pixel|像素|8.?bit",
                "2d-paper": r"paper cut|剪紙|stop.?motion|定格", "2d-lineart": r"whiteboard|白板|doodle|line art|線稿",
                "2d-cel": r"anime|cel|賽璐璐|日系動畫", "2d-vector": r"vector|flat|motion graphic|扁平"}


def measure_look(sheet: Path | None) -> dict:
    """Simple measurements of the reference frames that hint at the medium."""
    try:
        import cv2
        import numpy as np
        img = cv2.imread(str(sheet))
        if img is None:
            return {}
        small = cv2.resize(img, (480, int(480 * img.shape[0] / img.shape[1])))
        hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
        q = (small // 32).reshape(-1, 3)
        uniq = len({tuple(x) for x in q[:: max(1, len(q) // 20000)]})
        edges = cv2.Canny(cv2.cvtColor(small, cv2.COLOR_BGR2GRAY), 80, 160).mean() / 255
        white = float(((small > 225).all(axis=2)).mean())
        lap = cv2.Laplacian(cv2.cvtColor(small, cv2.COLOR_BGR2GRAY), cv2.CV_64F).var()
        return {"saturation": round(float(hsv[..., 1].mean() / 255), 3), "colour_bins": uniq, "edge_density": round(float(edges), 3),
                "white_ratio": round(white, 3), "texture": round(float(lap), 1)}
    except Exception:
        return {}


def pick(brief: str, report: dict, metrics: dict) -> tuple[dict, float, list[str], list[dict]]:
    """Score every installed 2D style. Returns (style, confidence, why, alternatives)."""
    styles = [s for s in registry() if s["installed"] and s["medium"].startswith("2d")]
    if not styles:
        styles = [{"name": "motion-graphics", "engine": "hyperframes", "medium": "2d-vector", "priority": 60, "title": "Motion graphics"}]
    text = (brief or "").lower()
    scores = []
    for s in styles:
        sc = s["priority"] / 100
        why = []
        kw = KEYWORDS.get(s["name"])
        if kw and re.search(kw, text):
            sc += 1.2
            why.append("your brief asks for it")
        mw = MEDIUM_WORDS.get(s["medium"])
        if mw and re.search(mw, text):
            sc += 0.6
        m = metrics or {}
        if s["medium"] == "2d-lineart" and m.get("white_ratio", 0) > 0.45 and m.get("saturation", 1) < 0.18:
            sc += 0.9
            why.append("the reference is mostly white with dark lines")
        if s["medium"] == "2d-pixel" and m.get("colour_bins", 999) < 70 and m.get("edge_density", 0) > 0.08:
            sc += 0.7
            why.append("few colours and hard edges, like pixel art")
        if s["medium"] == "2d-painted" and m.get("texture", 0) > 900 and m.get("saturation", 0) < 0.45:
            sc += 0.4
            why.append("soft, textured colour like paint")
        if s["medium"] == "2d-vector" and m.get("saturation", 0) > 0.4:
            sc += 0.25
            why.append("bright flat colours")
        audio = (report or {}).get("audio") or {}
        if s["name"] in ("music-kinetic", "painted-story-mv") and audio.get("bpm") and not audio.get("silent"):
            sc += 0.2
            why.append("music drives the cut")
        pacing = (report or {}).get("pacing") or {}
        if s["name"] == "narrated-comic-vlog" and (pacing.get("mean_shot_s") or 9) < 3.2:
            sc += 0.15
        scores.append((sc, s, why))
    scores.sort(key=lambda x: -x[0])
    best, s, why = scores[0]
    second = scores[1][0] if len(scores) > 1 else 0
    conf = max(0.35, min(0.95, 0.5 + (best - second) * 0.4))
    alts = [{"style": x[1]["name"], "why": "; ".join(x[2]) or f"priority {x[1]['priority']}"} for x in scores[1:3]]
    return s, round(conf, 2), why or [f"closest match among the installed 2D styles (priority {s['priority']})"], alts
