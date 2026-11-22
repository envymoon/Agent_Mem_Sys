#!/usr/bin/env bash
# Native (no-docker) production backends for the memory systems:
#   Postgres 16 + pgvector (mem0 OSS server default, Letta), Qdrant server, Neo4j 5.26 (Graphiti/Zep).
# Works on Colab (Ubuntu 22.04, root) and in this dev container (Ubuntu 24.04).
#
#   scripts/services.sh install            # one-time: apt/pgdg + qdrant/neo4j tarballs
#   scripts/services.sh start  [pg|qdrant|neo4j|all]
#   scripts/services.sh stop   [pg|qdrant|neo4j|all]
#   scripts/services.sh reset  [pg|qdrant|neo4j|all]   # stop + wipe data (fresh store per run)
#   scripts/services.sh status
#
# Data lives under $SVC_DATA (default /opt/svc/data). On Colab keep it on the VM disk, not on Drive.
set -euo pipefail
SVC_HOME=${SVC_HOME:-/opt/svc}
SVC_DATA=${SVC_DATA:-$SVC_HOME/data}
PG_VER=${PG_VER:-16}
QDRANT_VER=${QDRANT_VER:-1.15.5}
NEO4J_VER=${NEO4J_VER:-5.26.0}
NEO4J_PASSWORD=${NEO4J_PASSWORD:-memprof-neo4j}
PG_PORT=${PG_PORT:-5432}
PGBIN=/usr/lib/postgresql/$PG_VER/bin
LOGS=$SVC_DATA/logs
mkdir -p "$SVC_HOME" "$SVC_DATA" "$LOGS"; chmod 1777 "$LOGS"

install() {
  export DEBIAN_FRONTEND=noninteractive
  if ! apt-cache policy "postgresql-$PG_VER-pgvector" 2>/dev/null | grep -q "Candidate: [0-9]"; then
    apt-get install -y -q curl ca-certificates gnupg lsb-release >/dev/null
    install -d /usr/share/postgresql-common/pgdg
    curl -fsSL -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc \
      https://www.postgresql.org/media/keys/ACCC4CF8.asc
    echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc] https://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" \
      > /etc/apt/sources.list.d/pgdg.list
    apt-get update -q >/dev/null
  fi
  apt-get install -y -q "postgresql-$PG_VER" "postgresql-$PG_VER-pgvector" postgresql-contrib >/dev/null || \
    apt-get install -y -q "postgresql-$PG_VER" "postgresql-$PG_VER-pgvector" >/dev/null
  # Java 21 for Neo4j 5.26
  command -v java >/dev/null && java -version 2>&1 | grep -q '"21\|"17' || apt-get install -y -q openjdk-21-jre-headless >/dev/null \
    || apt-get install -y -q openjdk-17-jre-headless >/dev/null
  cd "$SVC_HOME"
  [ -x qdrant ] || { curl -fsSL -o qdrant.tgz "https://github.com/qdrant/qdrant/releases/download/v$QDRANT_VER/qdrant-x86_64-unknown-linux-gnu.tar.gz" && tar xzf qdrant.tgz && rm qdrant.tgz; }
  [ -d "neo4j-community-$NEO4J_VER" ] || { curl -fsSL -o neo4j.tgz "https://dist.neo4j.org/neo4j-community-$NEO4J_VER-unix.tar.gz" && tar xzf neo4j.tgz && rm neo4j.tgz; }
  echo "install ok: pg=$PG_VER qdrant=$QDRANT_VER neo4j=$NEO4J_VER"
}

wait_port() { for _ in $(seq 1 120); do (echo >/dev/tcp/127.0.0.1/"$1") 2>/dev/null && return 0; sleep 0.5; done; echo "port $1 not up"; return 1; }

start_pg() {
  local D=$SVC_DATA/pg
  if [ ! -f "$D/PG_VERSION" ]; then
    mkdir -p "$D" && chown -R postgres:postgres "$D"
    su postgres -c "$PGBIN/initdb -D $D -A trust -E UTF8" >"$LOGS/pg_init.log"
    # Production-ish defaults: durable commits (fsync/synchronous_commit on), larger buffers, stats.
    cat >>"$D/postgresql.conf" <<EOF
port = $PG_PORT
listen_addresses = '127.0.0.1'
unix_socket_directories = '/tmp'
shared_buffers = '2GB'
work_mem = '64MB'
maintenance_work_mem = '1GB'
effective_cache_size = '8GB'
max_connections = 200
shared_preload_libraries = 'pg_stat_statements'
pg_stat_statements.track = all
track_io_timing = on
EOF
  fi
  su postgres -c "$PGBIN/pg_ctl -D $D -l $LOGS/pg.log -w start" >/dev/null 2>&1 </dev/null
  psql -h 127.0.0.1 -p "$PG_PORT" -U postgres -tAc "SELECT 1 FROM pg_database WHERE datname='memprof'" | grep -q 1 || \
    psql -h 127.0.0.1 -p "$PG_PORT" -U postgres -qc "CREATE DATABASE memprof"
  psql -h 127.0.0.1 -p "$PG_PORT" -U postgres -d memprof -qc "CREATE EXTENSION IF NOT EXISTS vector; CREATE EXTENSION IF NOT EXISTS pg_stat_statements;"
  echo "pg up :$PG_PORT (db memprof, user postgres, trust auth)"
}
stop_pg() { [ -f "$SVC_DATA/pg/postmaster.pid" ] && su postgres -c "$PGBIN/pg_ctl -D $SVC_DATA/pg -m fast stop" >/dev/null || true; }

start_qdrant() {
  mkdir -p "$SVC_DATA/qdrant"
  ( cd "$SVC_DATA/qdrant" && QDRANT__STORAGE__STORAGE_PATH="$SVC_DATA/qdrant/storage" \
    QDRANT__STORAGE__SNAPSHOTS_PATH="$SVC_DATA/qdrant/snapshots" QDRANT__TELEMETRY_DISABLED=true \
    QDRANT__SERVICE__HOST=127.0.0.1 QDRANT__SERVICE__HTTP_PORT=6333 QDRANT__SERVICE__GRPC_PORT=6334 \
    nohup "$SVC_HOME/qdrant" >"$LOGS/qdrant.log" 2>&1 </dev/null & echo $! >"$SVC_DATA/qdrant.pid" )
  wait_port 6333 && echo "qdrant up :6333"
}
stop_qdrant() { pkill -f "$SVC_HOME/qdrant" 2>/dev/null; rm -f "$SVC_DATA/qdrant.pid"; sleep 1; }

start_neo4j() {
  local N=$SVC_HOME/neo4j-community-$NEO4J_VER
  export NEO4J_HOME=$N NEO4J_CONF=$SVC_DATA/neo4j/conf
  if [ ! -d "$NEO4J_CONF" ]; then
    mkdir -p "$NEO4J_CONF" "$SVC_DATA/neo4j/data" "$SVC_DATA/neo4j/logs"
    cp "$N/conf/"* "$NEO4J_CONF/"
    cat >>"$NEO4J_CONF/neo4j.conf" <<EOF
server.directories.data=$SVC_DATA/neo4j/data
server.directories.logs=$SVC_DATA/neo4j/logs
server.default_listen_address=127.0.0.1
server.bolt.listen_address=127.0.0.1:7687
server.http.listen_address=127.0.0.1:7474
server.memory.heap.initial_size=${NEO4J_HEAP:-2g}
server.memory.heap.max_size=${NEO4J_HEAP:-2g}
server.memory.pagecache.size=${NEO4J_PAGECACHE:-2g}
db.logs.query.enabled=INFO
db.logs.query.threshold=0
EOF
    "$N/bin/neo4j-admin" dbms set-initial-password "$NEO4J_PASSWORD" >/dev/null 2>&1 || true
  fi
  "$N/bin/neo4j" start >"$LOGS/neo4j_start.log" 2>&1
  wait_port 7687 && echo "neo4j up :7687 (neo4j/$NEO4J_PASSWORD)"
}
stop_neo4j() { local N=$SVC_HOME/neo4j-community-$NEO4J_VER; NEO4J_CONF=$SVC_DATA/neo4j/conf NEO4J_HOME=$N "$N/bin/neo4j" stop >/dev/null 2>&1 || true; }

each() { local act=$1 what=${2:-all}; for s in pg qdrant neo4j; do [ "$what" = all ] || [ "$what" = "$s" ] && "${act}_$s"; done; return 0; }
cmd=${1:-status}; what=${2:-all}
case $cmd in
  install) install ;;
  start) each start "$what" ;;
  stop) each stop "$what" ;;
  reset) each stop "$what"; for s in pg qdrant neo4j; do { [ "$what" = all ] || [ "$what" = "$s" ]; } && rm -rf "${SVC_DATA:?}/$s"; done; echo "reset $what" ;;
  status) for p in $PG_PORT 6333 7687; do (echo >/dev/tcp/127.0.0.1/$p) 2>/dev/null && echo "port $p up" || echo "port $p down"; done ;;
esac
