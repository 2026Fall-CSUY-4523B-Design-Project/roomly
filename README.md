# Roomly Mono repo

Roomly: a monorepo for the Roomly project — Next.js frontend, FastAPI backend, PostgreSQL with a
SQLite fallback. Backend details in [docs/backend/](docs/backend/README.md); frontend in
[docs/frontend/](docs/frontend/README.md).

## Structure
- Frontend: Node, Next.js 12 pages router ([docs/frontend/](docs/frontend/README.md))
- Backend: Python, FastAPI + pydantic on uvicorn; layers DTO → controller → service → SQL mapper → entity ([docs/backend/](docs/backend/README.md))
- DB: PostgreSQL as primary, SQLite as fallback

```
backend/
  src/roomly/
    controller/   HTTP routers, one per SSDS use case (§8.1.2.1–8)
    service/      account authentication; remaining methods are stubs (HTTP 501)
    mapper/       hand-written SQL, one mapper per aggregate
    entity/       one dataclass per table
    dto/          request/response bodies: pydantic models with validation rules
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
script/       run.sh · backend.sh · frontend.sh · database.sh · release.sh
.github/      CI and release workflows
docs/         backend/*.md · frontend/*.md
```

## Quick start
```sh
git clone <repo>
cd roomly
script/run.sh        # = script/run.sh --dev
```

`script/run.sh --dev` starts local Postgres (`127.0.0.1:5433`, data in `db/data`), the backend (`:8000`) and the frontend (`:3000`, `/api/*` is rewritten to the backend). Output is prefixed per service (`[db]`, `[backend]`, `[frontend]`); Ctrl-C stops everything.

`script/run.sh --prod` builds and starts the backend and frontend against an external database; `DATABASE_URL` must be set.

The backend applies pending migrations when it starts. API docs: <http://127.0.0.1:8000/docs> (Swagger UI), `/redoc`, `/openapi.json`. All 56 endpoints are declared with their DTOs; sign-up, sign-in, sign-out and `/me` are implemented and the rest are stubs (see [docs/backend/traceability.md](docs/backend/traceability.md#to-do)).

**Fixtures.** In dev a stub answers with a sample response from `backend/src/roomly/fixtures.py` and an `X-Roomly-Fixture: 1` header instead of 501, so the frontend can be built against the real API shape first. Validation (422) and authentication (401) still apply. `ROOMLY_FIXTURES=off` disables it; it is off in prod.

## Database: PostgreSQL primary, SQLite fallback
- At startup the backend connects to `DATABASE_URL` (PostgreSQL).
- If Postgres is unreachable and a fallback file is configured, it logs a warning and runs on SQLite instead. The fallback is `db/roomly.sqlite3` in dev and off in prod; `ROOMLY_SQLITE_FALLBACK` changes it.
- `DATABASE_URL=sqlite:///path/to/file.sqlite3` runs on SQLite only. The two are separate databases; data is not copied back.
- `GET /health` reports which engine is in use: `{"status": "ok", "database": "postgres"}`.
- Both engines run the same schema and the same invariants (at most six members per group, one vote per member, one notification per event). See [docs/backend/database.md](docs/backend/database.md).

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
script/frontend.sh build  # frontend build check (there are no frontend tests)
```

The Postgres runs use a throwaway `roomly_test` database (`ROOMLY_TEST_DATABASE_URL` overrides it). Without a reachable server they are skipped locally and fail in CI.

## Account authentication

Sign up at `/sign-up` or sign in at `/sign-in`; the header shows the account and a sign-out button.
Passwords are salted scrypt, only SHA-256 hashes of bearer tokens are stored, sessions last seven
days, and sign-out revokes the current session. The browser keeps the token in per-tab
`sessionStorage` and restores it through `GET /me`; closing the tab clears storage but not the
server session. Authentication requires real accounts even with fixtures on. Browser behaviour is
described in [docs/frontend/auth.md](docs/frontend/auth.md), the API in
[docs/backend/endpoints.md](docs/backend/endpoints.md#login-8121).

## CI and releases
- `ci.yml`: backend lint + test (with a `postgres:18` service), frontend build.
- `release.yml`: pushing a `v*` tag runs the tests, `script/release.sh`, and publishes a GitHub Release with the backend wheel plus the frontend and migrations tarballs.

## Dependencies
- [fastapi (v0.162)](https://fastapi.tiangolo.com/) + [pydantic (v2.14)](https://docs.pydantic.dev/), served by [uvicorn (v0.54)](https://www.uvicorn.org/)
    -- [python (v3.14.0)](https://www.python.org/downloads/release/python-3140/)
    -- [uv (v0.13.1)](https://github.com/astral-sh/uv)
- [nextjs (v12.0.0)](https://github.com/vercel/next.js)
    -- [node (v24.x LTS)](https://nodejs.org/en/download) + [pnpm (v10.10.0)](https://pnpm.io/)
- [psycopg (v3.2+)](https://www.psycopg.org/psycopg3/) + psycopg-pool, the PostgreSQL driver
- [postgresql (v18.6)](https://www.postgresql.org/download/)
- [sqlite (v3.54.0)](https://www.sqlite.org/download.html)

## Useful links
- [Roomly SSDS](https://docs.google.com/document/d/1Dh9CcZlhd7KVQ4CXoJAdhSbQfYPbDyGvlC8uDVS-4Y0)
