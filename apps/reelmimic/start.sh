#!/usr/bin/env bash
# ReelMimic — build the UI if needed and start the server on http://localhost:4318
set -e
cd "$(dirname "$0")/app"
[ -d node_modules ] || npm install
[ -d dist ] || npm run build
( sleep 2; (command -v xdg-open >/dev/null && xdg-open http://localhost:4318) || (command -v open >/dev/null && open http://localhost:4318) || true ) &
exec node server/index.ts
