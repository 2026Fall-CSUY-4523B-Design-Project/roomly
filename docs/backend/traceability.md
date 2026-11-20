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

## Tests

`script/backend.sh test` runs all of `backend/tests/`. Database tests are parametrized over both
engines and need a reachable Postgres (see the repo README); they skip locally without one and fail
in CI.

| File | Covers |
| --- | --- |
| `test_auth` | the real HTTP account lifecycle and sessions, on both engines |
| `test_dto` | validation rules, 422 locations, the OpenAPI document |
| `test_fixtures` | a sample for every route, served through FastAPI |
| `test_schema` | DDL invariants, on both engines |
| `test_database` | primary/fallback selection |
| `test_config`, `test_health` | settings and the health payload |

HTTP-level tests use FastAPI's `TestClient`.

## To do

- Remaining service methods, including account deletion, group membership, and access checks such as
  "members only" and "owner only". Account authentication is implemented.
- Pieces the SSDS plans that have no stub yet: the SampleFeed collector job, ranking with explained
  scores (R-3.3), commute routing (R-3.5), live room push, the email/digest worker, importing a
  listing from a URL, personal data export, and the per-member group fit matrix.
- A way to grant the administrator role (today: `UPDATE app_user SET role = 'admin'`).
