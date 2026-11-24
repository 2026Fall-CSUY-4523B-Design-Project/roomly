# Data and the API

## One origin

`next.config.js` rewrites `/api/:path*` to `${ROOMLY_API_URL}/:path*` (default
`http://127.0.0.1:8000`). The browser therefore only ever sees same-origin `/api/...`, in dev and in
prod alike, and no CORS is configured anywhere. Consequences:

- client code calls `"/api/search"`, never `http://127.0.0.1:8000/search`;
- the rewrite is resolved by the Next server at build/start time, so changing `ROOMLY_API_URL`
  requires restarting (and, for `build`/`start`, rebuilding);
- there is no service worker, no `NEXT_PUBLIC_*` backend URL, and no server-side fetch.

## `lib/api.js`

HTTP helpers and endpoint wrappers live here.

`searchListings(filters, { sort = "newest", limit = 20, offset = 0 })` → `GET /api/search`.
Filters are the object from `FilterPanel.toSearchParams`:

| Key | Wire format |
| --- | --- |
| `borough` | repeated query param, one per selected borough |
| `min_rent_cents` / `max_rent_cents` | integer cents; the panel converts the dollars typed |
| `min_bedrooms` | one of `""` (any), `0`…`4` |
| `no_broker_fee` | `true` or omitted |

`null`, `undefined` and `""` values are dropped, so callers can pass the whole filter object.
`sort` is `newest | rent_asc | rent_desc`; `limit`/`offset` are always sent even though nothing pages
yet.

`accountRequest(path, { method = "GET", body, token })` → JSON, or `null` on `204`. Sets
`Content-Type` only when there is a body and `Authorization: Bearer` only when there is a token.
On failure it throws an `Error` carrying `err.status`, with the message derived from FastAPI's body:
a 422 `detail` array becomes `field.sub: message` pairs joined by spaces, a string `detail` is used
as is, anything else falls back to a generic sentence. Add new endpoints here rather than calling
`fetch` from a component.

Note the asymmetry: `searchListings`' internal `get()` throws `GET /search failed with <status>` and
has **no** `.status` property, so it cannot distinguish 401 from 500. Don't build logic on it.

## Real errors, not sample data

Every endpoint now has a real implementation, so a 4xx or 5xx in the UI is a real answer: 401 means
the token is missing/expired, 403 means the account is not allowed, 409 means a rule conflict (the
body may carry `constraint`), 422 is validation. There is no development mode that substitutes
sample data; if a page looks empty, check the API response.

## Matching the DTOs

Field names in the UI come straight from the response DTOs (`ListingSummaryDTO` etc.): snake_case,
integer cents, ISO dates, `null` for unknown. `lib/format.js` owns the display translation — see
[ui.md](ui.md). When a DTO gains a field, render it through a `format*` helper so unknown values keep
their "Unknown" label.

## Listing details and reports

`getListing(id)` reads `GET /listings/{id}` with structured status errors through `accountRequest`.
`reportListing(authenticatedRequest, id, body)` posts `{reason, details}` to the report endpoint
using the authenticated request function supplied by `useAuth()`. IDs are URL-encoded.
