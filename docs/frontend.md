# Frontend

Next.js 12 (pages router) with React 17 and plain JavaScript, managed by pnpm. The browser talks only to same-origin `/api/*`; `next.config.js` rewrites those requests to the backend (`ROOMLY_API_URL`, default `http://127.0.0.1:8000`).

```sh
script/frontend.sh dev     # :3000, with the backend on :8000
script/frontend.sh test    # node:test unit tests for lib/
script/frontend.sh build   # production build (CI runs test + build)
```

## Layout

```
frontend/
  pages/          one file per route (see below); _app wraps every page in Layout
  components/     Layout (header, nav, account), ListingCard, SprintNotice, Field, Seats, SignInPrompt
  lib/
    api.js        fetch client: /api prefix, bearer token, ApiError, percent-encoded query strings
    auth.js       the session in localStorage (in memory when storage is blocked), safeNext()
    useSession.js React hook: { session, ready }
    format.js     money in cents, Unknown labels, boroughs, dates
  styles/         globals.css (design tokens, primitives) and one CSS module per page family
  tests/          node:test files for lib/
  public/         favicon
```

## Routes

| Route | State |
| --- | --- |
| `/` | Search: borough chips, max rent, bedrooms, no broker fee and sort, with listing cards from `GET /search` |
| `/listings/[id]` | Listing card: every value labeled as known or Unknown, sources, conflicts, price history |
| `/sign-up`, `/sign-in` | Working; `?next=` accepts same-site paths only |
| `/groups` | Your groups, invitations for you (join or decline), create a group |
| `/groups/[id]` | Members, invite (owner), make owner or remove a member (owner), sent invitations, leave or dissolve |
| `/compare` | Shell: the comparison table lands in Sprint 4 (the API is ready) |
| `/notifications` | Shell: the inbox and settings land in Sprint 5 |
| `/admin` | Administrators only. Shell: the duplicate queue lands in Sprint 4; source management in Sprint 3 |

A screen that is not built shows a `SprintNotice`: the sprint and its dates from the SSDS plan, what the screen will do, and the endpoints it will call. It never presents placeholder data as real.

## Conventions

- **Unknown is a label.** `format.js` turns `null` into "Unknown" (or "Unknown beds" and so on), and the UI sets it in muted italics. Filters never treat Unknown as a match.
- **Money is integer cents** end to end. `dollarsToCents()` parses what a person types.
- **Errors**: `ApiError.message` is safe to show. `ApiError.fields` maps 422 items to form fields, so `Field` shows each message under its input. A 401 on a signed-in call clears the session.
- **Query strings are percent-encoded** (`query()`); a raw `+` in a timestamp cursor would otherwise reach the server as a space.
- **Design tokens** live on `:root` in `globals.css`, with a dark palette under `prefers-color-scheme: dark`. The accent (brick) marks actions and the sprint notices; green is reserved for "good" (best value, joined, net-effective rent).
- Logging uses `console.warn` and `console.error` with a `[roomly]` prefix. Bodies of 422 responses are never logged, because they echo the submitted input, passwords included.
