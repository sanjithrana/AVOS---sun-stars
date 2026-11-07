#!/usr/bin/env bash
# ReelMimic — one-time setup: Python packages, web app, UI build, environment check.
set -e
cd "$(dirname "$0")"
# first command that really runs Python 3.10+ (Windows may have a Store stub named python3)
PY="${PYTHON:-}"
if [ -z "$PY" ]; then
  for c in python3 python py; do
    if "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' >/dev/null 2>&1; then PY="$c"; break; fi
  done
fi
[ -n "$PY" ] || { echo "Python 3.10+ not found. Install it, or set PYTHON=/path/to/python"; exit 1; }
echo "== Python packages ($PY)"; "$PY" -m pip install -r requirements.txt
echo "== Web app"; cd app && npm install && npm run build
echo "== Environment check"; node scripts/doctor.mjs || true
cat <<'MSG'

Next:
  1. Install and log in to at least one AI director:
       Claude Code:  npm i -g @anthropic-ai/claude-code   then run `claude` once to log in
       Codex:        npm i -g @openai/codex               then `codex login`
  2. Optional keys → ~/.reelmimic/secrets.json (see secrets.example.json)
  3. Start: ./start.sh   →  http://localhost:4318
MSG
