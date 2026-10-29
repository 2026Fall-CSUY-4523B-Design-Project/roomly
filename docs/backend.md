# Backend

The Roomly API: Python 3.14 on [fastapi-reborn](https://github.com/2026Fall-CSUY-4523B-Design-Project/fastapi-reborn) (stdlib only, no pydantic), with PostgreSQL as the primary database and SQLite as the fallback. It implements the eight use cases of SSDS-001 v2.0 §8.1.2 as 56 endpoints plus `/health`.

```sh
script/backend.sh dev       # serve on 127.0.0.1:8000, applying pending migrations first
script/backend.sh test      # pytest: every database test runs on Postgres and on SQLite
script/backend.sh migrate   # apply migrations to the configured database (or its fallback)
script/backend.sh admin you@example.com [--revoke]   # grant or revoke the administrator role
```

`GET /openapi.json` (also served at `/docs`) returns the OpenAPI document, with request and response schemas generated from the DTOs.

## Layers

```
HTTP ─▶ controller ─▶ service ─▶ mapper ─▶ Tx ─▶ PostgreSQL  (or the SQLite fallback)
        parse DTOs     rules,      SQL        one
        map errors     transactions           transaction
```

| Package | Role | SSDS |
| --- | --- | --- |
| `roomly.controller` | One `APIRouter` per use case. Parses path, query and body into DTOs, resolves the bearer session, calls one service method, and returns a DTO. It holds no business rules. | boundary classes |
| `roomly.service` | One class per use case. Each method opens a transaction, enforces the rules and access checks (`access.require_member` and similar), and raises `ServiceError` subclasses (`NotFound`, `Forbidden`, `Conflict`, ...). | control classes §9.1 |
| `roomly.mapper` | Hand-written SQL, MyBatis style: one mapper per aggregate, and every statement visible in one place. Rows come back as entities. | — |
| `roomly.entity` | One frozen dataclass per table; field names equal column names. | entity classes §9.1 |
| `roomly.dto` | Frozen dataclasses for request and response bodies. Each field declares its constraints with `rule(...)` (length, range, pattern, unique items, lower-casing); `check()` holds cross-field rules. `parse()` returns FastAPI-style 422 errors. | — |
| `roomly.db` | `Database` (primary/fallback selection, migrations) and the engine-neutral `Tx`. | — |

Controllers are async; `controller.base.run` moves each blocking service call onto a worker thread (`asyncio.to_thread`). Services are synchronous and use psycopg 3 with a connection pool, or `sqlite3` with one connection per transaction.

## Errors

| Status | Body | When |
| --- | --- | --- |
| 401 | `{"detail": "..."}` plus `WWW-Authenticate: Bearer` | missing, expired or revoked session |
| 403 | `{"detail": "..."}` | signed in, but not allowed (not a member, not the owner, not an administrator) |
| 404 | `{"detail": "..."}` | not found; also an invitation addressed to someone else, so its existence is never confirmed |
| 409 | `{"detail": "...", "constraint": "name"}` | a rule conflict from a service, or a database invariant that caught a race |
| 422 | `{"detail": [{"loc": ["body", "email"], "msg": "...", "type": "...", "input": ...}]}` | DTO validation |
| 503 | `{"detail": "the database is unavailable, try again shortly"}` | the database dropped while serving |

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

As a result, services see the same Python values from both engines. The two constructs that differ come from the transaction:

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
- Passwords are hashed with PBKDF2-SHA256 (600,000 iterations by default). Sessions are random bearer tokens, and only `sha256(token)` is stored, in `user_session`.

### Invariants the database enforces

The services check these rules first. The database enforces them again, so a race or a forgotten check still cannot break them; a violation becomes a 409 that names the constraint.

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

"Guest" means no token is needed. Every other route takes `Authorization: Bearer <token>` from sign-up or sign-in.

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

| Use case | Controller | Service | Mapper | Tests |
| --- | --- | --- | --- | --- |
| §8.1.2.1 Login | `account_controller` | `AccountService` | `account_mapper` | `test_account_api` |
| §8.1.2.2 Group Management | `group_controller` | `GroupService` | `group_mapper` | `test_group_api` |
| §8.1.2.3 Listing Submission | `listing_controller` | `ListingService` | `listing_mapper` | `test_listing_admin_api` |
| §8.1.2.4 Listing Administration | `admin_controller` | `AdminService` | `listing_mapper` | `test_listing_admin_api`, `test_admin_cli` |
| §8.1.2.5 Search and Ranking | `search_controller` | `SearchService` | `search_mapper`, `listing_mapper` | `test_search_api` |
| §8.1.2.6 Comparison | `comparison_controller` | `ComparisonService` | `comparison_mapper` | `test_comparison_api` |
| §8.1.2.7 Group Discussion | `room_controller` | `RoomService` | `room_mapper` | `test_room_api` |
| §8.1.2.8 Notifications | `notification_controller` | `NotificationService` | `notification_mapper` | `test_notification_api` |

Cross-cutting tests: `test_dto` (validation), `test_schema` (DDL invariants on both engines), `test_database` (fallback selection), `test_config`, `test_health`.

## Not built yet

These parts of the SSDS have a schema or an endpoint shape but no working implementation. Each is listed here so it is not mistaken for a finished feature.

| Item | Use case | Sprint | State today |
| --- | --- | --- | --- |
| SampleFeed ingestion and normalization | §8.1.2.4 | 3 | tables (`listing_source`, `source_record`) and source admin exist; no collector job |
| Ranking with explained scores | §8.1.2.5, R-3.3 | 4 | `/search` orders by the requested sort; results carry no score |
| Commute times (routing) | §8.1.2.5, R-3.5 | 4 | destinations are stored; comparisons show commute as Unknown with a note |
| Live room updates (push) | §8.1.2.7 | 5 | clients poll `GET /groups/{id}/messages` |
| Email delivery, digest and quiet hours | §8.1.2.8 | 5 | notifications are stored with `email_status = 'pending'`; no worker sends them |
| Import a listing from a URL | §8.1.2.3 | — | manual entry only |
| Personal data export | §8.1.2.1 | — | deletion works; export does not |
| Per-member group fit matrix | — | — | not started |
