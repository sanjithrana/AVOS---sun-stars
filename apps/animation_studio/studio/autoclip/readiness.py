"""A quick "is everything ready?" check before a run: the things that fail late and confusingly (a missing ffmpeg filter, no disk space, Ollama not running,
a YouTube login that expired) are tried now, each in a second or two, and reported with what to do. Nothing here changes anything."""
from __future__ import annotations

import importlib.util as iu
import shutil
import subprocess
from typing import Any

import httpx

from . import polish, store, youtube


def _row(id: str, label: str, status: str, detail: str = "", fix: str = "") -> dict:
    return {"id": id, "label": label, "status": status, "detail": detail, "fix": fix}


def _ffmpeg() -> list[dict]:
    from .. import config
    try:
        exe = config.ffmpeg()
        out = subprocess.run([exe, "-hide_banner", "-filters"], capture_output=True, text=True, timeout=20).stdout
    except Exception as e:  # noqa: BLE001
        return [_row("ffmpeg", "ffmpeg", "fail", str(e)[:120], "Rebuild the studio container (docker compose up -d --build animation-studio).")]
    need = {"subtitles": "captions", "sidechaincompress": "music ducking", "rgbashift": "glitch effect", "colorbalance": "colour looks", "loudnorm": "loudness"}
    miss = [f"{k} ({v})" for k, v in need.items() if f" {k} " not in out]
    if miss:
        return [_row("ffmpeg", "ffmpeg", "warn", "Missing: " + ", ".join(miss), "Use the studio's own container image: its ffmpeg has all of these.")]
    return [_row("ffmpeg", "ffmpeg", "ok", "All the filters the editor uses are present.")]


def _files() -> list[dict]:
    from .. import config
    rows = []
    free = shutil.disk_usage(store.ROOT if store.ROOT.exists() else ".").free / 1e9
    rows.append(_row("disk", "Disk space", "ok" if free >= 3 else "warn" if free >= 1 else "fail", f"{free:.1f} GB free", "Free some space: a long video needs a few GB while it is cut." if free < 3 else ""))
    from .stickers import FONT
    rows.append(_row("font", "Callout font", "ok" if FONT.is_file() else "fail", "" if FONT.is_file() else "Poppins-Bold.ttf is missing", "Reinstall the latest update zip."))
    rows.append(_row("music", "Built-in music", "ok", "Loops are written on first use."))
    return rows


def _tools() -> list[dict]:
    from . import intake, reframe
    rows = [_row("ytdlp", "Downloader (yt-dlp)", "ok" if intake.have_ytdlp() else "warn", "" if intake.have_ytdlp() else "Not installed: only uploads work.", "pip install yt-dlp inside the studio container (the image has it).")]
    w = iu.find_spec("faster_whisper") is not None
    rows.append(_row("whisper", "Captions (faster-whisper)", "ok" if w else "warn", "" if w else "Not installed: clips get no captions unless the video has subtitles.", "Add faster-whisper to the studio image."))
    rs = reframe.status()
    rows.append(_row("reframe", "AI Reframe (faces)", "ok" if rs.get("ready") else "warn", "" if rs.get("ready") else "Face tracking is not ready; clips use the blurred layout.", rs.get("fix") or ""))
    return rows


def _ai() -> list[dict]:
    from ..llm import ollama_url
    crew = store.settings()["defaults"].get("crew") or "builtin"
    rows = []
    if crew == "builtin":
        rows.append(_row("ai", "AI helper", "warn", "The built-in crew is selected: moments are picked by loudness and rules, with no AI titles or ranking.", "Pick Ollama or a paid helper in Make clips."))
    else:
        rows.append(_row("ai", "AI helper", "ok", f"Crew: {crew}"))
    try:
        r = httpx.get(ollama_url() + "/api/tags", timeout=3)
        n = len((r.json() or {}).get("models") or []) if r.status_code == 200 else 0
        rows.append(_row("ollama", "Ollama", "ok" if n else "warn", f"{n} model(s) installed" if r.status_code == 200 else f"Answered with {r.status_code}",
                         "" if n else "Run: ollama pull qwen2.5:7b"))
    except Exception:  # noqa: BLE001
        rows.append(_row("ollama", "Ollama", "ok" if crew not in ("ollama", "local") else "fail", "Not running (fine if you use a paid helper)." if crew not in ("ollama", "local") else "Not reachable but selected as the crew.",
                         "" if crew not in ("ollama", "local") else "Start Ollama on this PC (and allow the container to reach it)."))
    return rows


NEED = {"upload": "youtube.upload", "analytics": "yt-analytics.readonly", "comments": "youtube.force-ssl"}


def _youtube() -> list[dict]:
    rows = []
    if not youtube.has_client():
        return [_row("yt", "YouTube", "warn", "Not connected: no Google client saved.", "Open the YouTube tab and follow the 4 steps.")]
    chans = (store.accounts().get("channels") or {}).values()
    if not chans:
        return [_row("yt", "YouTube", "warn", "No channel connected yet.", "Connect a channel on the YouTube tab.")]
    for c in chans:
        sc = c.get("scopes") or ""
        label = f"YouTube: {c.get('title')}"
        try:
            youtube.token(c["id"])
        except Exception as e:  # noqa: BLE001
            rows.append(_row("yt-" + c["id"], label, "fail", str(e)[:140], "Connect the channel again on the YouTube tab (publish the Google app so logins don't expire)."))
            continue
        miss = [k for k, s in NEED.items() if s not in sc]
        if miss:
            rows.append(_row("yt-" + c["id"], label, "warn", "Connected, but it was authorised before: " + ", ".join(miss) + " are not allowed yet.",
                             "Disconnect and connect it again to unlock retention learning and comments."))
        else:
            rows.append(_row("yt-" + c["id"], label, "ok", "Login works; upload, numbers and comments are allowed."))
    return rows


def run() -> dict:
    rows: list[dict] = []
    for fn in (_ffmpeg, _files, _tools, _ai, _youtube):
        try:
            rows += fn()
        except Exception as e:  # noqa: BLE001 - a broken check is reported, never fatal
            rows.append(_row(fn.__name__, fn.__name__.strip("_"), "warn", "Could not check: " + str(e)[:120]))
    order = {"fail": 0, "warn": 1, "ok": 2}
    worst = min((order[r["status"]] for r in rows), default=2)
    return {"ok": worst == 2, "blocking": worst == 0, "rows": rows, "at": store.now(), "edit_styles": list(polish.STYLES)}
