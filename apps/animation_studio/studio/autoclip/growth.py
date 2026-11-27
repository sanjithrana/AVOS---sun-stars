"""House rules for the words around a clip (title, hook, caption, hashtags), read from Ootto's content skills.

The skills live in apps/skills/content-growth/skills (github.com/Ootto-AI/claude-content-skills, MIT, Copyright (c) 2026
Ootto; Humanizer is bundled there from blader/humanizer, MIT). Each writer gets a short extract, not the whole files:
  - Virality: the eight-point hook checklist (from 262 posts and 3.5M views), trimmed to what fits a clip
  - Viral Hook Writer and Caption & Hashtags: the caption shape, one CTA, tiered hashtags, a question for comments
  - Humanizer: the names of the AI-writing tells to avoid
Edit those SKILL.md files and the writers follow the new text on the next run. When the folder is missing the extract is
empty and the writers keep their own rules."""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

LIMIT = 2600


def folder() -> Path | None:
    from ..creative.skills import skills_dir
    d = skills_dir()
    d = d / "content-growth" / "skills" if d else None
    return d if d and d.is_dir() else None


def _read(name: str) -> str:
    d = folder()
    p = d / name / "SKILL.md" if d else None
    try:
        return p.read_text("utf-8") if p and p.is_file() else ""
    except OSError:
        return ""


def section(text: str, heading: str) -> str:
    """The body under the first heading containing `heading` (any level), up to the next heading of the same or higher level."""
    lines = text.splitlines()
    for i, ln in enumerate(lines):
        m = re.match(r"^(#{1,6})\s+(.*)", ln)
        if m and heading.lower() in m.group(2).lower():
            lvl, out = len(m.group(1)), []
            for nxt in lines[i + 1:]:
                h = re.match(r"^(#{1,6})\s", nxt)
                if h and len(h.group(1)) <= lvl:
                    break
                out.append(nxt)
            return "\n".join(out).strip()
    return ""


def _plain(s: str) -> str:
    s = re.sub(r"\*\*(.+?)\*\*", r"\1", s)
    s = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", s)
    return re.sub(r"\n{3,}", "\n\n", s).strip()


@lru_cache(maxsize=4)
def _rules(stamp: float) -> str:  # noqa: ARG001 - the stamp only invalidates the cache when a file changes
    parts = []
    check = section(_read("virality"), "The checklist")
    if check:
        parts.append("HOOK CHECKLIST (Virality skill; the clip's first 3 seconds and its on-screen hook must pass):\n" + _plain(check))
    cap = _read("caption-and-hashtags")
    if cap:
        parts.append("CAPTION: the first line is a second hook (it is the only line shown before 'more'); then 1-3 short lines of value; "
                     "one clear ask; no hashtag soup in the text; tiered hashtags (a few broad, several mid, several niche); "
                     "end with a question that invites comments.")
    hum = _read("humanizer")
    if hum:
        tells = [re.sub(r"^#+\s*\d+\.\s*", "", ln).strip() for ln in hum.splitlines() if re.match(r"^###\s+\d+\.", ln)]
        if tells:
            parts.append("SOUND HUMAN (Humanizer skill), avoid: " + "; ".join(tells[:24]) + ".")
    out = "\n\n".join(parts)
    return out[:LIMIT]


def rules() -> str:
    """The extract for title, hook and caption writers ('' when the skills are not installed)."""
    d = folder()
    if not d:
        return ""
    try:
        stamp = max((p.stat().st_mtime for n in ("virality", "caption-and-hashtags", "humanizer") for p in [d / n / "SKILL.md"] if p.is_file()), default=0.0)
    except OSError:
        stamp = 0.0
    return _rules(stamp)
