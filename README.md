# Roomly Mono repo

## About
Roomly is a mono repo that contains multiple packages and applications related to the Roomly project. This repository is structured to facilitate development, testing, and deployment of various components in a unified manner.

## Structure
- Frontend: node, nextjs (frontend only)
- Backend: python, fastapi-reborn
- DB: postgres/sqlite

```
backend/     Python API (src/roomly, tests/)
frontend/    Next.js app (pages/)
db/          migrations/ (local data in db/data, gitignored)
packages/    git submodules (fastapi-reborn)
script/      run.sh · backend.sh · frontend.sh · database.sh · release.sh
.github/     CI and release workflows
docs/
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

## Scripts
| Script | Usage |
| --- | --- |
| `script/run.sh` | `[--dev\|--prod]` whole stack, see above |
| `script/backend.sh` | `[dev\|prod\|test\|lint]` API server, pytest, ruff |
| `script/frontend.sh` | `[dev\|build\|start]` Next.js via pnpm |
| `script/database.sh` | `[start\|reset\|psql]` local Postgres in the foreground (`ROOMLY_DB_PORT` overrides 5433) |
| `script/release.sh` | `[version]` builds wheels and the frontend tarball into `dist/` |

## Configuration
Copy [.env.example](.env.example) and export it, or set the variables in your deploy environment.

| Variable | Default | Notes |
| --- | --- | --- |
| `ROOMLY_ENV` | `dev` | `dev` or `prod`; `prod` binds `0.0.0.0`, logs at INFO and requires `DATABASE_URL` |
| `ROOMLY_HOST` / `ROOMLY_PORT` | `127.0.0.1` (`0.0.0.0` in prod) / `8000` | backend bind address |
| `ROOMLY_LOG_LEVEL` | `DEBUG` (`INFO` in prod) | |
| `DATABASE_URL` | `postgresql://roomly@127.0.0.1:5433/postgres` in dev | required in prod |
| `ROOMLY_API_URL` | `http://127.0.0.1:8000` | frontend rewrite target, read by `next.config.js` at build/start |

## Testing
```sh
script/backend.sh test    # pytest
script/backend.sh lint    # ruff
script/frontend.sh build  # frontend build check
```

## CI and releases
- `ci.yml`: backend lint + test, frontend build.
- `release.yml`: pushing a `v*` tag runs the tests, `script/release.sh`, and publishes a GitHub Release with the backend and `fastapi-reborn` wheels plus the frontend tarball.
- CI clones the private submodule with a read-only deploy key (`SUBMODULE_SSH_KEY` secret).

## Dependencies
- [fastapi-reborn (v0.1.0)](https://github.com/2026Fall-CSUY-4523B-Design-Project/fastapi-reborn)
    -- [python (v3.14.0)](https://www.python.org/downloads/release/python-3140/)
    -- [uv (v0.13.1)](https://github.com/astral-sh/uv)
- [nextjs (v12.0.0)](https://github.com/vercel/next.js)
    -- [node (v24.x LTS)](https://nodejs.org/en/download) + [pnpm (v10.10.0)](https://pnpm.io/)
- [postgresql (v18.6)](https://www.postgresql.org/download/)
- [sqlite (v3.54.0)](https://www.sqlite.org/download.html)

## Useful links
- [Roomly SSDS](https://docs.google.com/document/d/1Dh9CcZlhd7KVQ4CXoJAdhSbQfYPbDyGvlC8uDVS-4Y0)
