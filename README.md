# Roomly Mono repo

## About
Roomly is a mono repo that contains multiple packages and applications related to the Roomly project. This repository is structured to facilitate development, testing, and deployment of various components in a unified manner.

## Structure
- Frontend: Node, Next.js 12 pages router
- Backend: Python, fastapi-reborn; layers DTO → controller → service → SQL mapper → entity ([docs/backend.md](docs/backend.md))
- DB: PostgreSQL as primary, SQLite as fallback

```
backend/
  src/roomly/
    controller/   HTTP routers, one per SSDS use case (§8.1.2.1–8)
    service/      SSDS control classes: method stubs (NotImplementedError -> HTTP 501)
    mapper/       hand-written SQL, one mapper per aggregate
    entity/       one dataclass per table
    dto/          request/response bodies with validation rules
    db/           Database (Postgres primary, SQLite fallback), Tx, migrations
  tests/          pytest; database tests run on both engines
frontend/
  pages/          routes (Next.js pages router)
  components/     shared React components
  lib/            client helpers (API calls etc.)
  styles/         CSS
  public/         static files
db/
  migrations/postgres/   NNNN_name.sql, PostgreSQL dialect
  migrations/sqlite/     the same versions in SQLite dialect
  data/                  local Postgres cluster (gitignored)
packages/     git submodules (fastapi-reborn)
script/       run.sh · backend.sh · frontend.sh · database.sh · release.sh
.github/      CI and release workflows
docs/         backend.md
```

## Quick start
```sh
git clone --recurse-submodules <repo>   # or: git submodule update --init
cd roomly
script/run.sh                           # = script/run.sh --dev
```

`fastapi-reborn` is a private submodule cloned over SSH, so your GitHub account needs access to it.

`script/run.sh --dev` starts local Postgres (`127.0.0.1:5433`, data in `db/data`), the backend (`:8000`) and the frontend (`:3000`, `/api/*` is rewritten to the backend). Output is prefixed per service (`[db]`, `[backend]`, `[frontend]`); Ctrl-C stops everything.

`script/run.sh --prod` builds and starts the backend and frontend against an external database; `DATABASE_URL` must be set.

The backend applies pending migrations when it starts. All 56 endpoints are declared with their DTOs; the service methods behind them are stubs (see [docs/backend.md](docs/backend.md#to-do)).

**Fixtures for frontend work.** In dev, a stub answers with a sample response from `backend/src/roomly/fixtures.py` instead of 501. The response has the route's real status code and an `X-Roomly-Fixture: 1` header. Request validation (422) and the bearer check (401: send any token) still apply, so the frontend can be built against the real API shape before the logic exists. Methods that get implemented return real data automatically. `ROOMLY_FIXTURES=off` turns this off; it is off by default in prod.

## Database: PostgreSQL primary, SQLite fallback
- At startup the backend connects to `DATABASE_URL` (PostgreSQL).
- If Postgres is unreachable and a fallback file is configured, it logs a warning and runs on SQLite instead. The fallback is `db/roomly.sqlite3` in dev and off in prod; `ROOMLY_SQLITE_FALLBACK` changes it.
- `DATABASE_URL=sqlite:///path/to/file.sqlite3` runs on SQLite only.
- `GET /health` reports which engine is in use: `{"status": "ok", "database": "postgres"}`.
- The fallback is a separate database: data written to SQLite is not copied back into Postgres.
- Both engines run the same schema and the same invariants, for example at most six members per group, one vote per member and one notification per event. See [docs/backend.md](docs/backend.md#database).

## Scripts
| Script | Usage |
| --- | --- |
| `script/run.sh` | `[--dev\|--prod]` whole stack, see above |
| `script/backend.sh` | `[dev\|prod\|test\|lint\|migrate]` API server, pytest, ruff, apply migrations |
| `script/frontend.sh` | `[dev\|build\|start]` Next.js via pnpm |
| `script/database.sh` | `[start\|reset\|psql]` local Postgres in the foreground (`ROOMLY_DB_PORT` overrides 5433) |
| `script/release.sh` | `[version]` builds wheels, the frontend tarball and the migrations tarball into `dist/` |

## Configuration
Copy [.env.example](.env.example) and export it, or set the variables in your deploy environment.

| Variable | Default | Notes |
| --- | --- | --- |
| `ROOMLY_ENV` | `dev` | `dev` or `prod`; `prod` binds `0.0.0.0`, logs at INFO and requires `DATABASE_URL` |
| `ROOMLY_HOST` / `ROOMLY_PORT` | `127.0.0.1` (`0.0.0.0` in prod) / `8000` | backend bind address |
| `ROOMLY_LOG_LEVEL` | `DEBUG` (`INFO` in prod) | |
| `DATABASE_URL` | `postgresql://roomly@127.0.0.1:5433/postgres` in dev | required in prod; `sqlite:///path` = SQLite only |
| `ROOMLY_SQLITE_FALLBACK` | `db/roomly.sqlite3` in dev, off in prod | SQLite file used when Postgres is unreachable at startup; `off` disables |
| `ROOMLY_FIXTURES` | `on` in dev, `off` in prod | stub endpoints answer with sample responses instead of 501 |
| `ROOMLY_MIGRATIONS_DIR` | repo `db/migrations` | set it when running from installed wheels (the release ships `roomly-db-<v>.tar.gz`) |
| `ROOMLY_API_URL` | `http://127.0.0.1:8000` | frontend rewrite target, read by `next.config.js` at build/start |

## Testing
```sh
script/database.sh start  # local Postgres for the Postgres half of the suite (another terminal)
script/backend.sh test    # pytest: DTO validation, DDL invariants on Postgres and SQLite, DB fallback
script/backend.sh lint    # ruff
script/frontend.sh build  # frontend build check
```

The Postgres runs use a throwaway `roomly_test` database (`ROOMLY_TEST_DATABASE_URL` overrides it). Without a reachable server they are skipped locally and fail in CI.

## CI and releases
- `ci.yml`: backend lint + test (with a `postgres:18` service), frontend build.
- `release.yml`: pushing a `v*` tag runs the tests, `script/release.sh`, and publishes a GitHub Release with the backend and `fastapi-reborn` wheels plus the frontend and migrations tarballs.
- CI clones the private submodule with a read-only deploy key (`SUBMODULE_SSH_KEY` secret).

## Dependencies
- [fastapi-reborn (v0.1.0)](https://github.com/2026Fall-CSUY-4523B-Design-Project/fastapi-reborn)
    -- [python (v3.14.0)](https://www.python.org/downloads/release/python-3140/)
    -- [uv (v0.13.1)](https://github.com/astral-sh/uv)
- [nextjs (v12.0.0)](https://github.com/vercel/next.js)
    -- [node (v24.x LTS)](https://nodejs.org/en/download) + [pnpm (v10.10.0)](https://pnpm.io/)
- [psycopg (v3.2+)](https://www.psycopg.org/psycopg3/) + psycopg-pool, the PostgreSQL driver
- [postgresql (v18.6)](https://www.postgresql.org/download/)
- [sqlite (v3.54.0)](https://www.sqlite.org/download.html)

## Useful links
- [Roomly SSDS](https://docs.google.com/document/d/1Dh9CcZlhd7KVQ4CXoJAdhSbQfYPbDyGvlC8uDVS-4Y0)
