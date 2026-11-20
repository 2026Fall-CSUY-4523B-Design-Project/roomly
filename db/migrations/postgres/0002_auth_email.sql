-- Roomly schema v2 (PostgreSQL): email verification and password reset.
-- Mirrors ../sqlite/0002_auth_email.sql; change both together.
--
-- Rollback-safe: the column is nullable and the table is new, so the previous release still
-- starts against this schema (it simply never reads them).

ALTER TABLE app_user ADD COLUMN email_verified_at timestamptz;

-- Accounts that exist today were created before verification did, and sign-in now requires it.
-- Treat them as verified when they signed up, otherwise the release locks every current user out.
UPDATE app_user SET email_verified_at = created_at WHERE deleted_at IS NULL;

-- One row per emailed link. Only the sha256 of the token is stored (as for user_session), so a
-- database read cannot be turned into a working link. A link works once: consumed_at is set by
-- the same UPDATE that checks it.
CREATE TABLE auth_token (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     uuid NOT NULL REFERENCES app_user (id) ON DELETE CASCADE,
    kind        text NOT NULL CHECK (kind IN ('verify_email', 'reset_password')),
    token_hash  bytea NOT NULL UNIQUE,
    created_at  timestamptz NOT NULL DEFAULT now(),
    expires_at  timestamptz NOT NULL,
    consumed_at timestamptz,
    CHECK (expires_at > created_at)
);
-- Serves the send throttle: "how many links of this kind did this user ask for recently".
CREATE INDEX auth_token_user_kind_idx ON auth_token (user_id, kind, created_at DESC);
