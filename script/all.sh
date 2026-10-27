#!/usr/bin/env bash
# Run database + backend + frontend together in dev mode, logs prefixed per service.
# Ctrl-C (or any service exiting) stops everything. Usage: script/all.sh
set -euo pipefail
set -m  # each service gets its own process group, so we can kill its whole tree
DIR="$(cd "$(dirname "$0")" && pwd)"
DB_PORT="${ROOMLY_DB_PORT:-5433}"
PIDS=()

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

run db database.sh start
for _ in $(seq 60); do nc -z 127.0.0.1 "$DB_PORT" 2>/dev/null && break; sleep 0.5; done
nc -z 127.0.0.1 "$DB_PORT" 2>/dev/null || { echo "[all] postgres did not come up on :$DB_PORT" >&2; exit 1; }

run backend  backend.sh dev
run frontend frontend.sh dev

# bash 3.2 (macOS) has no `wait -n`: poll until any service dies.
while :; do
  for p in "${PIDS[@]}"; do
    kill -0 "$p" 2>/dev/null || { echo "[all] a service exited, shutting down" >&2; exit 1; }
  done
  sleep 1
done
