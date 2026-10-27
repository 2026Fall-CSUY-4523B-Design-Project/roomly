#!/usr/bin/env bash
# Run the whole stack with per-service log prefixes. Usage: script/run.sh [--dev|--prod]
#   --dev  (default) local Postgres + backend dev + frontend dev
#   --prod backend prod + frontend build/start; Postgres is external, DATABASE_URL required
# Ctrl-C (or any service exiting) stops everything.
set -euo pipefail
set -m  # each service gets its own process group, so we can kill its whole tree
DIR="$(cd "$(dirname "$0")" && pwd)"
DB_PORT="${ROOMLY_DB_PORT:-5433}"
PIDS=()

MODE=dev
case "${1:---dev}" in
  --dev)  MODE=dev ;;
  --prod) MODE=prod ;;
  *) echo "usage: $0 [--dev|--prod]" >&2; exit 2 ;;
esac

cleanup() {
  trap - INT TERM EXIT
  local p
  for p in ${PIDS[@]+"${PIDS[@]}"}; do kill -TERM -- "-$p" 2>/dev/null || true; done
  wait 2>/dev/null || true
}
trap 'exit 130' INT TERM
trap cleanup EXIT

run() { # run <name> <script> [args...]
  local name="$1"; shift
  "$DIR/$1" "${@:2}" > >(awk -v p="[$name]" '{ print p " " $0; fflush() }') 2>&1 &
  PIDS+=("$!")
}

if [ "$MODE" = dev ]; then
  run db database.sh start
  for _ in $(seq 60); do nc -z 127.0.0.1 "$DB_PORT" 2>/dev/null && break; sleep 0.5; done
  nc -z 127.0.0.1 "$DB_PORT" 2>/dev/null || { echo "[all] postgres did not come up on :$DB_PORT" >&2; exit 1; }
  run backend  backend.sh dev
  run frontend frontend.sh dev
else
  : "${DATABASE_URL:?--prod needs DATABASE_URL in the environment}"
  "$DIR/frontend.sh" build
  run backend  backend.sh prod
  run frontend frontend.sh start
fi

# bash 3.2 (macOS) has no `wait -n`: poll until any service dies.
while :; do
  for p in "${PIDS[@]}"; do
    kill -0 "$p" 2>/dev/null || { echo "[all] a service exited, shutting down" >&2; exit 1; }
  done
  sleep 1
done
