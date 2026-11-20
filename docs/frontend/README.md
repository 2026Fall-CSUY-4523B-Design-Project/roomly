# Frontend

Next.js 12.0.0 (pages router) + React 17, plain JavaScript, one global stylesheet. It talks to the
backend only through same-origin `/api/*`, which `next.config.js` rewrites to `ROOMLY_API_URL`.

```sh
script/frontend.sh dev     # http://localhost:3000
script/frontend.sh build   # the only check: there are no frontend tests or typecheck
script/frontend.sh start   # serve a previous build (prod)
```

`script/run.sh` starts Postgres, the backend and the frontend together. For the API side see
[../backend/README.md](../backend/README.md).

| Page | Contents |
| --- | --- |
| [routing.md](routing.md) | routes, layout, header, loading/empty/error states, what is not built yet |
| [data.md](data.md) | `lib/api.js`, the `/api` rewrite, search parameters, error handling, fixtures |
| [auth.md](auth.md) | `AuthProvider`, `sessionStorage`, restore, expiry, sign-out |
| [ui.md](ui.md) | `globals.css` tokens and classes, `lib/format.js`, accessibility conventions |

## Layout

```
frontend/
  pages/       _app.js (providers + CSS), index.js (dashboard), sign-in.js, sign-up.js
  components/  Header, AuthForm, FilterPanel, ListingCard
  lib/         api.js (HTTP), auth.js (session), format.js (display helpers)
  styles/      globals.css — the whole stylesheet
  next.config.js  /api/* rewrite; jsconfig.json  @/* → frontend/
```

`@/*` resolves to the `frontend/` root, so imports read `@/lib/api`, `@/components/Header`.

## Status

Implemented against the real API: search/dashboard (UC-3), sign-up, sign-in, sign-out, session
restore. Everything else in the navigation — compare, groups, notifications, the listing detail page
— has no route yet and 404s; those links are placeholders for later slices.

In dev the backend answers unimplemented endpoints with **fixture data** rather than 501, so pages
can look complete while the logic is still a stub. See [data.md](data.md#fixtures).

## Conventions

- JavaScript, not TypeScript; function components with hooks; no state library, no data-fetching
  library, no CSS framework.
- All HTTP goes through `lib/api.js`. The browser must never call the backend origin directly; that
  would need CORS and would break the prod reverse-proxy assumption.
- Session state comes from `useAuth()`; no component reads `sessionStorage` itself.
- Rents cross the API boundary as integer cents. Convert in the form, format for display.
- Comments explain the SSDS rule a component implements (e.g. "hard-constraint filters (R-3.1)");
  follow that when adding UI.
