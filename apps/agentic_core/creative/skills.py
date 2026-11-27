"""AVOS skills: one SKILL.md per agent role (apps/skills/<name>/SKILL.md). The agents read them as their instructions,
so changing how AVOS writes, directs or checks is editing a Markdown file, not code.

    ---
    name: avos-scene-director
    description: Turns each beat into a shot: scene graph (who stands where, camera) + motion blueprint (what moves when)
    used_by: Series → render a part (DoP)
    ---
    # Scene director
    ...the craft rules...

load("avos-scene-director") returns the body (fallback text when the file is missing); catalog() lists them all.
The output JSON schema stays in code, so an edited skill can change the craft but never break the pipeline.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

FRONT = re.compile(r"^---\s*\n(.*?)\n---\s*\n?", re.S)


def skills_dir() -> Path | None:
    env = os.environ.get("AVOS_SKILLS_DIR")
    if env and Path(env).is_dir():
        return Path(env)
    here = Path(__file__).resolve()
    for p in here.parents:
        cand = p / "skills"
        if cand.is_dir() and any(cand.glob("*/SKILL.md")):
            return cand
    return None


def _parse(text: str) -> tuple[dict[str, str], str]:
    m = FRONT.match(text)
    meta: dict[str, str] = {}
    if m:
        for line in m.group(1).splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                v = v.strip()
                if len(v) > 1 and v[0] == v[-1] and v[0] in "\"'":     # a quoted value, as some SKILL.md files write it
                    v = v[1:-1].strip()
                meta[k.strip()] = v
        text = text[m.end():]
    return meta, text.strip()


def load(name: str, default: str = "") -> str:
    d = skills_dir()
    p = d / name / "SKILL.md" if d else None
    if p and p.is_file():
        try:
            return _parse(p.read_text("utf-8"))[1] or default
        except OSError:
            return default
    return default


def catalog() -> list[dict[str, Any]]:
    """Every SKILL.md under apps/skills, one or two folders deep.

    Nested because vendored collections keep their skills in folders of their own
    (skills/animation-skills/skills/graph/SKILL.md), and those are instruction files like any other -- leaving them out
    of the list only makes them invisible, not absent. Three folders deep is the limit, and the folders a package
    manager fills are skipped, so one stray node_modules cannot turn the list into thousands of rows.
    """
    d = skills_dir()
    out, seen = [], set()
    skip = {"node_modules", "vendor", ".git", "__pycache__", ".next", "dist", "build"}
    found = [p for p in d.rglob("SKILL.md")
             if len(p.parent.relative_to(d).parts) <= 3 and not (skip & set(p.relative_to(d).parts))] if d else []
    for p in sorted(found):
        if p in seen:
            continue
        seen.add(p)
        try:
            meta, body = _parse(p.read_text("utf-8"))
        except OSError:
            continue
        rel = p.parent.relative_to(d)
        out.append({"name": meta.get("name") or p.parent.name, "description": meta.get("description", ""),
                    "used_by": meta.get("used_by", ""), "path": str(p), "chars": len(body),
                    "folder": str(rel).replace("\\", "/")})
    return out
