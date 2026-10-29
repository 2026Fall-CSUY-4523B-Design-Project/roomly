# Backend

The Roomly API: Python 3.14 on [FastAPI](https://fastapi.tiangolo.com/) (pydantic DTOs, served by uvicorn), with PostgreSQL as the primary database and SQLite as the fallback. It declares the API of the eight use cases of SSDS-001 v2.0 §8.1.2: 56 endpoints plus `/health`.

What exists: the schema and migrations, the database layer (with the fallback), DTOs, controllers, SQL mappers and entities. The service methods behind the controllers are **stubs**: each one raises `NotImplementedError`, which the API answers with `501 {"detail": "not implemented yet"}`. DTO validation (422) and the bearer-token check (401) already run before a stub is reached. In dev, stubs answer with sample data instead; see [Fixtures](#fixtures).

```sh
script/backend.sh dev       # serve on 127.0.0.1:8000, applying pending migrations first
script/backend.sh test      # pytest: DTO validation and DDL invariants (on Postgres and on SQLite)
script/backend.sh migrate   # apply migrations to the configured database (or its fallback)
```

`GET /openapi.json` returns the OpenAPI document, with request and response schemas generated from the DTOs; `/docs` (Swagger UI) and `/redoc` render it.

## Layers

```
HTTP ─▶ controller ─▶ service ─▶ mapper ─▶ Tx ─▶ PostgreSQL  (or the SQLite fallback)
        typed params,  rules,      SQL        one
        DTOs, Depends
        map errors     transactions           transaction
```

| Package | Role | SSDS |
| --- | --- | --- |
| `roomly.controller` | One `APIRouter` per use case. Endpoints declare typed path and query parameters and a request DTO, which FastAPI validates; `Depends` resolves the services (`Svc`) and the bearer session (`CurrentUser`). Each endpoint calls one service method and returns a DTO, its declared response model. It holds no business rules. | boundary classes |
| `roomly.service` | One class per use case, with the method signatures the controllers call; docstrings note the SSDS rule where one applies. Every method is a stub (`raise NotImplementedError`). Implementations open a transaction (`self.db.transaction()`), use the mappers, and raise `ServiceError` subclasses (`NotFound`, `Forbidden`, `Conflict`, ...), which the controller layer maps to HTTP statuses. | control classes §9.1 |
| `roomly.mapper` | Hand-written SQL, MyBatis style: one mapper per aggregate, and every statement visible in one place. Rows come back as entities. | — |
| `roomly.entity` | One frozen dataclass per table; field names equal column names. | entity classes §9.1 |
| `roomly.dto` | Frozen pydantic models (`dto.base.DTO`) for request and response bodies. Fields declare constraints with `Field(...)` and `StringConstraints` (length, range, pattern); `Email`, `Secret` (not stripped) and `Distinct` (unique items) are shared. Request numbers and booleans are strict (`StrictInt`, `StrictFloat`, `StrictBool`). `check()` holds cross-field rules and reports each problem at its field. | — |
| `roomly.db` | `Database` (primary/fallback selection, migrations) and the engine-neutral `Tx`. | — |

Endpoints and the `current_user` dependency are plain `def`, so FastAPI runs them in its thread pool and the blocking database calls stay off the event loop. Services are synchronous and use psycopg 3 with a connection pool, or `sqlite3` with one connection per transaction.

## Errors

| Status | Body | When |
| --- | --- | --- |
| 401 | `{"detail": "..."}` plus `WWW-Authenticate: Bearer` | no bearer token (checked today); an expired or revoked session (once `AccountService.authenticate` is implemented) |
| 403 | `{"detail": "..."}` | signed in, but not allowed (not a member, not the owner, not an administrator) |
| 404 | `{"detail": "..."}` | not found; also an invitation addressed to someone else, so its existence is never confirmed |
| 409 | `{"detail": "...", "constraint": "name"}` | a rule conflict from a service, or a database invariant that caught a race |
| 422 | `{"detail": [{"loc": ["body", "email"], "msg": "...", "type": "...", "input": ...}]}` | validation of the body, path (`["path", "group_id"]`) or query (`["query", "limit"]`), all problems at once |
| 501 | `{"detail": "not implemented yet"}` | the service method is still a stub and fixtures are off |
| 503 | `{"detail": "the database is unavailable, try again shortly"}` | the database dropped while serving |

## Fixtures

`backend/src/roomly/fixtures.py` holds one sample response per route, keyed by `"METHOD /route/template"`. When a service stub raises `NotImplementedError` and `ROOMLY_FIXTURES` is on (the default in dev; off in prod), the error handler answers with that route's sample:

- the response uses the route's normal status code (201 for creates, 204 with no body for deletes) and carries `X-Roomly-Fixture: 1`;
- while `AccountService.authenticate` is a stub, any bearer token resolves to the sample user (Maya), so a route still validates its path, query and body first (422) and still rejects a missing token (401);
- path ids and request bodies do not change the sample: every call to a route returns the same data;
- once a service method is implemented it returns real data, while the routes still on stubs keep returning samples.

The samples form one consistent world, so ids line up across endpoints:

- Maya owns the group "Bushwick crew" with Alex and Sam;
- three listings: Brooklyn (sources disagree on the bathrooms), Queens (with Unknown values) and Manhattan;
- a shared comparison with one changed value;
- messages (one from a deleted user), an open poll, notifications, and admin sources, a duplicate pair and a report.

The samples are built from the response DTOs, so a missing or renamed field fails at import. `tests/test_fixtures.py` checks that every route with a body has a sample of its declared return type.

## Database

### PostgreSQL primary, SQLite fallback

`DATABASE_URL` names the primary database. At startup Roomly probes it with a 3-second connect timeout:

- If the probe succeeds, Roomly runs on **Postgres**, with a psycopg pool.
- If Postgres is unreachable and `ROOMLY_SQLITE_FALLBACK` names a file, Roomly logs a `WARNING` and runs on **SQLite** at that path. The fallback is on by default in dev (`db/roomly.sqlite3`) and off in prod. Set it to `off` to disable it in dev, or to a path to enable it in prod.
- If Postgres is unreachable and no fallback is set, startup fails with the connection error.
- `DATABASE_URL=sqlite:///path/to/file.sqlite3` runs on SQLite only.

`GET /health` reports the engine in use: `{"status": "ok", "database": "postgres" | "sqlite"}`.

The fallback is a separate database. Rows written there are **not** copied back to Postgres when it returns; Roomly simply starts on Postgres again on the next start.

### One SQL text, two engines

Mappers write each statement once, in the SQL both engines share, with psycopg-style named parameters (`%(name)s`). `SqliteTx`:

- rewrites the parameters to `:name`;
- drops `FOR UPDATE`, since a SQLite transaction starts with `BEGIN IMMEDIATE` and already holds the write lock;
- registers `gen_random_uuid()`, `now()` and `regexp()` (with Postgres `~` semantics);
- converts row values back to the entity's annotated types: UUID, datetime, date, Decimal, bool, list and dict.

As a result, mappers return the same Python values from both engines. The two constructs that differ come from the transaction:

| Need | Call | PostgreSQL | SQLite |
| --- | --- | --- | --- |
| value in a list parameter | `tx.any_of(expr, param, "uuid")` | `expr = ANY(%(p)s::uuid[])` | `expr IN (SELECT value FROM json_each(:p))` |
| array contains every item | `tx.contains_all(col, param)` | `col @> %(p)s::text[]` | `NOT EXISTS (...json_each...)` |

### Migrations

`db/migrations/postgres/NNNN_name.sql` and `db/migrations/sqlite/NNNN_name.sql` hold the same schema in each dialect. Each migration file runs once, in its own transaction, and is recorded in `schema_migration`. On Postgres the runner holds an advisory lock; on SQLite it uses `BEGIN IMMEDIATE`. Two servers starting together therefore never apply the same file twice.

To add a migration, write **both** files with the same version number. `tests/test_schema.py` runs every invariant on both engines.

### Schema conventions

- **NULL means Unknown.** An Unknown value is never stored as 0 or as an empty string. DTOs carry an `unknown` list so a client can label the value "Unknown".
- Money is stored as **integer cents** (`*_cents`). Enums are `text` columns with a `CHECK`. Timestamps are UTC (`timestamptz` in Postgres; fixed-width ISO text in SQLite, so text order is time order).
- No PostGIS: `listing.latitude` and `longitude` are plain columns, and the map viewport filter is a bounds check. Routing for commute times (R-3.5) is not built yet.

### Invariants the database enforces

The database enforces these rules itself, so they hold whatever a service does or forgets; a violation becomes a 409 that names the constraint.

| Rule | Constraint |
| --- | --- |
| A group has at most six current members (R-1.2) | trigger `group_membership_max_six` |
| Administrators are never group members | trigger `group_membership_eligible` |
| A group has one current owner | unique index `group_membership_one_owner_key` |
| A person has at most three commute destinations | trigger `commute_destination_max_three` |
| A searchable listing has a borough and a minimum stay of at least 30 days (R-2.1) | check `listing_searchable_in_scope` |
| A retried fetch is not a second record | unique `source_record_fetch_key` |
| A closed poll rejects votes; a vote's option belongs to its poll | trigger `poll_vote_poll_open`, composite FK |
| One reaction per member per message; one vote per member per poll | unique keys |
| A notification is sent once per (recipient, kind, event) | unique `notification_once_key` |
| A deleted account holds no personal data (R-1.4) | check on `app_user` |

21 tables: `app_user`, `user_session`, `user_group`, `group_membership`, `group_invitation`, `listing_source`, `listing`, `source_record`, `listing_price_history`, `duplicate_candidate`, `data_report`, `commute_destination`, `saved_search`, `comparison`, `comparison_listing`, `message`, `message_reaction`, `poll`, `poll_option`, `poll_vote`, `notification`.

## Endpoints

The intended behavior of each endpoint, from the SSDS. Today every one of them answers 501 once its request has passed DTO validation and, where required, the bearer check. "Guest" means no token is needed; every other route takes `Authorization: Bearer <token>` from sign-up or sign-in.

### Login (§8.1.2.1)
| | |
| --- | --- |
| `POST /auth/sign-up` | guest · create an account and sign in |
| `POST /auth/sign-in` | guest · sign in with email and password |
| `POST /auth/sign-out` | invalidate this session |
| `GET /me` | the signed-in account |
| `DELETE /me` | delete the account (the password confirms it); shared content then shows "Deleted user" |

### Group Management (§8.1.2.2)
| | |
| --- | --- |
| `POST /groups` | create a group; you become its owner |
| `GET /groups` | your current groups |
| `GET /groups/{id}` | a group and its current members |
| `POST /groups/{id}/invitations` | owner · invite by email |
| `GET /groups/{id}/invitations` | invitations the group has sent |
| `POST /groups/{id}/leave` | leave; an owner transfers ownership first, and a sole member leaving dissolves the group |
| `POST /groups/{id}/transfer` | owner · hand ownership to another member |
| `DELETE /groups/{id}/members/{user_id}` | owner · remove a member |
| `GET /invitations` | pending invitations addressed to you |
| `POST /invitations/{id}/accept` · `/decline` | respond to an invitation |

### Listing Submission and cards (§8.1.2.3)
| | |
| --- | --- |
| `POST /listings` | submit by manual entry; possible duplicates are held for review |
| `GET /listings/{id}` | guest · the full card with sources, conflicts, price history and price per sq ft (with its formula) |
| `POST /listings/{id}/reports` | report wrong data or a wrong merge |

### Listing Administration (§8.1.2.4), administrators only
| | |
| --- | --- |
| `GET /admin/sources` · `POST /admin/sources` · `PATCH /admin/sources/{id}` | listing sources |
| `GET /admin/duplicates` | the duplicate review queue |
| `POST /admin/duplicates/{id}/merge` · `/keep-separate` · `/split` | decide a candidate pair, or undo a merge |
| `GET /admin/reports` · `POST /admin/reports/{id}/resolve` | user data reports |

### Search and Ranking (§8.1.2.5)
| | |
| --- | --- |
| `GET /search` | guest · hard constraints only (rent, borough, bedrooms, area, move-in, amenities, no broker fee, viewport). Repeat `borough` or `amenity` to pass several values. An Unknown value fails any active constraint on it. |
| `GET /saved-searches` · `POST /saved-searches` · `DELETE /saved-searches/{id}` | saved criteria |
| `GET /saved-searches/{id}/results` | re-run a saved search |
| `GET /me/commute-destinations` · `POST` · `DELETE /{id}` | up to three destinations |

### Comparison (§8.1.2.6)
| | |
| --- | --- |
| `POST /comparisons/preview` | guest · compare 2–4 listings without saving. Best value is highlighted only among at least two known, untied values. |
| `POST /comparisons` · `GET /comparisons` · `GET /comparisons/{id}` | save, list and open comparisons; a saved one flags the values that changed since it was saved instead of replacing them |
| `POST /comparisons/{id}/share` · `GET /groups/{id}/comparisons` | share with a group |

### Group Discussion (§8.1.2.7)
| | |
| --- | --- |
| `GET /groups/{id}/messages?before=...` · `POST` | room messages, newest first, with cursor paging |
| `PUT /messages/{id}/reaction` · `DELETE` | one reaction per member |
| `POST /groups/{id}/polls` · `GET` · `GET /polls/{id}` | polls with 2–4 options |
| `PUT /polls/{id}/vote` · `POST /polls/{id}/close` | vote or change a vote; the creator or the owner closes the poll |

### Notifications (§8.1.2.8)
| | |
| --- | --- |
| `GET /notifications` | your notifications with unread count |
| `POST /notifications/{id}/read` · `/read-all` | mark as read |
| `GET /me/notification-settings` · `PUT` | kinds, email, digest, quiet hours |

## Traceability

| Use case | Controller | Service (stub) | Mapper | DTOs |
| --- | --- | --- | --- | --- |
| §8.1.2.1 Login | `account_controller` | `AccountService` | `account_mapper` | `dto/account` |
| §8.1.2.2 Group Management | `group_controller` | `GroupService` | `group_mapper` | `dto/group` |
| §8.1.2.3 Listing Submission | `listing_controller` | `ListingService` | `listing_mapper` | `dto/listing` |
| §8.1.2.4 Listing Administration | `admin_controller` | `AdminService` | `listing_mapper` | `dto/admin` |
| §8.1.2.5 Search and Ranking | `search_controller` | `SearchService` | `search_mapper`, `listing_mapper` | `dto/search` |
| §8.1.2.6 Comparison | `comparison_controller` | `ComparisonService` | `comparison_mapper` | `dto/comparison` |
| §8.1.2.7 Group Discussion | `room_controller` | `RoomService` | `room_mapper` | `dto/room` |
| §8.1.2.8 Notifications | `notification_controller` | `NotificationService` | `notification_mapper` | `dto/notification` |

Tests: `test_dto` (validation rules, 422 locations, the OpenAPI document), `test_fixtures` (a sample for every route, served through FastAPI), `test_schema` (DDL invariants on both engines), `test_database` (primary/fallback selection), `test_config`, `test_health`. HTTP-level tests use FastAPI's `TestClient`.

## To do

- Every method in `roomly/service/` (all eight use cases), including sign-in itself: password hashing and bearer sessions (`AccountService.authenticate`), and access checks such as "members only" and "owner only".
- Pieces the SSDS plans that have no stub yet: the SampleFeed collector job, ranking with explained scores (R-3.3), commute routing (R-3.5), live room push, the email/digest worker, importing a listing from a URL, personal data export, and the per-member group fit matrix.
- A way to grant the administrator role (today: `UPDATE app_user SET role = 'admin'`).
