"""Where the kit files live. The shipped copy (assets/) is read-only; a working copy with three.js dropped in is made on first use."""
from __future__ import annotations

import shutil
from pathlib import Path

from .. import config

ASSETS = Path(__file__).resolve().parent / "assets"
THREE = ASSETS / "shared" / "three.min.js"


def runtime_root() -> Path:
    d = config.PROJECTS.parent / "kits_runtime" if config.PROJECTS.name == "projects" else config.PROJECTS / "_kits"
    d.mkdir(parents=True, exist_ok=True)
    return d


def kit_dir(kit: str) -> Path:
    """A writable copy of assets/<kit> (engine/ gets three.min.js so pack.py --offline and the 3D player work with no internet)."""
    src, dst = ASSETS / kit, runtime_root() / kit
    stamp = dst / ".stamp"
    if not stamp.is_file() or stamp.read_text() != str(max(p.stat().st_mtime for p in src.rglob("*") if p.is_file())):
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
        (dst / "engine").mkdir(exist_ok=True)
        shutil.copyfile(THREE, dst / "engine" / "three.min.js")
        stamp.write_text(str(max(p.stat().st_mtime for p in src.rglob("*") if p.is_file())))
    return dst
