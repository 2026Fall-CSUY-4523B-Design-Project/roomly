# Authentication

A thin browser layer over the backend's bearer sessions. Plain passwords never leave the form until
`POST /auth/sign-*`; the browser stores only the opaque token.

## Endpoints used

| Call | Body / result |
| --- | --- |
| `POST /auth/sign-up` | `{email, password, display_name?}` → `{email, verification_sent}`; no session |
| `POST /auth/verify-email` | `{token}` → `204` |
| `POST /auth/verify-email/resend`, `/auth/forgot-password` | `{email}` → `202`, identical for every address |
| `POST /auth/reset-password` | `{token, password}` → `204`; every session of the account is revoked |
| `POST /auth/sign-in` | `{email, password}` → `{token, expires_at, user}`; `403` + `code: "email_not_verified"` before confirmation |
| `POST /auth/sign-out` | bearer token → `204` |
| `GET /me` | bearer token → user |

Sessions last seven days server-side; sign-out revokes only the current session.

## `AuthProvider` (`lib/auth.js`)

Mounted in `_app.js`, so every page shares one `AuthContext`. It exposes
`{ user, loading, error, signIn, signOut }` — no token, by design: components never touch it.

State: `session` (`{token, expires_at, user}`), `loading` (true until the restore attempt settles),
`error` (a user-facing string, rendered inline by callers).

Storage: `sessionStorage["roomly.session"]` holding `{token, expires_at}` — deliberately **not** the
user, which is re-fetched from `/me` on load. `sessionStorage` is per tab: a new tab starts signed
out, closing the tab drops the token (the server session survives; there is no cross-tab sync).

## Lifecycle

1. **Restore (once, on mount).** Parse storage. No entry, or missing token, or `expires_at` already
   past → remove it and stop (still `loading` until then). Otherwise `GET /me` with the token; on
   success set the session, on `401` or unparseable JSON remove the entry, on any other error show
   "Could not restore your session. Please reload to try again."
2. **Expiry timer.** When a session exists, a `setTimeout` fires at `expires_at`, clears storage and
   sets "Your session has expired. Please sign in again." The timer is cleared on any session change.
3. **Sign in.** `signIn(path, body)` posts, writes `{token, expires_at}` to storage, then stores the
   whole response (`user` included). If storage throws (private mode, storage disabled) it revokes
   the freshly created server session and throws "Allow browser session storage to sign in." — keep
   that cleanup if you refactor.
4. **Sign out.** `POST /auth/sign-out` first, then clear. A `401` also clears (the token was already
   dead); any other failure keeps the session and surfaces "Could not sign out. Please try again."

`AuthForm` uses `loading` to show "Checking session…" instead of the form, and redirects to `/` with
`router.replace` after a successful submit; a signed-in visitor sees "You are signed in as …"
instead of the form.

## Email confirmation and password reset

- **Sign-up creates no session.** `AuthForm` shows "Check your email" with `ResendVerification`; the
  user signs in after opening the link. A sign-in answered `403 email_not_verified` shows the same
  panel (identified by `err.code`, which `accountRequest` copies from `detail.code`).
- **Token pages** (`/verify-email`, `/reset-password`) read `?token=` once through `useUrlToken`
  (`lib/token.js`), then replace the URL with the bare path (shallow) so the token leaves the address
  bar, history and later `Referer`. Both send `Referrer-Policy: no-referrer` (`next.config.js`) and a
  `<meta name="referrer">`. `/verify-email` calls the API once per load (a ref guards the call; the
  token is single-use).
- **Send-a-link calls answer the same for every address**, so the copy says "If an account exists…"
  and never "we sent"; keep it that way.

## Rules when extending

- Read auth through `useAuth()`; don't read or write `sessionStorage` elsewhere.
- Protected calls take the token from context and go through `accountRequest(..., { token })`.
- Auth failures are shown inline (`role="alert"`), not as redirects; only the auth pages redirect.
- Sign-up enforces 8–128 characters client-side (`minLength`), but the server is the authority —
  don't duplicate the remaining rules in the form.
