# Routing and layout

Pages router: one file per route under `pages/`. `pages/_app.js` wraps every page in `AuthProvider`
and imports `styles/globals.css` — that is the only place global CSS is loaded.

| Route | File | Purpose |
| --- | --- | --- |
| `/` | `pages/index.js` | Dashboard: filters + matching listings (UC-3, R-3.1). Guests allowed. |
| `/sign-in` | `pages/sign-in.js` | `<AuthForm />` |
| `/sign-up` | `pages/sign-up.js` | `<AuthForm signUp />`; success shows "Check your email" (no session yet) |
| `/verify-email` | `pages/verify-email.js` | target of the emailed link; confirms once on load |
| `/forgot-password` | `pages/forgot-password.js` | asks for a reset link |
| `/reset-password` | `pages/reset-password.js` | target of the reset link; chooses a new password |

No other routes exist. `Header` links to `/compare`, `/groups` and `/notifications`, and
`ListingCard` links to `/listings/<id>`; all four 404 until those slices land. When adding one, add
the page and keep the header link — the navigation is the product spec.

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
