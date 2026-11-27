"""Test setup: every run gets its own projects folder and secrets file (set before `studio` is imported)."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

_TMP = Path(tempfile.mkdtemp(prefix="avos-studio-tests-"))
os.environ["STUDIO_PROJECTS"] = str(_TMP / "projects")
os.environ["STUDIO_SECRETS"] = str(_TMP / "secrets.json")
os.environ["STUDIO_FONT_CACHE"] = str(_TMP / "fonts")
os.environ["FAKE_OLLAMA_LOG"] = str(_TMP / "fake_ollama.log")
os.environ["COMFYUI_WORKFLOW_DIR"] = str(_TMP / "comfyui_workflows")
os.environ["AVOS_SETTINGS_FILE"] = str(_TMP / "avos_settings.json")
for k in ("OLLAMA_URL", "STUDIO_OLLAMA_MODEL", "STUDIO_OLLAMA_VISION_MODEL", "STUDIO_DEFAULT_AGENT", "GROQ_API_KEY",
          "FAL_KEY", "COMFYUI_URL", "MODEL_BACKEND", "STUDIO_IMAGE_MODEL", "STUDIO_IMAGES",
          "CLOUDFLARE_ACCOUNT_ID", "CLOUDFLARE_API_TOKEN", "IMAGE_SERVICE_URL",
          "GEMINI_API_KEY", "OPENROUTER_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
    os.environ.pop(k, None)
# The writer is picked automatically from saved keys (llm.auto_agent); a test that saves a Groq key must not turn every
# later test into a call to Groq, so the suite pins the old default. test_setup.py unsets it to test the automatic pick.
os.environ["STUDIO_DEFAULT_AGENT"] = "ollama"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

needs_ffmpeg = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="FFmpeg is not installed")


@pytest.fixture(scope="session")
def reference_video() -> Path:
    """A 9-second reference: three visibly different shots and a tone."""
    if not shutil.which("ffmpeg"):
        pytest.skip("FFmpeg is not installed")
    out = _TMP / "reference.mp4"
    if not out.exists():
        subprocess.run(["ffmpeg", "-v", "error", "-y",
                        "-f", "lavfi", "-i", "testsrc2=s=640x360:r=24:d=3", "-f", "lavfi", "-i", "smptebars=s=640x360:r=24:d=3",
                        "-f", "lavfi", "-i", "mandelbrot=s=640x360:r=24", "-f", "lavfi", "-i", "sine=f=440:d=9",
                        "-filter_complex", "[2:v]trim=duration=3[m];[0:v][1:v][m]concat=n=3:v=1:a=0[v]",
                        "-map", "[v]", "-map", "3:a", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-shortest", str(out)], check=True)
    return out


@pytest.fixture(autouse=True)
def _no_web_research(monkeypatch):
    """The packaging team's web searches never run in tests (test_research.py fakes them itself)."""
    try:
        from studio.autoclip import research
    except Exception:  # noqa: BLE001
        return
    monkeypatch.setattr(research, "_api_search", lambda q, n: None)
    monkeypatch.setattr(research, "_ytdlp_search", lambda q, n: [])
    monkeypatch.setattr(research, "_details", lambda ids: {})


@pytest.fixture(autouse=True)
def _no_web_comments(monkeypatch):
    """Comment downloads never run in tests."""
    try:
        from studio.autoclip import signals
    except Exception:  # noqa: BLE001
        return
    monkeypatch.setattr(signals, "comments", lambda url, dest, cancel=None, limit=400: [])


@pytest.fixture(autouse=True)
def _no_web_transcripts(request, monkeypatch):
    """Jobs with YouTube links must not ask YouTube for a transcript during tests (test_yttranscript tests it directly)."""
    if request.module.__name__.endswith("test_yttranscript"):
        return
    try:
        from studio.autoclip import yttranscript
    except Exception:  # noqa: BLE001
        return
    monkeypatch.setattr(yttranscript, "fetch", lambda url, langs=None, log=None: (None, "tests run offline"))
