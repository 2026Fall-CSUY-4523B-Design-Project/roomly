# Routing and layout

Pages router: one file per route under `pages/`. `pages/_app.js` wraps every page in `AuthProvider` and `ComparisonProvider`
and imports `styles/globals.css` — that is the only place global CSS is loaded.

| Route | File | Purpose |
| --- | --- | --- |
| `/` | `pages/index.js` | Dashboard: filters + matching listings (UC-3, R-3.1). Guests allowed. |
| `/compare` | `pages/compare.js` | Guest preview of 2–4 selected listings; signed-in renters can **Share to group**. |
| `/listings/[id]` | `pages/listings/[id].js` | Guest listing details, provenance, conflicts, price history and signed-in reports. |
| `/groups` | `pages/groups/index.js` | Group directory, creation and incoming invitations. |
| `/groups/[id]` | `pages/groups/[id].js` | Membership, sent invitations, shared comparisons, messages and polls. |
| `/sign-in` | `pages/sign-in.js` | `<AuthForm />` |
| `/sign-up` | `pages/sign-up.js` | `<AuthForm signUp />`; success shows "Check your email" (no session yet) |
| `/verify-email` | `pages/verify-email.js` | target of the emailed link; confirms once on load |
| `/forgot-password` | `pages/forgot-password.js` | asks for a reset link |
| `/reset-password` | `pages/reset-password.js` | target of the reset link; chooses a new password |

The Notifications header link still points to an unimplemented route. Signed-in renters start a listing thread from listing detail via **Discuss with a group**, and a comparison thread from `/compare` via **Share to group**; both open `/groups/[id]` with `?listing=` or `?comparison=` preselecting the thread. Room messages and poll totals can be refreshed on demand.

## Page shape

Each page renders its own `Header` (there is no shared layout component), then `<main>`:

```jsx
<>
  <Head><title>…</title></Head>
  <Header />
  <main className="dashboard">…</main>
</>
```

There is no `_document.js`; Next's default document is used.

## Dashboard (`/`)

Three pieces of state: submitted `filters`, `sort`, and the result `page`. `FilterPanel` keeps its
own draft state and only calls `onApply` on submit — typing does not trigger a search per keystroke.
Any change to `filters` or `sort` refetches through a `useEffect` keyed on both.

The effect guards against out-of-order responses with a `cancelled` flag; preserve that pattern for
any new fetch effect.

Status is a single `"loading" | "ready" | "error"` string, rendered as:

- `loading` → "Loading listings…"
- `error` → "Could not load listings. Is the backend running on :8000?" (the API failure is not
  surfaced per-error; don't add a toast layer for it)
- `ready` with no items → "No listings match these filters."
- `ready` → `.grid` of `ListingCard`

The results bar shows `page.total` from the API, not `items.length`; pagination fields exist in the
response (`limit`/`offset` are always sent) but there is no pager UI yet.

## Header

`components/Header.js` renders the brand, the four nav links, and the account slot:

- `loading` → "Checking session…"
- signed in → display name or email + a Sign out button (`pending` disables it)
- signed out → a Sign in button

Auth errors surface as an inline `role="alert"` span next to the nav rather than as a redirect.

## Listing detail

`/listings/[id]` fetches the guest listing card through `getListing`. Loading, missing/invalid IDs,
retryable errors and route changes are handled without retaining the previous listing. The page
shows costs, lease terms, amenities, sources with HTTP(S) links and collection times, conflicting
values, price history, and monthly rent per square foot. Null values remain Unknown, and
merged listings link to the surviving listing. Money is displayed with cent precision.

`ListingReport` offers signed-in users the four API report reasons and optional details (up to
2,000 characters), with pending, success and error states. Guests get a sign-in link. Requests
use `useAuth().authenticatedRequest`, which supplies the session token and clears expired sessions
on a 401 without components accessing browser storage.

## Guest comparison

`ComparisonProvider` retains up to four unique listing IDs and display titles across routes and
stores them in per-tab `sessionStorage` under `roomly.comparison`. If storage is unavailable,
selection still works in memory. Search cards and listing details offer a toggle; at four selections,
unselected toggles are disabled. The shared header shows the count, selected listings, removal and
clear controls, and a link to `/compare`.

`/compare` requests a fresh preview when at least two listings are selected. Empty/one-listing states,
loading, retryable errors and missing listings keep selection controls available. Old responses are
ignored after selection changes. The table uses API `known`, `best`, and direction fields; bathrooms,
amenities and availability are additional unranked rows from the returned listing summaries. The
region scrolls horizontally on narrow screens and supports keyboard focus. Saving and sharing
comparisons remain future slices.
