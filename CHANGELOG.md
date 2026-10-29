# Changelog

All notable changes to this project are documented here, following [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

## [2.1.0] - 2026-10-29

First release, matching SSDS-001 v2.1.

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
- Fixture mode (`ROOMLY_FIXTURES`, on in dev): stub endpoints answer with consistent sample responses from `roomly/fixtures.py` (real status codes, `X-Roomly-Fixture: 1`, validation and the bearer check still applied) so the frontend can be built before the logic exists.
- Frontend directory skeleton: `components/`, `lib/`, `styles/`, `public/` next to `pages/`.
- Backend tests for DTO validation, DDL invariants (on both Postgres and SQLite), fallback selection and fixture coverage.
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
- The backend runs on FastAPI (0.162) and pydantic 2, served by uvicorn, instead of fastapi-reborn:
  - DTOs are frozen pydantic models (`dto.base.DTO`). Strings are stripped except `Secret` passwords, request numbers and booleans are strict (`true` is not 1, `"3"` is not 3), `Distinct` rejects repeated list items, and patterns match the whole value. `check()` still reports each cross-field problem at its field.
  - Endpoints declare typed path and query parameters and request DTOs, so FastAPI validates them and documents them in OpenAPI. `Depends` resolves the services and the bearer user. Blocking endpoints are plain `def` and run in FastAPI's thread pool.
  - 422 bodies keep the shape `{"detail": [{"type", "loc", "msg", "input"}]}` and now use pydantic's error types: a non-object body is `model_type`, and a blank poll option or amenity is a `string_too_short` at that item.
  - `/docs` serves Swagger UI and `/redoc` serves ReDoc; `/openapi.json` is unchanged.
  - Tests use FastAPI's `TestClient` (dev dependency `httpx2`).
- CI and release start a `postgres:18` service for the backend tests; the release also ships `roomly-db-<v>.tar.gz` (the migrations).
- Backend depends on `psycopg[binary]` and `psycopg-pool`.
- Node 20 -> 24 (`frontend/.nvmrc`, `engines.node >=24`); CI actions bumped to their Node 24 majors (checkout v7, setup-node v7, pnpm/action-setup v6, setup-uv v10, ssh-agent v0.10).

### Removed
- The `packages/fastapi-reborn` submodule, the `SUBMODULE_SSH_KEY` deploy-key steps in CI and release, and the fastapi-reborn wheel from releases.
- The hand-written validator and JSON Schema generator in `dto/base.py` (`rule`, `parse`, `schema_of`, `body`, `returns`) and the controller helpers that wrapped them (`read`, `run`, `path_uuid`, `query_uuid`, `paging`, `choice`), as well as the `MessageCursor` DTO.
