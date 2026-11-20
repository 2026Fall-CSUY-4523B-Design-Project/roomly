# Database

## PostgreSQL primary, SQLite fallback

`DATABASE_URL` names the primary database. At startup Roomly probes it with a 3-second connect
timeout:

- If the probe succeeds, Roomly runs on **Postgres**, with a psycopg pool.
- If Postgres is unreachable and `ROOMLY_SQLITE_FALLBACK` names a file, Roomly logs a `WARNING` and
  runs on **SQLite** at that path. The fallback is on by default in dev (`db/roomly.sqlite3`) and off
  in prod. Set it to `off` to disable it in dev, or to a path to enable it in prod.
- If Postgres is unreachable and no fallback is set, startup fails with the connection error.
- `DATABASE_URL=sqlite:///path/to/file.sqlite3` runs on SQLite only.

`GET /health` reports the engine in use: `{"status": "ok", "database": "postgres" | "sqlite"}`.

The fallback is a separate database. Rows written there are **not** copied back to Postgres when it
returns; Roomly simply starts on Postgres again on the next start.

## One SQL text, two engines

Mappers write each statement once, in the SQL both engines share, with psycopg-style named
parameters (`%(name)s`). `SqliteTx`:

- rewrites the parameters to `:name`;
- drops `FOR UPDATE`, since a SQLite transaction starts with `BEGIN IMMEDIATE` and already holds the
  write lock;
- registers `gen_random_uuid()`, `now()` and `regexp()` (with Postgres `~` semantics);
- converts row values back to the entity's annotated types: UUID, datetime, date, Decimal, bool,
  list and dict.

As a result, mappers return the same Python values from both engines. The two constructs that differ
come from the transaction:

| Need | Call | PostgreSQL | SQLite |
| --- | --- | --- | --- |
| value in a list parameter | `tx.any_of(expr, param, "uuid")` | `expr = ANY(%(p)s::uuid[])` | `expr IN (SELECT value FROM json_each(:p))` |
| array contains every item | `tx.contains_all(col, param)` | `col @> %(p)s::text[]` | `NOT EXISTS (...json_each...)` |

## Migrations

`db/migrations/postgres/NNNN_name.sql` and `db/migrations/sqlite/NNNN_name.sql` hold the same schema
in each dialect. Each migration file runs once, in its own transaction, and is recorded in
`schema_migration` by version only — there is no checksum, so editing a file that has already been
applied changes nothing. Add a new numbered file instead. On Postgres the runner holds an advisory
lock; on SQLite it uses `BEGIN IMMEDIATE`. Two servers starting together therefore never apply the
same file twice.

To add a migration, write **both** files with the same version number. `tests/test_schema.py` runs
every invariant on both engines.

## Schema conventions

- **NULL means Unknown.** An Unknown value is never stored as 0 or as an empty string. DTOs carry an
  `unknown` list so a client can label the value "Unknown".
- Money is stored as **integer cents** (`*_cents`). Enums are `text` columns with a `CHECK`.
  Timestamps are UTC (`timestamptz` in Postgres; fixed-width ISO text in SQLite, so text order is
  time order).
- No PostGIS: `listing.latitude` and `longitude` are plain columns, and the map viewport filter is a
  bounds check. Routing for commute times (R-3.5) is not built yet.

## Invariants the database enforces

The database enforces these rules itself, so they hold whatever a service does or forgets; a
violation becomes a 409 that names the constraint.

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

21 tables: `app_user`, `user_session`, `user_group`, `group_membership`, `group_invitation`,
`listing_source`, `listing`, `source_record`, `listing_price_history`, `duplicate_candidate`,
`data_report`, `commute_destination`, `saved_search`, `comparison`, `comparison_listing`, `message`,
`message_reaction`, `poll`, `poll_option`, `poll_vote`, `notification`.
