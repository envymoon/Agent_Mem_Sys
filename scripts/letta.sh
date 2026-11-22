#!/usr/bin/env bash
# Letta server (0.16.8, last release of the server package) on Postgres + pgvector, LLM/embeddings via
# the memprof proxy.
#   scripts/letta.sh setup     # venv (deps pinned to the release date) + alembic migrations from sdist
#   scripts/letta.sh reset     # drop + recreate DB 'letta', run migrations
#   scripts/letta.sh start | stop
set -euo pipefail
cd "$(dirname "$0")/.."
LV=.venv-letta
SRC=${SVC_HOME:-/opt/svc}/letta-src/letta-0.16.8
PG=${MEMPROF_PG_HOSTPORT:-127.0.0.1:5432}
URI=postgresql://postgres@$PG/letta
PROXY=${MEMPROF_PROXY:-http://127.0.0.1:8100/v1}
LOG=${LETTA_LOG:-results/letta_server.log}

setup() {
  command -v uv >/dev/null || pip install -q uv
  [ -x $LV/bin/letta ] || { uv venv -q -p 3.12 $LV; VIRTUAL_ENV=$LV uv pip install -q --exclude-newer 2026-05-15 \
      "letta==0.16.8" asyncpg pgvector psycopg2-binary pg8000; }
  if [ ! -f "$SRC/alembic.ini" ]; then
    mkdir -p "$(dirname "$SRC")"
    curl -fsSL -o /tmp/letta-sdist.tgz \
      https://files.pythonhosted.org/packages/6a/94/b51b0746dd862b86538f10085b57c216ab32e3d40532e45b63afe0925c4c/letta-0.16.8.tar.gz
    tar xzf /tmp/letta-sdist.tgz -C "$(dirname "$SRC")" letta-0.16.8/alembic.ini letta-0.16.8/alembic
  fi
  echo "letta setup ok"
}
reset() {
  stop
  psql -h "${PG%:*}" -p "${PG#*:}" -U postgres -qc "DROP DATABASE IF EXISTS letta" -qc "CREATE DATABASE letta"
  psql -h "${PG%:*}" -p "${PG#*:}" -U postgres -d letta -qc "CREATE EXTENSION IF NOT EXISTS vector"
  (cd "$SRC" && LETTA_PG_URI=$URI "$OLDPWD/$LV/bin/alembic" upgrade head >/dev/null 2>&1)
  echo "letta db reset"
}
start() {
  mkdir -p "$(dirname "$LOG")"
  LETTA_PG_URI=$URI OPENAI_API_BASE=$PROXY OPENAI_API_KEY=sk-local LETTA_TELEMETRY_DISABLED=true \
    nohup $LV/bin/letta server --port 8283 >"$LOG" 2>&1 </dev/null &
  for _ in $(seq 1 120); do curl -sf http://127.0.0.1:8283/v1/health/ >/dev/null && { echo "letta up :8283"; return 0; }; sleep 1; done
  echo "letta failed to start"; tail -20 "$LOG"; return 1
}
stop() { pkill -f "$LV/bin/letta server" 2>/dev/null || true; sleep 1; }
"${1:-start}"
