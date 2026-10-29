#!/usr/bin/env bash
# Run the Roomly API (fastapi-reborn). Usage: script/backend.sh [dev|prod|test|lint|migrate]
# dev/prod apply pending db/migrations before serving; prod needs DATABASE_URL in the environment.
# test needs Postgres (script/database.sh); it uses a throwaway roomly_test database.
set -euo pipefail
cd "$(dirname "$0")/../backend"

case "${1:-dev}" in
  dev)  uv sync --quiet && exec uv run python -m roomly.main ;;
  prod) uv sync --quiet --frozen --no-dev && ROOMLY_ENV=prod exec uv run --frozen --no-dev python -m roomly.main ;;
  test) uv sync --quiet && exec uv run pytest -q ;;
  lint) uv sync --quiet && exec uv run ruff check src tests ;;
  migrate) uv sync --quiet && exec uv run python -m roomly.db ;;
  *)    echo "usage: $0 [dev|prod|test|lint|migrate]" >&2; exit 2 ;;
esac
