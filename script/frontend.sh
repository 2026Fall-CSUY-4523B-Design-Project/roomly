#!/usr/bin/env bash
# Run the Roomly frontend (Next.js). Usage: script/frontend.sh [dev|build|start]
set -euo pipefail
cd "$(dirname "$0")/../frontend"

pnpm install --silent
case "${1:-dev}" in
  dev|build|start) exec pnpm run "${1:-dev}" ;;
  *) echo "usage: $0 [dev|build|start]" >&2; exit 2 ;;
esac
