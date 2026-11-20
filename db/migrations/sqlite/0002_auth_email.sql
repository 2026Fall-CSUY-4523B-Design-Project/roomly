-- Roomly schema v2 for the SQLite fallback: email verification and password reset.
-- Mirrors ../postgres/0002_auth_email.sql; change both together. Storage conventions are the
-- ones in 0001 (TEXT timestamps from now(), BLOB hashes). Do not add BEGIN/COMMIT.

ALTER TABLE app_user ADD COLUMN email_verified_at TEXT;

-- Accounts that exist today were created before verification did; see the Postgres file.
UPDATE app_user SET email_verified_at = created_at WHERE deleted_at IS NULL;

CREATE TABLE auth_token (
    id          TEXT PRIMARY KEY DEFAULT (gen_random_uuid()),
    user_id     TEXT NOT NULL REFERENCES app_user (id) ON DELETE CASCADE,
    kind        TEXT NOT NULL CHECK (kind IN ('verify_email', 'reset_password')),
    token_hash  BLOB NOT NULL UNIQUE,
    created_at  TEXT NOT NULL DEFAULT (now()),
    expires_at  TEXT NOT NULL,
    consumed_at TEXT,
    CHECK (expires_at > created_at)
);
CREATE INDEX auth_token_user_kind_idx ON auth_token (user_id, kind, created_at DESC);
