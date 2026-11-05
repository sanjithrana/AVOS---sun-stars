#!/usr/bin/env bash
# Restart the ReelMimic server. Jobs cut off mid-turn are marked "interrupted" at startup and can be resumed (重試).
cd "$(dirname "$0")/.."
LOG="${TMPDIR:-${TEMP:-/tmp}}/reelmimic.log"
# refuse while an agent is working (a restart cuts its turn off) unless --force
if [ "$1" != "--force" ]; then
  BUSY=$(curl -s -m 2 localhost:${PORT:-4318}/api/projects | node -e "let s='';process.stdin.on('data',d=>s+=d).on('end',()=>{try{const W=['analyzing','styling','planning','replanning','producing','revising','critiquing'];console.log(JSON.parse(s).filter(p=>W.includes(p.stage)).map(p=>p.id+'('+p.stage+')').join(' '))}catch{}})")
  if [ -n "$BUSY" ]; then echo "not restarting — still working: $BUSY  (use --force to restart anyway)"; exit 2; fi
fi
# stop only the server on this port (other checkouts / ports keep running), together with the agents it started
P=${PORT:-4318}
if command -v powershell >/dev/null 2>&1; then
  powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort $P -State Listen -ErrorAction SilentlyContinue | % { taskkill /PID \$_.OwningProcess /T /F }" >/dev/null 2>&1 || true
elif command -v lsof >/dev/null 2>&1; then
  lsof -ti tcp:$P -sTCP:LISTEN | xargs kill 2>/dev/null || true
else
  fuser -k $P/tcp 2>/dev/null || true
fi
sleep 2
nohup node app/server/index.ts > "$LOG" 2>&1 &
for i in $(seq 1 20); do curl -s -m 1 localhost:${PORT:-4318}/api/config >/dev/null && { echo "server up"; exit 0; }; sleep 0.5; done
echo "server did not start"; tail -20 "$LOG"; exit 1
