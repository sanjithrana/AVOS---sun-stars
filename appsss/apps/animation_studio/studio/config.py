"""Paths, settings and the secrets file.

The ReelMimic repo (apps/reelmimic) is used as-is: its style registry
(.claude/skills/video-clone/styles/*.md), its analysis/lyrics/asset scripts
and its file contract. Projects live in their own folder.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import threading
from pathlib import Path

HERE = Path(__file__).resolve().parent
SERVICE_ROOT = HERE.parent


def _repo() -> Path:
    env = os.environ.get("REELMIMIC_ROOT")
    if env:
        return Path(env).resolve()
    for cand in (SERVICE_ROOT.parent / "reelmimic", SERVICE_ROOT / "reelmimic", Path("/app/reelmimic")):
        if (cand / ".claude" / "skills" / "video-clone").is_dir():
            return cand.resolve()
    return (SERVICE_ROOT.parent / "reelmimic").resolve()


REPO = _repo()                      # the full ReelMimic repo (optional: engine SKILL.md snapshots)
SKILLS = REPO / ".claude" / "skills"
SKILL = SKILLS / "video-clone"
VENDOR = SERVICE_ROOT / "reelmimic_assets"   # ReelMimic's scripts, styles and caption fonts (see NOTICE.md)
SCRIPTS = VENDOR / "scripts" if (VENDOR / "scripts" / "analyze.py").exists() else SKILL / "scripts"
STYLES = Path(os.environ.get("STUDIO_STYLES") or (VENDOR / "styles" if (VENDOR / "styles").is_dir() else SKILL / "styles"))
FONTS_DIR = VENDOR / "fonts" if (VENDOR / "fonts").is_dir() else SKILLS / "embedded-captions" / "modes" / "standard" / "fonts" / "files"
WORK_DIR = REPO if REPO.is_dir() else SERVICE_ROOT
PROJECTS = Path(os.environ.get("STUDIO_PROJECTS") or (SERVICE_ROOT / "projects")).resolve()
PY = os.environ.get("PYTHON") or sys.executable
PORT = int(os.environ.get("PORT") or os.environ.get("STUDIO_PORT") or 8020)

# ---------- secrets / settings (shared format with ReelMimic's ~/.reelmimic/secrets.json) ----------
SECRETS_PATH = Path(os.environ.get("STUDIO_SECRETS") or os.environ.get("REELMIMIC_SECRETS")
                    or (Path.home() / ".reelmimic" / "secrets.json"))
_lock = threading.Lock()


def load_secrets() -> dict:
    try:
        return json.loads(SECRETS_PATH.read_text("utf-8"))
    except Exception:
        return {}


def save_secrets(update: dict) -> dict:
    """Merge `update` into the secrets file (None / "" removes a key) and into os.environ."""
    with _lock:
        cur = load_secrets()
        for k, v in update.items():
            if v is None or v == "":
                cur.pop(k, None)
                os.environ.pop(k, None)
            else:
                cur[k] = v
                os.environ[k] = str(v)
        SECRETS_PATH.parent.mkdir(parents=True, exist_ok=True)
        SECRETS_PATH.write_text(json.dumps(cur, indent=1, ensure_ascii=False), "utf-8")
        return cur


def forget_secrets(names) -> None:
    """Remove names from the studio's own secrets file only (they now live in the shared AVOS settings)."""
    with _lock:
        cur = load_secrets()
        if any(n in cur for n in names):
            for n in names:
                cur.pop(n, None)
            SECRETS_PATH.write_text(json.dumps(cur, indent=1, ensure_ascii=False), "utf-8")


def apply_secrets() -> None:
    """Values from the secrets file fill in environment variables that aren't set (real env wins)."""
    for k, v in load_secrets().items():
        if v is not None and not os.environ.get(k):   # an empty variable (e.g. from docker compose) counts as unset
            os.environ[k] = str(v)
    if os.environ.get("FFMPEG_DIR"):
        os.environ["PATH"] = os.environ["FFMPEG_DIR"] + os.pathsep + os.environ.get("PATH", "")


apply_secrets()


def _apply_shared() -> None:
    """Keys, GPU server and models saved on the AVOS Settings page (shared with Facts) win over the above."""
    from . import avos_settings
    avos_settings.apply()


_apply_shared()


def env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name) or default)
    except ValueError:
        return default


CONFIG = {
    "builders": env_int("BUILDERS", 4),           # parallel shot builders per project
    "castRounds": env_int("CAST_ROUNDS", 3),
    "chunkRounds": env_int("CHUNK_ROUNDS", 3),
    "finalRounds": env_int("FINAL_ROUNDS", 2),
    "maxAgentsGlobal": env_int("MAX_AGENTS", 8),  # all projects together (local model / CPU)
}
ROUND_KEYS = ("castRounds", "chunkRounds", "finalRounds")
ROUND_RANGE = {"min": 1, "max": 10}


def render_settings() -> dict:
    q = os.environ.get("STUDIO_QUALITY", "720p")
    img = os.environ.get("STUDIO_IMAGES", "ai")      # AI pictures by default (free chain always works); "drawn" only if you pick it
    return {"quality": q if q in ("720p", "1080p") else "720p", "images": img if img in ("drawn", "ai") else "ai"}


def ffmpeg() -> str:
    return shutil.which("ffmpeg") or "ffmpeg"


def ffprobe() -> str:
    return shutil.which("ffprobe") or "ffprobe"
