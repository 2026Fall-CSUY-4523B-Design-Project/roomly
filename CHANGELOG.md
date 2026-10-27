# Changelog

All notable changes to this project are documented here, following [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

### Added
- Monorepo skeleton: `backend/` (fastapi-reborn app with `/health`, pytest), `frontend/` (Next.js 12 + React 17, `/api/*` rewritten to the backend), `db/` (migrations), `docs/`.
- `packages/fastapi-reborn` as a git submodule pinned to v0.1.0; backend consumes it as an editable path dependency.
- `script/backend.sh`, `script/frontend.sh`, `script/database.sh` (foreground local Postgres in `db/data`, port 5433).
- Frontend build config: `next.config.js`, `jsconfig.json`, `.npmrc`, `.nvmrc`, `.env.example`; `dev`/`build` set `--openssl-legacy-provider` because Next 12.0.0's webpack 5 uses MD4 hashing, unsupported on Node 17+.
- Root `.gitignore`.
