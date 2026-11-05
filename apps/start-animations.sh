#!/usr/bin/env bash
# AVOS Animations tab: starts the Animation Studio service (ReelMimic in Python) on http://127.0.0.1:8020
set -e
cd "$(dirname "$0")/animation_studio"
if [ ! -x .venv/bin/python ]; then
  PY=""
  for c in python3.12 python3.11 python3.10 python3; do
    if command -v "$c" >/dev/null && "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)'; then PY="$c"; break; fi
  done
  [ -n "$PY" ] || { echo "Python 3.10+ is needed."; exit 1; }
  "$PY" -m venv .venv
fi
if [ ! -f .venv/installed.txt ]; then
  .venv/bin/python -m pip install --upgrade pip >/dev/null
  .venv/bin/python -m pip install -r requirements.txt
  .venv/bin/python -m pip install -r requirements-lyrics.txt || echo "Lyric timing not installed (optional)."
  echo ok > .venv/installed.txt
fi
command -v ffmpeg >/dev/null || echo "FFmpeg not found: install it (brew install ffmpeg / apt install ffmpeg)."
.venv/bin/python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:11434/api/tags', timeout=2)" 2>/dev/null \
  || echo "Ollama is not running (local AI crew): https://ollama.com, then: ollama pull qwen2.5:7b"
STUDIO_HOST=127.0.0.1 exec .venv/bin/python -m studio
