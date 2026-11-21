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
    service/      business rules and transactions, one class per use case
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
mail/         Cloudflare Worker: outbound auth mail `mail.roomly.bid`, inbound routing
deploy/       docker compose stack, nginx site, and the deploy script CI calls
.github/      CI and release workflows
docs/         backend/*.md · frontend/*.md · deploy.md
```

## Quick start
```sh
git clone <repo>
cd roomly
script/run.sh        # = script/run.sh --dev
```

`script/run.sh --dev` starts local Postgres (`127.0.0.1:5433`, data in `db/data`), the backend (`:8000`) and the frontend (`:3000`, `/api/*` is rewritten to the backend). Output is prefixed per service (`[db]`, `[backend]`, `[frontend]`); Ctrl-C stops everything.

`script/run.sh --prod` builds and starts the backend and frontend against an external database; `DATABASE_URL` must be set.

To fill the development database with demo accounts, groups, listings and activity, run `script/seed.sh` (all demo passwords are `roomly1234`; `--reset` empties the database first).

The backend applies pending migrations when it starts. API docs: <http://127.0.0.1:8000/docs> (Swagger UI), `/redoc`, `/openapi.json`. All 56 endpoints are implemented with their DTOs; the remaining work is listed in [docs/backend/traceability.md](docs/backend/traceability.md#remaining-work).

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
| `script/seed.sh` | `[--reset]` demo accounts, groups, listings and activity in the development database |
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
| `ROOMLY_MIGRATIONS_DIR` | repo `db/migrations` | set it when running from installed wheels (the release ships `roomly-db-<v>.tar.gz`) |
| `ROOMLY_MAIL` | `log` in dev, `http` in prod | `log` writes verification and reset links to the backend log; `http` posts to the mail Worker (prod refuses `log`) |
| `ROOMLY_MAIL_URL` / `ROOMLY_MAIL_SECRET` | none | required when `ROOMLY_MAIL=http`: the Worker's base URL and the secret both sides sign with |
| `ROOMLY_APP_URL` | `http://localhost:3000` | site URL used in the links the `log` mailer prints |
| `ROOMLY_API_URL` | `http://127.0.0.1:8000` | frontend rewrite target, read by `next.config.js` at build/start |

## Testing
```sh
script/database.sh start  # local Postgres for the Postgres half of the suite (another terminal)
script/backend.sh test    # pytest: services, DTO validation, DDL invariants on Postgres and SQLite, DB fallback
script/backend.sh lint    # ruff
script/frontend.sh build  # frontend build check (there are no frontend tests)
```

The Postgres runs use a throwaway `roomly_test` database (`ROOMLY_TEST_DATABASE_URL` overrides it). Without a reachable server they are skipped locally and fail in CI.

Acceptance testing: [docs/testing/uat.md](docs/testing/uat.md) is run against a seeded database before every major version bump.

## Account authentication

Sign up at `/sign-up`, confirm the address with the emailed link, then sign in at `/sign-in`; the
header shows the account and a sign-out button. Sign-in is refused until the address is confirmed.
`/forgot-password` emails a reset link that signs the account out everywhere. In development the
links are printed in the backend log (`ROOMLY_MAIL=log`).
Passwords are salted scrypt, only SHA-256 hashes of bearer tokens are stored, sessions last seven
days, and sign-out revokes the current session. The browser keeps the token in per-tab
`sessionStorage` and restores it through `GET /me`; closing the tab clears storage but not the
server session. Browser behaviour is
described in [docs/frontend/auth.md](docs/frontend/auth.md), the API in
[docs/backend/endpoints.md](docs/backend/endpoints.md#login-8121).

## CI and releases
- `ci.yml`: backend lint + test (with a `postgres:18` service), frontend build, and a `containers`
  job that runs `deploy/test-deploy.sh`, builds both images and starts the production compose stack
  (read-only, no capabilities) until it answers through the frontend, so a broken Dockerfile or
  compose file fails before a tag does.
- `mail.yml`: typecheck, vitest and a `wrangler deploy --dry-run` for the mail Worker; `main` deploys
  the staging Worker.
- `release.yml`: pushing a `v*` tag publishes both images to ghcr.io, deploys the mail Worker, then
  the host, and opens the GitHub Release. There is no approval step — the tag is the deploy.

Production is one VPS behind Cloudflare running docker compose, with the mail Worker alongside it.
[docs/deploy.md](docs/deploy.md) covers the host, DNS, mail, the deploy key and what a compromised
container can reach.

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
