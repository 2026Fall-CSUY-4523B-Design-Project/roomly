#!/usr/bin/env bash
# Build release artifacts into dist/. Usage: script/release.sh [version]
#   dist/roomly-<v>-py3-none-any.whl                  backend (FastAPI and the drivers come from PyPI)
#   dist/roomly-frontend-<v>.tar.gz                   Next.js build (.next + package files)
#   dist/roomly-db-<v>.tar.gz                         db/migrations (point ROOMLY_MIGRATIONS_DIR at it)
# On the target host: install the wheel with uv, then in the unpacked frontend
# run `pnpm install --prod && pnpm start`.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VERSION="${1:-$(git -C "$ROOT" describe --tags --always)}"
VERSION="${VERSION#v}"
DIST="$ROOT/dist"
rm -rf "$DIST" && mkdir -p "$DIST"

echo "== backend wheel"
uv build --wheel --out-dir "$DIST" "$ROOT/backend"

echo "== frontend build"
cd "$ROOT/frontend"
pnpm install --frozen-lockfile
NODE_ENV=production pnpm build
tar -czf "$DIST/roomly-frontend-$VERSION.tar.gz" \
  .next package.json pnpm-lock.yaml next.config.js .npmrc \
  $([ -d public ] && echo public)

echo "== database migrations"
tar -czf "$DIST/roomly-db-$VERSION.tar.gz" -C "$ROOT/db" migrations

echo "== artifacts"
ls -lh "$DIST"
