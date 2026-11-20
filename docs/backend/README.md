# Backend

The Roomly API: Python 3.14 on [FastAPI](https://fastapi.tiangolo.com/) (pydantic DTOs, served by
uvicorn), with PostgreSQL as the primary database and SQLite as the fallback. It declares the API of
the eight use cases of SSDS-001 v2.1 §8.1.2: 56 endpoints plus `/health`.

```sh
script/backend.sh dev       # serve on 127.0.0.1:8000, applying pending migrations first
script/backend.sh test      # pytest: DTO validation and DDL invariants (on Postgres and on SQLite)
script/backend.sh lint      # ruff
script/backend.sh migrate   # apply migrations to the configured database (or its fallback)
```

`GET /openapi.json` returns the OpenAPI document, with request and response schemas generated from
the DTOs; `/docs` (Swagger UI) and `/redoc` render it.

| Doc | Contents |
| --- | --- |
| [layers.md](layers.md) | controller → service → mapper → entity, DTO validation, error statuses, fixtures |
| [database.md](database.md) | Postgres/SQLite fallback, one SQL text for two engines, migrations, invariants |
| [endpoints.md](endpoints.md) | every endpoint by SSDS use case, and which are implemented |
| [traceability.md](traceability.md) | use case → controller/service/mapper/DTO map, tests, to do |

## Status

What exists: the schema and migrations, the database layer (with the fallback), DTOs, controllers,
SQL mappers and entities. Account sign-up, sign-in, sign-out, authentication and `GET /me` are
implemented. The remaining service methods are **stubs**: each raises `NotImplementedError`, which
the API answers with `501 {"detail": "not implemented yet"}`. DTO validation (422) and real session
authentication (401) already run before a stub is reached. In dev, stubs answer with sample data
instead; see [layers.md#fixtures](layers.md#fixtures).

## Layout

```
backend/
  src/roomly/
    main.py         app factory, lifespan (database + migrations), exception handlers
    config.py       Settings from ROOMLY_* / DATABASE_URL
    controller/     HTTP routers, one per SSDS use case
    service/        business rules; account authentication only, the rest are stubs
    mapper/         hand-written SQL, one mapper per aggregate
    entity/         one frozen dataclass per table
    dto/            request/response bodies (frozen pydantic models)
    db/             Database (primary/fallback), Tx, migrations
    fixtures.py     one sample response per route
  tests/            pytest; database tests run on both engines
```
