#!/usr/bin/env bash
# Fill the development database with demo accounts, groups, listings and activity.
# Usage: script/seed.sh [--reset]   (--reset empties every table except schema_migration)
set -euo pipefail
cd "$(dirname "$0")/../backend"
uv sync --quiet
exec uv run python -m roomly.seed "$@"
