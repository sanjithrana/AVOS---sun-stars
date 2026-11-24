"""The kit render engine: what must be installed, whether it is, and a one-time installer.

The kits draw each frame in a real browser (WebGL / canvas), so the service needs Python Playwright + Chromium, ffmpeg, and
edge-tts for the narration. None of it is bundled; `ensure()` installs what is missing the first time a kit skill runs
(pip, then `playwright install --with-deps chromium`), and `status()` tells the UI what is there.
"""
from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
import threading
from pathlib import Path
from typing import Callable

_lock = threading.Lock()
PIP = ["playwright", "edge-tts"]


def _has(mod: str) -> bool:
    return importlib.util.find_spec(mod) is not None


_chromium_seen = False


def _chromium_ok() -> bool:
    global _chromium_seen
    if _chromium_seen:
        return True
    if not _has("playwright"):
        return False
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            _chromium_seen = Path(p.chromium.executable_path).exists()
            return _chromium_seen
    except Exception:  # noqa: BLE001 - any failure means "not usable yet"
        return False


def status() -> dict:
    ff = bool(shutil.which("ffmpeg"))
    parts = {"ffmpeg": ff, "playwright": _has("playwright"), "edge_tts": _has("edge_tts")}
    parts["chromium"] = parts["playwright"] and _chromium_ok()
    ready = all(parts.values())
    missing = [k for k, v in parts.items() if not v]
    return {"ready": ready, "parts": parts, "missing": missing,
            "fix": "" if ready else ("Opens by itself the first time you run a kit skill (one-time download, about 300 MB). "
                                     "To do it now: docker compose exec animation-studio python -m studio.kits.engine"),
            "note": "Frames are drawn with software WebGL (no GPU needed): expect a few minutes for a short."}


def _run(cmd: list[str], log: Callable[[str], None]) -> None:
    log("$ " + " ".join(cmd))
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
    if r.returncode:
        raise RuntimeError(f"{' '.join(cmd[:4])} failed: {(r.stderr or r.stdout)[-400:]}")


def ensure(log: Callable[[str], None] | None = None) -> None:
    """Install whatever is missing. Safe to call on every run; does nothing once everything is there."""
    log = log or (lambda m: None)
    st = status()
    if st["ready"]:
        return
    with _lock:
        st = status()
        if st["ready"]:
            return
        if not st["parts"]["ffmpeg"]:
            raise RuntimeError("ffmpeg is not installed in the service (the animation-studio image should include it).")
        log("Installing the kit render engine (one time): " + ", ".join(st["missing"]))
        need = [m for m, ok in (("playwright", st["parts"]["playwright"]), ("edge-tts", st["parts"]["edge_tts"])) if not ok]
        if need:
            try:
                _run([sys.executable, "-m", "pip", "install", "-q", *need], log)
            except RuntimeError:
                _run([sys.executable, "-m", "pip", "install", "-q", "--break-system-packages", *need], log)
            importlib.invalidate_caches()
        if not _chromium_ok():
            try:
                _run([sys.executable, "-m", "playwright", "install", "--with-deps", "chromium"], log)
            except RuntimeError:
                _run([sys.executable, "-m", "playwright", "install", "chromium"], log)
        if not status()["ready"]:
            raise RuntimeError("The render engine could not be installed. Run it by hand: "
                               "docker compose exec animation-studio python -m studio.kits.engine")


if __name__ == "__main__":
    ensure(print)
    print(status())
