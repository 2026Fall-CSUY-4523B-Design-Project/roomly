# Backend

The Roomly API: Python 3.14 on [FastAPI](https://fastapi.tiangolo.com/) (pydantic DTOs, served by
uvicorn), with PostgreSQL as the primary database and SQLite as the fallback. It implements the API
of the eight use cases of SSDS-001 v2.1 §8.1.2: 56 endpoints plus `/health`.

```sh
script/backend.sh dev       # serve on 127.0.0.1:8000, applying pending migrations first
script/backend.sh test      # pytest: services, DTO validation and DDL invariants (Postgres and SQLite)
script/backend.sh lint      # ruff
script/backend.sh migrate   # apply migrations to the configured database (or its fallback)
```

`GET /openapi.json` returns the OpenAPI document, with request and response schemas generated from
the DTOs; `/docs` (Swagger UI) and `/redoc` render it.

| Doc | Contents |
| --- | --- |
| [layers.md](layers.md) | controller → service → mapper → entity, DTO validation, access checks, error statuses |
| [database.md](database.md) | Postgres/SQLite fallback, one SQL text for two engines, migrations, invariants |
| [endpoints.md](endpoints.md) | every endpoint by SSDS use case |
| [traceability.md](traceability.md) | use case → controller/service/mapper/DTO map, tests, remaining work |

## Status

All eight use cases are implemented: account lifecycle and deletion, invitation-only groups,
listing cards and manual submission, administration (sources, duplicate review, reports),
hard-constraint search with saved searches and commute destinations, comparison with change
tracking, room messages/reactions/polls, and notifications.

DTO validation (422) and bearer authentication (401) run before every service call. Rules the
database can enforce are also triggers and constraints, so a race that slips past a service check
becomes a 409 that names the constraint. What is still missing is listed in
[traceability.md](traceability.md#remaining-work).

## Layout

```
backend/
  src/roomly/
    main.py         app factory, lifespan (database + migrations), exception handlers
    config.py       Settings from ROOMLY_* / DATABASE_URL
    controller/     HTTP routers, one per SSDS use case
    service/        business rules and transactions, one class per use case
    mapper/         hand-written SQL, one mapper per aggregate
    entity/         one frozen dataclass per table
    dto/            request/response bodies (frozen pydantic models)
    db/             Database (primary/fallback), Tx, migrations
  tests/            pytest; database tests run on both engines
```
