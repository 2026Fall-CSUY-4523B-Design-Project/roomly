# Roomly Mono repo

## About
# Roomly is a mono repo that contains multiple packages and applications related to the Roomly project. This repository is structured to facilitate development, testing, and deployment of various components in a unified manner.

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

Clone with submodules: `git clone --recurse-submodules <repo>` (or `git submodule update --init`).

## Dependencies
- [fastapi-reborn (v0.1.0)](https://github.com/2026Fall-CSUY-4523B-Design-Project/fastapi-reborn)
    -- [python (v3.14.0)](https://www.python.org/downloads/release/python-3140/)
    -- [uv (v0.13.1)](https://github.com/astral-sh/uv)
- [nextjs (v12.0.0)](https://github.com/vercel/next.js)
    -- [node (v24.x LTS)](https://nodejs.org/en/download)
- [postgresql (v18.6)](https://www.postgresql.org/download/)
- [sqlite (v3.54.0)](https://www.sqlite.org/download.html)

## Useful links
- [Roomly SSDS](https://docs.google.com/document/d/1Dh9CcZlhd7KVQ4CXoJAdhSbQfYPbDyGvlC8uDVS-4Y0)
- 