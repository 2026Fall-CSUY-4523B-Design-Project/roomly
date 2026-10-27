#!/usr/bin/env bash
# Local Postgres for development, run in the foreground (Ctrl-C stops it).
# Data lives in db/data (gitignored). Usage: script/database.sh [start|reset|psql]
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DATA="$ROOT/db/data"
PORT="${ROOMLY_DB_PORT:-5433}"
PG_BIN="$(brew --prefix postgresql@18 2>/dev/null || true)/bin"
[ -x "$PG_BIN/postgres" ] || PG_BIN="$(dirname "$(command -v postgres)")"

case "${1:-start}" in
  start)
    if [ ! -d "$DATA" ]; then
      echo "initdb -> $DATA"
      "$PG_BIN/initdb" -D "$DATA" -U roomly --auth=trust >/dev/null
    fi
    echo "postgres on 127.0.0.1:$PORT (user roomly)"
    exec "$PG_BIN/postgres" -D "$DATA" -p "$PORT" -c listen_addresses=127.0.0.1 -c unix_socket_directories=/tmp
    ;;
  reset)
    read -r -p "Delete $DATA? [y/N] " ans
    [ "$ans" = y ] && trash "$DATA" && echo "removed" ;;
  psql)
    exec "$PG_BIN/psql" -h 127.0.0.1 -p "$PORT" -U roomly postgres ;;
  *) echo "usage: $0 [start|reset|psql]" >&2; exit 2 ;;
esac
