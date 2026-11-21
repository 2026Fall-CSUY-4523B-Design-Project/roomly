-- Support inbox: every message Email Routing hands the Worker, plus a login throttle.
-- Applied by `wrangler d1 migrations apply DB --remote --env <env>` before each deploy.

CREATE TABLE message (
  id            TEXT PRIMARY KEY,
  received_at   TEXT NOT NULL,                 -- ISO 8601 UTC
  envelope_from TEXT NOT NULL,
  envelope_to   TEXT NOT NULL,                 -- the address it was sent to (catch-all shows which one)
  from_name     TEXT NOT NULL DEFAULT '',
  from_address  TEXT NOT NULL DEFAULT '',
  subject       TEXT NOT NULL DEFAULT '',
  body          TEXT NOT NULL DEFAULT '',      -- plain text only; HTML is never stored or rendered
  size          INTEGER NOT NULL,
  attachments   INTEGER NOT NULL DEFAULT 0,    -- counted, not kept
  truncated     INTEGER NOT NULL DEFAULT 0,
  read_at       TEXT
);
CREATE INDEX message_received_idx ON message (received_at DESC);
CREATE INDEX message_to_idx ON message (envelope_to, received_at DESC);

CREATE TABLE login_failure (
  ip TEXT NOT NULL,
  at INTEGER NOT NULL                          -- unix seconds
);
CREATE INDEX login_failure_idx ON login_failure (ip, at);
