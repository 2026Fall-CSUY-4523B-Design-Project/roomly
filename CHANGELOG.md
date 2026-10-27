# Changelog

All notable changes to this project are documented here, following [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

### Changed
- Node 20 -> 24 (`frontend/.nvmrc`, `engines.node >=24`); CI actions bumped to their Node 24 majors (checkout v7, setup-node v7, pnpm/action-setup v6, setup-uv v10, ssh-agent v0.10).

### Added
- Monorepo skeleton: `backend/` (fastapi-reborn app with `/health`, pytest), `frontend/` (Next.js 12 + React 17, `/api/*` rewritten to the backend), `db/` (migrations), `docs/`.
- `packages/fastapi-reborn` as a git submodule pinned to v0.1.0; backend consumes it as an editable path dependency.
- `script/backend.sh`, `script/frontend.sh`, `script/database.sh` (foreground local Postgres in `db/data`, port 5433).
- Frontend build config: `next.config.js`, `jsconfig.json`, `.npmrc`, `.nvmrc`, `.env.example`; `dev`/`build` set `--openssl-legacy-provider` because Next 12.0.0's webpack 5 uses MD4 hashing, unsupported on Node 17+.
- Root `.gitignore`.
- dev/prod configuration: `roomly.config.Settings` driven by `ROOMLY_ENV` (prod binds 0.0.0.0, INFO logs, requires `DATABASE_URL`); `script/backend.sh prod`; `.env.example`.
- `script/run.sh [--dev|--prod]`: runs the whole stack with per-service log prefixes. `--dev` (default): local Postgres + backend + frontend dev, waits for Postgres before starting the backend; `--prod`: backend prod + frontend build/start against an external DB (`DATABASE_URL` required). Ctrl-C stops all (bash 3.2 compatible).
- `script/release.sh`: builds backend + fastapi-reborn wheels and a frontend tarball into `dist/`.
- GitHub Actions: `ci.yml` (backend lint+test, frontend build) and `release.yml` (tag `v*` -> tests, release.sh, GitHub Release with artifacts). Private submodule is cloned over SSH with a read-only deploy key (`SUBMODULE_SSH_KEY` secret).
