#!/usr/bin/env bash
# Run the Roomly API (fastapi-reborn). Usage: script/backend.sh [dev|prod|test|lint]
# prod needs DATABASE_URL in the environment.
set -euo pipefail
cd "$(dirname "$0")/../backend"

case "${1:-dev}" in
  dev)  uv sync --quiet && exec uv run python -m roomly.main ;;
  prod) uv sync --quiet --frozen --no-dev && ROOMLY_ENV=prod exec uv run --frozen --no-dev python -m roomly.main ;;
  test) uv sync --quiet && exec uv run pytest -q ;;
  lint) uv sync --quiet && exec uv run ruff check src tests ;;
  *)    echo "usage: $0 [dev|prod|test|lint]" >&2; exit 2 ;;
esac
