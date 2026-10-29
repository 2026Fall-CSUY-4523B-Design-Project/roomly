-- Roomly schema v1 for the SQLite fallback. Mirrors ../postgres/0001_init.sql table by table
-- with the same names, keys and invariants; change both together (the API suite runs on both).
--
-- SQLite storage
--   * uuid, timestamps (UTC, YYYY-MM-DDTHH:MM:SS.ffffff+00:00), dates and times are TEXT;
--     booleans are INTEGER 0/1; text[] and jsonb columns are JSON text.
--   * gen_random_uuid(), now() and regexp() (Postgres ~ semantics) are registered on every
--     connection by roomly.db.backend, so defaults and checks match the Postgres schema.
--   * Invariants Postgres enforces with plpgsql triggers or subquery checks are triggers here;
--     they RAISE "<constraint name>: <message>" so the API reports the same constraint.
-- Applied by roomly.db.migrate inside one transaction; do not add BEGIN/COMMIT.

-- =====================================================================================
-- Accounts (R-1.1, R-1.4)
-- =====================================================================================

CREATE TABLE app_user (
    id            TEXT PRIMARY KEY DEFAULT (gen_random_uuid()),
    email         TEXT,
    password_hash TEXT,
    display_name  TEXT CHECK (length(display_name) <= 60),
    role          TEXT NOT NULL DEFAULT 'user' CHECK (role IN ('user', 'admin')),
    preferences   TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(preferences)),
    notify_kinds  TEXT NOT NULL DEFAULT '["new_match","price_change","removed","message"]'
                  CHECK (json_valid(notify_kinds) AND json_type(notify_kinds) = 'array'),
    notify_email  INTEGER NOT NULL DEFAULT 1 CHECK (notify_email IN (0, 1)),
    notify_digest INTEGER NOT NULL DEFAULT 0 CHECK (notify_digest IN (0, 1)),
    quiet_start   TEXT,
    quiet_end     TEXT,
    created_at    TEXT NOT NULL DEFAULT (now()),
    updated_at    TEXT NOT NULL DEFAULT (now()),
    deleted_at    TEXT,
    CONSTRAINT app_user_live_has_credentials
        CHECK (deleted_at IS NOT NULL OR (email IS NOT NULL AND password_hash IS NOT NULL)),
    CONSTRAINT app_user_deleted_is_scrubbed
        CHECK (deleted_at IS NULL OR (email IS NULL AND password_hash IS NULL AND display_name IS NULL)),
    CONSTRAINT app_user_email_normalized CHECK (email = lower(trim(email))),
    CONSTRAINT app_user_quiet_hours_pair CHECK ((quiet_start IS NULL) = (quiet_end IS NULL))
);
CREATE UNIQUE INDEX app_user_email_key ON app_user (email);

CREATE TRIGGER app_user_notify_kinds_insert BEFORE INSERT ON app_user
WHEN EXISTS (SELECT 1 FROM json_each(NEW.notify_kinds)
             WHERE value NOT IN ('new_match', 'price_change', 'removed', 'message'))
BEGIN SELECT RAISE(ABORT, 'app_user_notify_kinds_valid: unknown notification kind'); END;

CREATE TRIGGER app_user_notify_kinds_update BEFORE UPDATE OF notify_kinds ON app_user
WHEN EXISTS (SELECT 1 FROM json_each(NEW.notify_kinds)
             WHERE value NOT IN ('new_match', 'price_change', 'removed', 'message'))
BEGIN SELECT RAISE(ABORT, 'app_user_notify_kinds_valid: unknown notification kind'); END;

CREATE TRIGGER app_user_touch AFTER UPDATE ON app_user WHEN NEW.updated_at = OLD.updated_at
BEGIN UPDATE app_user SET updated_at = now() WHERE id = NEW.id; END;

CREATE TABLE user_session (
    id         TEXT PRIMARY KEY DEFAULT (gen_random_uuid()),
    user_id    TEXT NOT NULL REFERENCES app_user (id) ON DELETE CASCADE,
    token_hash BLOB NOT NULL UNIQUE,
    created_at TEXT NOT NULL DEFAULT (now()),
    expires_at TEXT NOT NULL,
    revoked_at TEXT,
    CHECK (expires_at > created_at)
);
CREATE INDEX user_session_user_idx ON user_session (user_id) WHERE revoked_at IS NULL;

-- =====================================================================================
-- Invitation-only groups (R-1.2, R-1.3)
-- =====================================================================================

CREATE TABLE user_group (
    id         TEXT PRIMARY KEY DEFAULT (gen_random_uuid()),
    name       TEXT NOT NULL CHECK (length(trim(name)) BETWEEN 1 AND 80),
    created_at TEXT NOT NULL DEFAULT (now())
);

CREATE TABLE group_membership (
    id        TEXT PRIMARY KEY DEFAULT (gen_random_uuid()),
    group_id  TEXT NOT NULL REFERENCES user_group (id) ON DELETE CASCADE,
    user_id   TEXT NOT NULL REFERENCES app_user (id) ON DELETE CASCADE,
    role      TEXT NOT NULL DEFAULT 'member' CHECK (role IN ('owner', 'member')),
    joined_at TEXT NOT NULL DEFAULT (now()),
    left_at   TEXT,
    CHECK (left_at IS NULL OR left_at >= joined_at)
);
CREATE UNIQUE INDEX group_membership_current_key ON group_membership (group_id, user_id) WHERE left_at IS NULL;
CREATE UNIQUE INDEX group_membership_one_owner_key ON group_membership (group_id) WHERE role = 'owner' AND left_at IS NULL;
CREATE INDEX group_membership_user_idx ON group_membership (user_id) WHERE left_at IS NULL;

CREATE TRIGGER group_membership_eligible BEFORE INSERT ON group_membership
WHEN NEW.left_at IS NULL AND EXISTS (SELECT 1 FROM app_user u
                                     WHERE u.id = NEW.user_id AND (u.role = 'admin' OR u.deleted_at IS NOT NULL))
BEGIN SELECT RAISE(ABORT, 'group_membership_eligible: administrators and deleted accounts cannot be group members'); END;

CREATE TRIGGER group_membership_max_six BEFORE INSERT ON group_membership
WHEN NEW.left_at IS NULL AND (SELECT count(*) FROM group_membership m
                              WHERE m.group_id = NEW.group_id AND m.left_at IS NULL) >= 6
BEGIN SELECT RAISE(ABORT, 'group_membership_max_six: a group has at most 6 current members'); END;

CREATE TABLE group_invitation (
    id           TEXT PRIMARY KEY DEFAULT (gen_random_uuid()),
    group_id     TEXT NOT NULL REFERENCES user_group (id) ON DELETE CASCADE,
    email        TEXT NOT NULL CHECK (email = lower(trim(email))),
    invited_by   TEXT REFERENCES app_user (id) ON DELETE SET NULL,
    status       TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'accepted', 'declined')),
    created_at   TEXT NOT NULL DEFAULT (now()),
    expires_at   TEXT NOT NULL,
    responded_at TEXT,
    CHECK (expires_at > created_at),
    CHECK ((status = 'pending') = (responded_at IS NULL))
);
CREATE INDEX group_invitation_email_idx ON group_invitation (email) WHERE status = 'pending';
CREATE INDEX group_invitation_group_idx ON group_invitation (group_id, created_at DESC);

-- =====================================================================================
-- Listings and provenance (R-2)
-- =====================================================================================

CREATE TABLE listing_source (
    id           TEXT PRIMARY KEY DEFAULT (gen_random_uuid()),
    name         TEXT NOT NULL UNIQUE CHECK (length(trim(name)) BETWEEN 1 AND 80),
    kind         TEXT NOT NULL CHECK (kind IN ('feed', 'url', 'manual')),
    enabled      INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)),
    is_synthetic INTEGER NOT NULL DEFAULT 1 CHECK (is_synthetic IN (0, 1)),
    config       TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(config)),
    last_run_at  TEXT,
    last_error   TEXT,
    created_at   TEXT NOT NULL DEFAULT (now())
);

CREATE TABLE listing (
    id                       TEXT PRIMARY KEY DEFAULT (gen_random_uuid()),
    status                   TEXT NOT NULL DEFAULT 'searchable'
                             CHECK (status IN ('searchable', 'excluded', 'under_review', 'merged', 'removed')),
    merged_into_id           TEXT REFERENCES listing (id),
    title                    TEXT CHECK (length(title) <= 200),
    address_line             TEXT CHECK (length(address_line) <= 200),
    unit                     TEXT CHECK (length(unit) <= 20),
    borough                  TEXT CHECK (borough IN ('manhattan', 'brooklyn', 'queens', 'bronx', 'staten_island')),
    postal_code              TEXT CHECK (postal_code REGEXP '^[0-9]{5}$'),
    latitude                 REAL CHECK (latitude BETWEEN -90 AND 90),
    longitude                REAL CHECK (longitude BETWEEN -180 AND 180),
    advertised_rent_cents    INTEGER CHECK (advertised_rent_cents > 0),
    net_effective_rent_cents INTEGER CHECK (net_effective_rent_cents > 0),
    lease_term_months        INTEGER CHECK (lease_term_months > 0),
    broker_fee_cents         INTEGER CHECK (broker_fee_cents >= 0),
    monthly_fees_cents       INTEGER CHECK (monthly_fees_cents >= 0),
    bedrooms                 INTEGER CHECK (bedrooms >= 0),
    bathrooms                REAL CHECK (bathrooms >= 0),
    area_sqft                INTEGER CHECK (area_sqft > 0),
    move_in_date             TEXT,
    min_lease_days           INTEGER CHECK (min_lease_days > 0),
    amenities                TEXT NOT NULL DEFAULT '[]' CHECK (json_valid(amenities) AND json_type(amenities) = 'array'),
    availability             TEXT NOT NULL DEFAULT 'unknown' CHECK (availability IN ('available', 'unavailable', 'unknown')),
    conflicts                TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(conflicts)),
    is_synthetic             INTEGER NOT NULL DEFAULT 0 CHECK (is_synthetic IN (0, 1)),
    created_at               TEXT NOT NULL DEFAULT (now()),
    updated_at               TEXT NOT NULL DEFAULT (now()),
    CHECK ((latitude IS NULL) = (longitude IS NULL)),
    CHECK ((status = 'merged') = (merged_into_id IS NOT NULL)),
    CHECK (merged_into_id <> id),
    CONSTRAINT listing_searchable_in_scope CHECK (status <> 'searchable' OR (borough IS NOT NULL AND min_lease_days >= 30))
);
CREATE INDEX listing_rent_idx ON listing (advertised_rent_cents) WHERE status = 'searchable';
CREATE INDEX listing_borough_bedrooms_idx ON listing (borough, bedrooms) WHERE status = 'searchable';
CREATE INDEX listing_move_in_idx ON listing (move_in_date) WHERE status = 'searchable';
CREATE INDEX listing_coordinates_idx ON listing (latitude, longitude) WHERE latitude IS NOT NULL;
CREATE INDEX listing_address_idx ON listing (postal_code, lower(address_line), lower(unit));
CREATE INDEX listing_merged_into_idx ON listing (merged_into_id) WHERE merged_into_id IS NOT NULL;

CREATE TRIGGER listing_touch AFTER UPDATE ON listing WHEN NEW.updated_at = OLD.updated_at
BEGIN UPDATE listing SET updated_at = now() WHERE id = NEW.id; END;

CREATE TABLE source_record (
    id           TEXT PRIMARY KEY DEFAULT (gen_random_uuid()),
    source_id    TEXT NOT NULL REFERENCES listing_source (id),
    listing_id   TEXT REFERENCES listing (id),
    external_id  TEXT NOT NULL CHECK (length(external_id) BETWEEN 1 AND 200),
    original_url TEXT CHECK (original_url REGEXP '^https?://'),
    collected_at TEXT NOT NULL,
    raw_values   TEXT NOT NULL CHECK (json_valid(raw_values)),
    submitted_by TEXT REFERENCES app_user (id) ON DELETE SET NULL,
    created_at   TEXT NOT NULL DEFAULT (now()),
    CONSTRAINT source_record_fetch_key UNIQUE (source_id, external_id, collected_at)
);
CREATE INDEX source_record_listing_idx ON source_record (listing_id, collected_at DESC);

CREATE TABLE listing_price_history (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    listing_id       TEXT NOT NULL REFERENCES listing (id),
    source_record_id TEXT UNIQUE REFERENCES source_record (id),
    rent_cents       INTEGER NOT NULL CHECK (rent_cents > 0),
    observed_at      TEXT NOT NULL
);
CREATE INDEX listing_price_history_listing_idx ON listing_price_history (listing_id, observed_at DESC);

CREATE TABLE duplicate_candidate (
    id          TEXT PRIMARY KEY DEFAULT (gen_random_uuid()),
    record_a_id TEXT NOT NULL REFERENCES source_record (id),
    record_b_id TEXT NOT NULL REFERENCES source_record (id),
    confidence  REAL NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    status      TEXT NOT NULL DEFAULT 'queued' CHECK (status IN ('queued', 'merged', 'separate')),
    reviewed_by TEXT REFERENCES app_user (id) ON DELETE SET NULL,
    reviewed_at TEXT,
    created_at  TEXT NOT NULL DEFAULT (now()),
    CHECK (record_a_id <> record_b_id),
    CHECK ((status = 'queued') = (reviewed_at IS NULL))
);
CREATE UNIQUE INDEX duplicate_candidate_pair_key
    ON duplicate_candidate (min(record_a_id, record_b_id), max(record_a_id, record_b_id));
CREATE INDEX duplicate_candidate_queue_idx ON duplicate_candidate (created_at) WHERE status = 'queued';

CREATE TABLE data_report (
    id          TEXT PRIMARY KEY DEFAULT (gen_random_uuid()),
    listing_id  TEXT NOT NULL REFERENCES listing (id),
    reporter_id TEXT REFERENCES app_user (id) ON DELETE SET NULL,
    reason      TEXT NOT NULL CHECK (reason IN ('wrong_merge', 'wrong_value', 'unavailable', 'other')),
    details     TEXT CHECK (length(details) <= 2000),
    status      TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'resolved', 'dismissed')),
    created_at  TEXT NOT NULL DEFAULT (now()),
    resolved_by TEXT REFERENCES app_user (id) ON DELETE SET NULL,
    resolved_at TEXT,
    CHECK ((status = 'open') = (resolved_at IS NULL))
);
CREATE INDEX data_report_open_idx ON data_report (created_at) WHERE status = 'open';

-- =====================================================================================
-- Search, commute and comparison (R-3, R-4)
-- =====================================================================================

CREATE TABLE commute_destination (
    id         TEXT PRIMARY KEY DEFAULT (gen_random_uuid()),
    user_id    TEXT NOT NULL REFERENCES app_user (id) ON DELETE CASCADE,
    label      TEXT NOT NULL CHECK (length(trim(label)) BETWEEN 1 AND 60),
    address    TEXT CHECK (length(address) <= 200),
    latitude   REAL CHECK (latitude BETWEEN -90 AND 90),
    longitude  REAL CHECK (longitude BETWEEN -180 AND 180),
    mode       TEXT NOT NULL DEFAULT 'transit' CHECK (mode IN ('transit', 'walk', 'bike', 'drive')),
    created_at TEXT NOT NULL DEFAULT (now()),
    CHECK ((latitude IS NULL) = (longitude IS NULL))
);
CREATE INDEX commute_destination_user_idx ON commute_destination (user_id);

CREATE TRIGGER commute_destination_max_three BEFORE INSERT ON commute_destination
WHEN (SELECT count(*) FROM commute_destination d WHERE d.user_id = NEW.user_id) >= 3
BEGIN SELECT RAISE(ABORT, 'commute_destination_max_three: a user saves at most 3 commute destinations'); END;

CREATE TABLE saved_search (
    id              TEXT PRIMARY KEY DEFAULT (gen_random_uuid()),
    user_id         TEXT NOT NULL REFERENCES app_user (id) ON DELETE CASCADE,
    name            TEXT NOT NULL CHECK (length(trim(name)) BETWEEN 1 AND 80),
    criteria        TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(criteria)),
    weights         TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(weights)),
    alerts_enabled  INTEGER NOT NULL DEFAULT 1 CHECK (alerts_enabled IN (0, 1)),
    last_matched_at TEXT,
    created_at      TEXT NOT NULL DEFAULT (now()),
    updated_at      TEXT NOT NULL DEFAULT (now())
);
CREATE INDEX saved_search_user_idx ON saved_search (user_id, created_at DESC);

CREATE TRIGGER saved_search_touch AFTER UPDATE ON saved_search WHEN NEW.updated_at = OLD.updated_at
BEGIN UPDATE saved_search SET updated_at = now() WHERE id = NEW.id; END;

CREATE TABLE comparison (
    id        TEXT PRIMARY KEY DEFAULT (gen_random_uuid()),
    saved_by  TEXT REFERENCES app_user (id) ON DELETE SET NULL,
    group_id  TEXT REFERENCES user_group (id) ON DELETE CASCADE,
    title     TEXT CHECK (length(title) <= 120),
    saved_at  TEXT NOT NULL DEFAULT (now()),
    shared_at TEXT,
    CHECK ((shared_at IS NULL) = (group_id IS NULL)),
    UNIQUE (id, group_id)
);
CREATE INDEX comparison_group_idx ON comparison (group_id, shared_at DESC) WHERE group_id IS NOT NULL;
CREATE INDEX comparison_saved_by_idx ON comparison (saved_by, saved_at DESC);

CREATE TABLE comparison_listing (
    comparison_id TEXT NOT NULL REFERENCES comparison (id) ON DELETE CASCADE,
    position      INTEGER NOT NULL CHECK (position BETWEEN 1 AND 4),
    listing_id    TEXT NOT NULL REFERENCES listing (id),
    snapshot      TEXT NOT NULL CHECK (json_valid(snapshot)),
    PRIMARY KEY (comparison_id, position),
    UNIQUE (comparison_id, listing_id)
);

-- =====================================================================================
-- Group discussion and polls (R-5)
-- =====================================================================================

CREATE TABLE message (
    id            TEXT PRIMARY KEY DEFAULT (gen_random_uuid()),
    group_id      TEXT NOT NULL REFERENCES user_group (id) ON DELETE CASCADE,
    author_id     TEXT REFERENCES app_user (id) ON DELETE SET NULL,
    listing_id    TEXT REFERENCES listing (id),
    comparison_id TEXT,
    body          TEXT NOT NULL CHECK (length(trim(body)) BETWEEN 1 AND 4000),
    sent_at       TEXT NOT NULL DEFAULT (now()),
    CHECK ((listing_id IS NOT NULL) + (comparison_id IS NOT NULL) <= 1),
    FOREIGN KEY (comparison_id, group_id) REFERENCES comparison (id, group_id)
);
CREATE INDEX message_group_idx ON message (group_id, sent_at DESC);
CREATE INDEX message_listing_thread_idx ON message (group_id, listing_id, sent_at DESC) WHERE listing_id IS NOT NULL;
CREATE INDEX message_comparison_thread_idx ON message (comparison_id, sent_at DESC) WHERE comparison_id IS NOT NULL;

CREATE TABLE message_reaction (
    message_id TEXT NOT NULL REFERENCES message (id) ON DELETE CASCADE,
    user_id    TEXT NOT NULL REFERENCES app_user (id) ON DELETE CASCADE,
    emoji      TEXT NOT NULL CHECK (length(emoji) BETWEEN 1 AND 16),
    reacted_at TEXT NOT NULL DEFAULT (now()),
    PRIMARY KEY (message_id, user_id)
);

CREATE TABLE poll (
    id         TEXT PRIMARY KEY DEFAULT (gen_random_uuid()),
    group_id   TEXT NOT NULL REFERENCES user_group (id) ON DELETE CASCADE,
    created_by TEXT REFERENCES app_user (id) ON DELETE SET NULL,
    question   TEXT NOT NULL CHECK (length(trim(question)) BETWEEN 1 AND 200),
    state      TEXT NOT NULL DEFAULT 'open' CHECK (state IN ('open', 'closed')),
    created_at TEXT NOT NULL DEFAULT (now()),
    closed_at  TEXT,
    CHECK ((state = 'closed') = (closed_at IS NOT NULL))
);
CREATE INDEX poll_group_idx ON poll (group_id, created_at DESC);

CREATE TABLE poll_option (
    id       TEXT PRIMARY KEY DEFAULT (gen_random_uuid()),
    poll_id  TEXT NOT NULL REFERENCES poll (id) ON DELETE CASCADE,
    position INTEGER NOT NULL CHECK (position BETWEEN 1 AND 4),
    text     TEXT NOT NULL CHECK (length(trim(text)) BETWEEN 1 AND 120),
    UNIQUE (poll_id, position),
    UNIQUE (id, poll_id)
);

CREATE TABLE poll_vote (
    poll_id   TEXT NOT NULL REFERENCES poll (id) ON DELETE CASCADE,
    user_id   TEXT NOT NULL REFERENCES app_user (id) ON DELETE CASCADE,
    option_id TEXT NOT NULL,
    cast_at   TEXT NOT NULL DEFAULT (now()),
    PRIMARY KEY (poll_id, user_id),
    FOREIGN KEY (option_id, poll_id) REFERENCES poll_option (id, poll_id) ON DELETE CASCADE
);

CREATE TRIGGER poll_vote_open_insert BEFORE INSERT ON poll_vote
WHEN EXISTS (SELECT 1 FROM poll p WHERE p.id = NEW.poll_id AND p.state = 'closed')
BEGIN SELECT RAISE(ABORT, 'poll_vote_poll_open: poll is closed'); END;

CREATE TRIGGER poll_vote_open_update BEFORE UPDATE ON poll_vote
WHEN EXISTS (SELECT 1 FROM poll p WHERE p.id = NEW.poll_id AND p.state = 'closed')
BEGIN SELECT RAISE(ABORT, 'poll_vote_poll_open: poll is closed'); END;

-- =====================================================================================
-- Notifications (R-6)
-- =====================================================================================

CREATE TABLE notification (
    id           TEXT PRIMARY KEY DEFAULT (gen_random_uuid()),
    recipient_id TEXT NOT NULL REFERENCES app_user (id) ON DELETE CASCADE,
    kind         TEXT NOT NULL CHECK (kind IN ('new_match', 'price_change', 'removed', 'message')),
    event_id     TEXT NOT NULL,
    group_id     TEXT REFERENCES user_group (id) ON DELETE CASCADE,
    listing_id   TEXT REFERENCES listing (id),
    title        TEXT NOT NULL CHECK (length(title) <= 200),
    status       TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'deferred', 'delivered', 'suppressed')),
    email_status TEXT NOT NULL DEFAULT 'none' CHECK (email_status IN ('none', 'pending', 'sent', 'failed')),
    created_at   TEXT NOT NULL DEFAULT (now()),
    delivered_at TEXT,
    read_at      TEXT,
    CONSTRAINT notification_once_key UNIQUE (recipient_id, kind, event_id)
);
CREATE INDEX notification_inbox_idx ON notification (recipient_id, created_at DESC) WHERE status = 'delivered';
CREATE INDEX notification_email_queue_idx ON notification (created_at) WHERE email_status = 'pending';
