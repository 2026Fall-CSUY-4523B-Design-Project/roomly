# roomly-mail

The Cloudflare Worker behind `mail.roomly.bid`. It does two jobs:

- **Outbound.** `POST /v1/send` renders one of the transactional templates and hands it to the
  Email Service `send_email` binding. The API signs each request; nothing else can use the endpoint.
- **Inbound.** Email Routing delivers every message addressed to `@roomly.bid` to the Worker's
  `email()` handler, which stores it in D1. Human mail is also forwarded to `SUPPORT_INBOX` when that
  optional secret is set; bounces and DMARC traffic are not (`src/inbound.ts`).
- **Inbox.** `https://mail.roomly.bid/` is a password-protected web inbox over the stored mail
  (`src/inbox/`): list, search, per-recipient filter, read, delete. Plain text only.

Deployment, DNS and secrets are in [../docs/deploy.md](../docs/deploy.md).

## Layout

```
src/index.ts      fetch + email handlers, request validation, error codes
src/sign.ts       HMAC-SHA256 over `<timestamp>.<body>`, five-minute window
src/templates.ts  verify_email / reset_password, text and HTML
src/inbound.ts    which inbound mail is also forwarded to a private mailbox
src/inbox/        D1 store, MIME ingest, login session, pages and routes of the web inbox
migrations/       D1 schema, applied by `wrangler d1 migrations apply`
test/             vitest, no network and no Cloudflare account needed (inbox SQL runs on node:sqlite)
```

## API

`POST /v1/send`, signed by the API:

```
X-Roomly-Timestamp: 1763680000
X-Roomly-Signature: v1=<hex hmac-sha256 of "1763680000." + body>

{"template": "verify_email", "to": "maya@example.com", "data": {"token": "…", "display_name": "Maya"}}
```

`202 {"transport":"email","template":"verify_email","to":"…","id":"<message id>"}` on success.
`401` for a bad or stale signature, `403` when `MAIL_ALLOWED_RECIPIENTS` excludes the recipient,
`422` for an unknown template, a malformed address or an invalid token, `502` when Email Service
rejects the message. Errors are `{"error":{"code":"…","message":"…"}}`.

`GET /healthz` answers without touching the mail binding.

## Local development

```sh
cp .dev.vars.example .dev.vars   # MAIL_TRANSPORT=console prints instead of sending
pnpm install
pnpm test          # vitest
pnpm typecheck
pnpm dev           # http://127.0.0.1:8787
```

`MAIL_TRANSPORT=console` still verifies the signature, so exercise the endpoint with a real HMAC.
With `wrangler dev`, the `send_email` binding is local by default; run `wrangler dev --remote` when
you need the real Email Service.

## Deploy

```sh
pnpm deploy:dry-run        # bundle only, no account needed
pnpm deploy:staging        # roomly-mail-staging, staging-mail.roomly.bid
pnpm deploy:production     # roomly-mail, mail.roomly.bid
```

CI runs all three (`--dry-run` on every pull request, staging from `main`, production from a `v*`
tag). `MAIL_SECRET` is a Worker secret, not a var: `wrangler secret put MAIL_SECRET --env production`.
