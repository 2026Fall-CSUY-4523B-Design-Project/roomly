# Layers

```
HTTP ─▶ controller ─▶ service ─▶ mapper ─▶ Tx ─▶ PostgreSQL  (or the SQLite fallback)
        typed params,  rules,      SQL        one
        DTOs, Depends
        map errors     transactions           transaction
```

| Package | Role | SSDS |
| --- | --- | --- |
| `roomly.controller` | One `APIRouter` per use case. Endpoints declare typed path and query parameters and a request DTO, which FastAPI validates; `Depends` resolves the services (`Svc`) and the bearer session (`CurrentUser`). Each endpoint calls one service method and returns a DTO, its declared response model. It holds no business rules. | boundary classes |
| `roomly.service` | One class per use case, with the method signatures the controllers call; docstrings note the SSDS rule where one applies. Each method opens a transaction (`self.db.transaction()`), uses the mappers, applies the rule, and raises `ServiceError` subclasses (`NotFound`, `Forbidden`, `Conflict`, ...), which the controller layer maps to HTTP statuses. | control classes §9.1 |
| `roomly.mapper` | Hand-written SQL, MyBatis style: one mapper per aggregate, and every statement visible in one place. Rows come back as entities. | — |
| `roomly.entity` | One frozen dataclass per table; field names equal column names. | entity classes §9.1 |
| `roomly.dto` | Frozen pydantic models (`dto.base.DTO`) for request and response bodies. Fields declare constraints with `Field(...)` and `StringConstraints` (length, range, pattern); `Email`, `Secret` (not stripped) and `Distinct` (unique items) are shared. Request numbers and booleans are strict (`StrictInt`, `StrictFloat`, `StrictBool`). `check()` holds cross-field rules and reports each problem at its field. | — |
| `roomly.db` | `Database` (primary/fallback selection, migrations) and the engine-neutral `Tx`. | — |

Endpoints and the `current_user` dependency are plain `def`, so FastAPI runs them in its thread pool
and the blocking database calls stay off the event loop. Services are synchronous and use psycopg 3
with a connection pool, or `sqlite3` with one connection per transaction.

## Errors

| Status | Body | When |
| --- | --- | --- |
| 401 | `{"detail": "..."}` plus `WWW-Authenticate: Bearer` | missing, invalid, expired or revoked bearer token |
| 403 | `{"detail": "..."}` | signed in, but not allowed (not a member, not the owner, not an administrator) |
| 404 | `{"detail": "..."}` | not found; also an invitation addressed to someone else, so its existence is never confirmed |
| 409 | `{"detail": "...", "constraint": "name"}` | a rule conflict from a service, or a database invariant that caught a race |
| 422 | `{"detail": [{"loc": ["body", "email"], "msg": "...", "type": "...", "input": ...}]}` | validation of the body, path (`["path", "group_id"]`) or query (`["query", "limit"]`), all problems at once |
| 503 | `{"detail": "the database is unavailable, try again shortly"}` | the database dropped while serving |

## Access checks

Group rules are applied twice on purpose. The service re-reads current membership inside the same
transaction as the action (`service/access.py`: `require_member`, `require_owner`), so a member who
left or was removed on another connection cannot act on a stale page. The database then enforces
what a race could still slip past: at most six current members, one owner, administrators never
members. A violation raised by a trigger is a 409 naming the constraint.

Notification rows are created inside the transaction of the event that causes them
(`service/notification_events.py`), so a message and its alerts commit or roll back together; the
unique `(recipient, kind, event)` key makes a retry a no-op.
