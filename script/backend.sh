#!/usr/bin/env bash
# Run the Roomly API (fastapi-reborn). Usage: script/backend.sh [dev|test|lint]
set -euo pipefail
cd "$(dirname "$0")/../backend"

case "${1:-dev}" in
  dev)  uv sync --quiet && exec uv run python -m roomly.main ;;
  test) uv sync --quiet && exec uv run pytest -q ;;
  lint) uv sync --quiet && exec uv run ruff check src tests ;;
  *)    echo "usage: $0 [dev|test|lint]" >&2; exit 2 ;;
esac
