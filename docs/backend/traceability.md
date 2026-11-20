# Traceability and tests

Every SSDS use case has the same four pieces, one per layer:

| Use case | Controller | Service | Mapper | DTOs |
| --- | --- | --- | --- | --- |
| §8.1.2.1 Login | `account_controller` | `AccountService` | `account_mapper` | `dto/account` |
| §8.1.2.2 Group Management | `group_controller` | `GroupService` | `group_mapper` | `dto/group` |
| §8.1.2.3 Listing Submission | `listing_controller` | `ListingService` | `listing_mapper` | `dto/listing` |
| §8.1.2.4 Listing Administration | `admin_controller` | `AdminService` | `listing_mapper` | `dto/admin` |
| §8.1.2.5 Search and Ranking | `search_controller` | `SearchService` | `search_mapper`, `listing_mapper` | `dto/search` |
| §8.1.2.6 Comparison | `comparison_controller` | `ComparisonService` | `comparison_mapper` | `dto/comparison` |
| §8.1.2.7 Group Discussion | `room_controller` | `RoomService` | `room_mapper` | `dto/room` |
| §8.1.2.8 Notifications | `notification_controller` | `NotificationService` | `notification_mapper` | `dto/notification` |

`service/access.py` holds the current-membership check every group, comparison and room action
re-runs inside its transaction. `service/notification_events.py` creates message alerts in the
posting transaction, so the message and its notifications commit together.

## Tests

`script/backend.sh test` runs all of `backend/tests/`. Database tests are parametrized over both
engines and need a reachable Postgres (see the repo README); they skip locally without one and fail
in CI.

| File | Covers |
| --- | --- |
| `test_services` | every use case through HTTP: groups, listings, admin review, search, comparison, rooms, notifications, account deletion |
| `test_auth` | the account lifecycle and sessions, on both engines |
| `test_dto` | validation rules, 422 locations, the OpenAPI document |
| `test_schema` | DDL invariants, on both engines |
| `test_database` | primary/fallback selection |
| `test_config`, `test_health` | settings and the health payload |

HTTP-level tests use FastAPI's `TestClient`.

## Remaining work

- The SampleFeed collector job and its source adapters, so listings arrive without manual entry.
- Explained ranking scores (R-3.3) and commute routing (R-3.5); search currently orders by the
  requested sort and commute columns stay Unknown.
- Live room push over WebSocket (R-5) and the email/digest worker behind
  `notification.email_status = 'pending'`.
- Importing a listing from a URL, personal data export, and the per-member group fit matrix.
- A way to grant the administrator role (today: `UPDATE app_user SET role = 'admin'`).
