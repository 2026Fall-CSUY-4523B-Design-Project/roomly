# Changelog

All notable changes to this project are documented here, following [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

### Added
- Database schema, 21 tables, in two dialects: `db/migrations/postgres/0001_init.sql` and `db/migrations/sqlite/0001_init.sql`. Unknown values are NULL and money is integer cents. The database itself enforces the SSDS invariants: at most six members per group, administrators never members, one owner, at most three commute destinations, searchable listings in scope (R-2.1), closed polls reject votes, one reaction and one vote per member, one notification per event, and retried fetches not stored twice.
- PostgreSQL as the primary database with a SQLite fallback. When `DATABASE_URL` is unreachable at startup, the backend logs a warning and runs on `ROOMLY_SQLITE_FALLBACK` (`db/roomly.sqlite3` in dev, off in prod). `DATABASE_URL=sqlite:///...` runs on SQLite only, and `/health` reports the engine in use.
- Migration runner: applies each file once and records it in `schema_migration`, under an advisory lock on Postgres or `BEGIN IMMEDIATE` on SQLite. It runs on server start and from `script/backend.sh migrate`.
- Backend skeleton for the eight SSDS use cases (§8.1.2.1–8):
  - DTOs with declarative validation and FastAPI-style 422 errors;
  - controllers declaring all 56 endpoints, with OpenAPI request/response schemas;
  - hand-written SQL mappers and one entity per table;
  - service classes as stubs: every method raises `NotImplementedError`, answered with HTTP 501.
  See `docs/backend.md` for the endpoint map, traceability and the to-do list.
- Frontend directory skeleton: `components/`, `lib/`, `styles/`, `public/` next to `pages/`.
- Backend tests for DTO validation, DDL invariants (on both Postgres and SQLite) and fallback selection.
- `docs/backend.md`.
- Monorepo skeleton: `backend/` (fastapi-reborn app with `/health`, pytest), `frontend/` (Next.js 12 + React 17, `/api/*` rewritten to the backend), `db/` (migrations), `docs/`.
- `packages/fastapi-reborn` as a git submodule pinned to v0.1.0; backend consumes it as an editable path dependency.
- `script/backend.sh`, `script/frontend.sh`, `script/database.sh` (foreground local Postgres in `db/data`, port 5433).
- Frontend build config: `next.config.js`, `jsconfig.json`, `.npmrc`, `.nvmrc`, `.env.example`; `dev`/`build` set `--openssl-legacy-provider` because Next 12.0.0's webpack 5 uses MD4 hashing, unsupported on Node 17+.
- Root `.gitignore`.
- dev/prod configuration: `roomly.config.Settings` driven by `ROOMLY_ENV` (prod binds 0.0.0.0, INFO logs, requires `DATABASE_URL`); `script/backend.sh prod`; `.env.example`.
- `script/run.sh [--dev|--prod]`: runs the whole stack with per-service log prefixes. `--dev` (default): local Postgres + backend + frontend dev, waits for Postgres before starting the backend; `--prod`: backend prod + frontend build/start against an external DB (`DATABASE_URL` required). Ctrl-C stops all (bash 3.2 compatible).
- `script/release.sh`: builds backend + fastapi-reborn wheels and a frontend tarball into `dist/`.
- GitHub Actions: `ci.yml` (backend lint+test, frontend build) and `release.yml` (tag `v*` -> tests, release.sh, GitHub Release with artifacts). Private submodule is cloned over SSH with a read-only deploy key (`SUBMODULE_SSH_KEY` secret).

### Changed
- CI and release start a `postgres:18` service for the backend tests; the release also ships `roomly-db-<v>.tar.gz` (the migrations).
- Backend depends on `psycopg[binary]` and `psycopg-pool`.
- Node 20 -> 24 (`frontend/.nvmrc`, `engines.node >=24`); CI actions bumped to their Node 24 majors (checkout v7, setup-node v7, pnpm/action-setup v6, setup-uv v10, ssh-agent v0.10).
