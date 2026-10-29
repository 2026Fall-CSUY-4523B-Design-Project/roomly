-- Roomly schema v1, derived from SSDS-001 v2.0 §9.1 (entity classes and cardinalities).
--
-- Conventions
--   * Listing attributes use NULL for "Unknown" (§3 glossary): NULL is never 0, false or "none".
--   * Enumerations are text + CHECK, so adding a value is a one-line migration.
--   * Money is integer cents (USD). Times are timestamptz.
--   * Rules the SSDS states as hard invariants are enforced here as well as in the services:
--     1..6 current members per group, admins never members, at most 3 commute destinations,
--     one reaction per user per message, one vote per member per poll, no votes on closed polls,
--     one notification per recipient per event, searchable listings are NYC rentals of 30+ days.
-- Applied by roomly.db.migrate inside one transaction; do not add BEGIN/COMMIT.

CREATE FUNCTION touch_updated_at() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at := now();
    RETURN NEW;
END $$;

-- =====================================================================================
-- Accounts (R-1.1, R-1.4)
-- =====================================================================================

CREATE TABLE app_user (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    email         text,
    password_hash text,
    display_name  text CHECK (char_length(display_name) <= 60),
    role          text NOT NULL DEFAULT 'user' CHECK (role IN ('user', 'admin')),
    preferences   jsonb NOT NULL DEFAULT '{}'::jsonb,         -- stated ranking preferences (R-3.4)
    notify_kinds  text[] NOT NULL DEFAULT '{new_match,price_change,removed,message}',
    notify_email  boolean NOT NULL DEFAULT true,
    notify_digest boolean NOT NULL DEFAULT false,
    quiet_start   time,
    quiet_end     time,
    created_at    timestamptz NOT NULL DEFAULT now(),
    updated_at    timestamptz NOT NULL DEFAULT now(),
    deleted_at    timestamptz,
    -- A deleted account keeps its id so shared content can say "Deleted user", but no personal data.
    CONSTRAINT app_user_live_has_credentials
        CHECK (deleted_at IS NOT NULL OR (email IS NOT NULL AND password_hash IS NOT NULL)),
    CONSTRAINT app_user_deleted_is_scrubbed
        CHECK (deleted_at IS NULL OR (email IS NULL AND password_hash IS NULL AND display_name IS NULL)),
    CONSTRAINT app_user_email_normalized CHECK (email = lower(btrim(email))),
    CONSTRAINT app_user_quiet_hours_pair CHECK ((quiet_start IS NULL) = (quiet_end IS NULL)),
    CONSTRAINT app_user_notify_kinds_valid
        CHECK (notify_kinds <@ ARRAY['new_match', 'price_change', 'removed', 'message']::text[])
);
CREATE UNIQUE INDEX app_user_email_key ON app_user (email);  -- deleted accounts have NULL email
CREATE TRIGGER app_user_touch BEFORE UPDATE ON app_user FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

CREATE TABLE user_session (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id    uuid NOT NULL REFERENCES app_user (id) ON DELETE CASCADE,
    token_hash bytea NOT NULL UNIQUE,   -- sha256 of the bearer token; the token itself is never stored
    created_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz NOT NULL,
    revoked_at timestamptz,
    CHECK (expires_at > created_at)
);
CREATE INDEX user_session_user_idx ON user_session (user_id) WHERE revoked_at IS NULL;

-- =====================================================================================
-- Invitation-only groups (R-1.2, R-1.3)
-- =====================================================================================

CREATE TABLE user_group (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name       text NOT NULL CHECK (char_length(btrim(name)) BETWEEN 1 AND 80),
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE group_membership (
    id        uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    group_id  uuid NOT NULL REFERENCES user_group (id) ON DELETE CASCADE,
    user_id   uuid NOT NULL REFERENCES app_user (id) ON DELETE CASCADE,
    role      text NOT NULL DEFAULT 'member' CHECK (role IN ('owner', 'member')),
    joined_at timestamptz NOT NULL DEFAULT now(),
    left_at   timestamptz,               -- NULL = current member; history rows are kept
    CHECK (left_at IS NULL OR left_at >= joined_at)
);
CREATE UNIQUE INDEX group_membership_current_key ON group_membership (group_id, user_id) WHERE left_at IS NULL;
CREATE UNIQUE INDEX group_membership_one_owner_key ON group_membership (group_id) WHERE role = 'owner' AND left_at IS NULL;
CREATE INDEX group_membership_user_idx ON group_membership (user_id) WHERE left_at IS NULL;

-- Group 1 -- 1..6 Membership; Administrator has no association with Group (§9.1.3).
CREATE FUNCTION check_group_membership() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.left_at IS NOT NULL THEN
        RETURN NEW;
    END IF;
    IF EXISTS (SELECT 1 FROM app_user u WHERE u.id = NEW.user_id AND (u.role = 'admin' OR u.deleted_at IS NOT NULL)) THEN
        RAISE EXCEPTION 'administrators and deleted accounts cannot be group members'
            USING ERRCODE = 'check_violation', CONSTRAINT = 'group_membership_eligible';
    END IF;
    PERFORM 1 FROM user_group g WHERE g.id = NEW.group_id FOR UPDATE;  -- serialize joins per group
    IF (SELECT count(*) FROM group_membership m
        WHERE m.group_id = NEW.group_id AND m.left_at IS NULL AND m.id <> NEW.id) >= 6 THEN
        RAISE EXCEPTION 'a group has at most 6 current members'
            USING ERRCODE = 'check_violation', CONSTRAINT = 'group_membership_max_six';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER group_membership_check BEFORE INSERT ON group_membership
    FOR EACH ROW EXECUTE FUNCTION check_group_membership();

CREATE TABLE group_invitation (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    group_id     uuid NOT NULL REFERENCES user_group (id) ON DELETE CASCADE,
    email        text NOT NULL CHECK (email = lower(btrim(email))),
    invited_by   uuid REFERENCES app_user (id) ON DELETE SET NULL,
    status       text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'accepted', 'declined')),
    created_at   timestamptz NOT NULL DEFAULT now(),
    expires_at   timestamptz NOT NULL,   -- "expired" = pending and past expires_at (derived)
    responded_at timestamptz,
    CHECK (expires_at > created_at),
    CHECK ((status = 'pending') = (responded_at IS NULL))
);
CREATE INDEX group_invitation_email_idx ON group_invitation (email) WHERE status = 'pending';
CREATE INDEX group_invitation_group_idx ON group_invitation (group_id, created_at DESC);

-- =====================================================================================
-- Listings and provenance (R-2)
-- =====================================================================================

CREATE TABLE listing_source (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name         text NOT NULL UNIQUE CHECK (char_length(btrim(name)) BETWEEN 1 AND 80),
    kind         text NOT NULL CHECK (kind IN ('feed', 'url', 'manual')),
    enabled      boolean NOT NULL DEFAULT true,
    is_synthetic boolean NOT NULL DEFAULT true,          -- Release 1 feeds are synthetic
    config       jsonb NOT NULL DEFAULT '{}'::jsonb,     -- adapter settings; never credentials
    last_run_at  timestamptz,
    last_error   text,
    created_at   timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE listing (
    id                       uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    status                   text NOT NULL DEFAULT 'searchable'
                             CHECK (status IN ('searchable', 'excluded', 'under_review', 'merged', 'removed')),
    merged_into_id           uuid REFERENCES listing (id),
    title                    text CHECK (char_length(title) <= 200),
    address_line             text CHECK (char_length(address_line) <= 200),
    unit                     text CHECK (char_length(unit) <= 20),
    borough                  text CHECK (borough IN ('manhattan', 'brooklyn', 'queens', 'bronx', 'staten_island')),
    postal_code              text CHECK (postal_code ~ '^[0-9]{5}$'),
    latitude                 double precision CHECK (latitude BETWEEN -90 AND 90),
    longitude                double precision CHECK (longitude BETWEEN -180 AND 180),
    advertised_rent_cents    integer CHECK (advertised_rent_cents > 0),     -- monthly, as advertised
    net_effective_rent_cents integer CHECK (net_effective_rent_cents > 0),  -- only with a known concession
    lease_term_months        smallint CHECK (lease_term_months > 0),
    broker_fee_cents         integer CHECK (broker_fee_cents >= 0),
    monthly_fees_cents       integer CHECK (monthly_fees_cents >= 0),
    bedrooms                 smallint CHECK (bedrooms >= 0),                -- 0 = studio
    bathrooms                numeric(3, 1) CHECK (bathrooms >= 0),
    area_sqft                integer CHECK (area_sqft > 0),                 -- nonpositive areas are stored as Unknown
    move_in_date             date,
    min_lease_days           integer CHECK (min_lease_days > 0),
    amenities                text[] NOT NULL DEFAULT '{}',                  -- as reported; absence is not "no"
    availability             text NOT NULL DEFAULT 'unknown' CHECK (availability IN ('available', 'unavailable', 'unknown')),
    conflicts                jsonb NOT NULL DEFAULT '{}'::jsonb,            -- field -> [{source_record_id, value}]
    is_synthetic             boolean NOT NULL DEFAULT false,
    created_at               timestamptz NOT NULL DEFAULT now(),
    updated_at               timestamptz NOT NULL DEFAULT now(),
    CHECK ((latitude IS NULL) = (longitude IS NULL)),
    CHECK ((status = 'merged') = (merged_into_id IS NOT NULL)),
    CHECK (merged_into_id <> id),
    -- R-2.1: only identified rentals of 30+ days inside the five boroughs may appear in search.
    CONSTRAINT listing_searchable_in_scope CHECK (status <> 'searchable' OR (borough IS NOT NULL AND min_lease_days >= 30))
);
CREATE INDEX listing_rent_idx ON listing (advertised_rent_cents) WHERE status = 'searchable';
CREATE INDEX listing_borough_bedrooms_idx ON listing (borough, bedrooms) WHERE status = 'searchable';
CREATE INDEX listing_move_in_idx ON listing (move_in_date) WHERE status = 'searchable';
CREATE INDEX listing_amenities_idx ON listing USING gin (amenities);
CREATE INDEX listing_coordinates_idx ON listing (latitude, longitude) WHERE latitude IS NOT NULL;
CREATE INDEX listing_address_idx ON listing (postal_code, lower(address_line), lower(unit));
CREATE INDEX listing_merged_into_idx ON listing (merged_into_id) WHERE merged_into_id IS NOT NULL;
CREATE TRIGGER listing_touch BEFORE UPDATE ON listing FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

-- Listing 1 -- 1..* SourceRecord; ListingSource 1 -- 0..* SourceRecord.
CREATE TABLE source_record (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id    uuid NOT NULL REFERENCES listing_source (id),
    listing_id   uuid REFERENCES listing (id),
    external_id  text NOT NULL CHECK (char_length(external_id) BETWEEN 1 AND 200),  -- the id at the source
    original_url text CHECK (original_url ~ '^https?://'),
    collected_at timestamptz NOT NULL,
    raw_values   jsonb NOT NULL,
    submitted_by uuid REFERENCES app_user (id) ON DELETE SET NULL,  -- URL / manual submissions
    created_at   timestamptz NOT NULL DEFAULT now(),
    -- R-2.4: a retried fetch (same source, id and collection time) is recognized, never duplicated.
    CONSTRAINT source_record_fetch_key UNIQUE (source_id, external_id, collected_at)
);
CREATE INDEX source_record_listing_idx ON source_record (listing_id, collected_at DESC);

CREATE TABLE listing_price_history (
    id               bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    listing_id       uuid NOT NULL REFERENCES listing (id),
    source_record_id uuid UNIQUE REFERENCES source_record (id),
    rent_cents       integer NOT NULL CHECK (rent_cents > 0),
    observed_at      timestamptz NOT NULL
);
CREATE INDEX listing_price_history_listing_idx ON listing_price_history (listing_id, observed_at DESC);

-- DuplicateCandidate 1 -- 2 SourceRecord.
CREATE TABLE duplicate_candidate (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    record_a_id uuid NOT NULL REFERENCES source_record (id),   -- the record already in a listing
    record_b_id uuid NOT NULL REFERENCES source_record (id),   -- the newcomer held for review
    confidence  real NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    status      text NOT NULL DEFAULT 'queued' CHECK (status IN ('queued', 'merged', 'separate')),
    reviewed_by uuid REFERENCES app_user (id) ON DELETE SET NULL,
    reviewed_at timestamptz,
    created_at  timestamptz NOT NULL DEFAULT now(),
    CHECK (record_a_id <> record_b_id),
    CHECK ((status = 'queued') = (reviewed_at IS NULL))
);
CREATE UNIQUE INDEX duplicate_candidate_pair_key
    ON duplicate_candidate (LEAST(record_a_id, record_b_id), GREATEST(record_a_id, record_b_id));
CREATE INDEX duplicate_candidate_queue_idx ON duplicate_candidate (created_at) WHERE status = 'queued';

-- Data reports from users, handled in Listing Administration (§8.1.2.4).
CREATE TABLE data_report (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    listing_id  uuid NOT NULL REFERENCES listing (id),
    reporter_id uuid REFERENCES app_user (id) ON DELETE SET NULL,
    reason      text NOT NULL CHECK (reason IN ('wrong_merge', 'wrong_value', 'unavailable', 'other')),
    details     text CHECK (char_length(details) <= 2000),
    status      text NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'resolved', 'dismissed')),
    created_at  timestamptz NOT NULL DEFAULT now(),
    resolved_by uuid REFERENCES app_user (id) ON DELETE SET NULL,
    resolved_at timestamptz,
    CHECK ((status = 'open') = (resolved_at IS NULL))
);
CREATE INDEX data_report_open_idx ON data_report (created_at) WHERE status = 'open';

-- =====================================================================================
-- Search, commute and comparison (R-3, R-4)
-- =====================================================================================

-- User 1 -- 0..3 CommuteDestination.
CREATE TABLE commute_destination (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id    uuid NOT NULL REFERENCES app_user (id) ON DELETE CASCADE,
    label      text NOT NULL CHECK (char_length(btrim(label)) BETWEEN 1 AND 60),
    address    text CHECK (char_length(address) <= 200),
    latitude   double precision CHECK (latitude BETWEEN -90 AND 90),     -- NULL until geocoded
    longitude  double precision CHECK (longitude BETWEEN -180 AND 180),
    mode       text NOT NULL DEFAULT 'transit' CHECK (mode IN ('transit', 'walk', 'bike', 'drive')),
    created_at timestamptz NOT NULL DEFAULT now(),
    CHECK ((latitude IS NULL) = (longitude IS NULL))
);
CREATE INDEX commute_destination_user_idx ON commute_destination (user_id);

CREATE FUNCTION check_commute_destination_limit() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    PERFORM 1 FROM app_user u WHERE u.id = NEW.user_id FOR UPDATE;  -- serialize per user
    IF (SELECT count(*) FROM commute_destination d WHERE d.user_id = NEW.user_id) >= 3 THEN
        RAISE EXCEPTION 'a user saves at most 3 commute destinations'
            USING ERRCODE = 'check_violation', CONSTRAINT = 'commute_destination_max_three';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER commute_destination_limit BEFORE INSERT ON commute_destination
    FOR EACH ROW EXECUTE FUNCTION check_commute_destination_limit();

CREATE TABLE saved_search (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         uuid NOT NULL REFERENCES app_user (id) ON DELETE CASCADE,
    name            text NOT NULL CHECK (char_length(btrim(name)) BETWEEN 1 AND 80),
    criteria        jsonb NOT NULL DEFAULT '{}'::jsonb,
    weights         jsonb NOT NULL DEFAULT '{}'::jsonb,
    alerts_enabled  boolean NOT NULL DEFAULT true,
    last_matched_at timestamptz,          -- watermark for new-match alerts (R-6.1)
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX saved_search_user_idx ON saved_search (user_id, created_at DESC);
CREATE TRIGGER saved_search_touch BEFORE UPDATE ON saved_search FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

-- Comparison 1 -- 2..4 Listing (ordered); Group 1 -- 0..* Comparison (shares).
CREATE TABLE comparison (
    id        uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    saved_by  uuid REFERENCES app_user (id) ON DELETE SET NULL,
    group_id  uuid REFERENCES user_group (id) ON DELETE CASCADE,
    title     text CHECK (char_length(title) <= 120),
    saved_at  timestamptz NOT NULL DEFAULT now(),
    shared_at timestamptz,
    CHECK ((shared_at IS NULL) = (group_id IS NULL)),
    UNIQUE (id, group_id)                 -- target of message's same-group foreign key
);
CREATE INDEX comparison_group_idx ON comparison (group_id, shared_at DESC) WHERE group_id IS NOT NULL;
CREATE INDEX comparison_saved_by_idx ON comparison (saved_by, saved_at DESC);

CREATE TABLE comparison_listing (
    comparison_id uuid NOT NULL REFERENCES comparison (id) ON DELETE CASCADE,
    position      smallint NOT NULL CHECK (position BETWEEN 1 AND 4),
    listing_id    uuid NOT NULL REFERENCES listing (id),
    snapshot      jsonb NOT NULL,   -- values at save time: later changes are flagged, never swapped in (R-4.5)
    PRIMARY KEY (comparison_id, position),
    UNIQUE (comparison_id, listing_id)
);

-- =====================================================================================
-- Group discussion and polls (R-5)
-- =====================================================================================

CREATE TABLE message (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    group_id      uuid NOT NULL REFERENCES user_group (id) ON DELETE CASCADE,
    author_id     uuid REFERENCES app_user (id) ON DELETE SET NULL,
    listing_id    uuid REFERENCES listing (id),
    comparison_id uuid,
    body          text NOT NULL CHECK (char_length(btrim(body)) BETWEEN 1 AND 4000),
    sent_at       timestamptz NOT NULL DEFAULT now(),
    CHECK (num_nonnulls(listing_id, comparison_id) <= 1),
    -- a comparison thread must belong to the same group
    FOREIGN KEY (comparison_id, group_id) REFERENCES comparison (id, group_id)
);
CREATE INDEX message_group_idx ON message (group_id, sent_at DESC);
CREATE INDEX message_listing_thread_idx ON message (group_id, listing_id, sent_at DESC) WHERE listing_id IS NOT NULL;
CREATE INDEX message_comparison_thread_idx ON message (comparison_id, sent_at DESC) WHERE comparison_id IS NOT NULL;

CREATE TABLE message_reaction (
    message_id uuid NOT NULL REFERENCES message (id) ON DELETE CASCADE,
    user_id    uuid NOT NULL REFERENCES app_user (id) ON DELETE CASCADE,
    emoji      text NOT NULL CHECK (char_length(emoji) BETWEEN 1 AND 16),
    reacted_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (message_id, user_id)   -- R-5.2: one reaction per user per message
);

CREATE TABLE poll (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    group_id   uuid NOT NULL REFERENCES user_group (id) ON DELETE CASCADE,
    created_by uuid REFERENCES app_user (id) ON DELETE SET NULL,
    question   text NOT NULL CHECK (char_length(btrim(question)) BETWEEN 1 AND 200),
    state      text NOT NULL DEFAULT 'open' CHECK (state IN ('open', 'closed')),
    created_at timestamptz NOT NULL DEFAULT now(),
    closed_at  timestamptz,
    CHECK ((state = 'closed') = (closed_at IS NOT NULL))
);
CREATE INDEX poll_group_idx ON poll (group_id, created_at DESC);

-- Poll 1 -- 2..4 PollOption (the lower bound is checked by RoomService on creation).
CREATE TABLE poll_option (
    id       uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    poll_id  uuid NOT NULL REFERENCES poll (id) ON DELETE CASCADE,
    position smallint NOT NULL CHECK (position BETWEEN 1 AND 4),
    text     text NOT NULL CHECK (char_length(btrim(text)) BETWEEN 1 AND 120),
    UNIQUE (poll_id, position),
    UNIQUE (id, poll_id)
);

CREATE TABLE poll_vote (
    poll_id   uuid NOT NULL REFERENCES poll (id) ON DELETE CASCADE,
    user_id   uuid NOT NULL REFERENCES app_user (id) ON DELETE CASCADE,
    option_id uuid NOT NULL,
    cast_at   timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (poll_id, user_id),     -- R-5.3: one active vote per member per poll
    FOREIGN KEY (option_id, poll_id) REFERENCES poll_option (id, poll_id) ON DELETE CASCADE
);

-- R-5.4: closed polls reject changes.
CREATE FUNCTION check_poll_open() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF EXISTS (SELECT 1 FROM poll p WHERE p.id = COALESCE(NEW.poll_id, OLD.poll_id) AND p.state = 'closed') THEN
        RAISE EXCEPTION 'poll is closed'
            USING ERRCODE = 'check_violation', CONSTRAINT = 'poll_vote_poll_open';
    END IF;
    RETURN COALESCE(NEW, OLD);
END $$;
CREATE TRIGGER poll_vote_open BEFORE INSERT OR UPDATE ON poll_vote
    FOR EACH ROW EXECUTE FUNCTION check_poll_open();

-- =====================================================================================
-- Notifications (R-6)
-- =====================================================================================

CREATE TABLE notification (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    recipient_id uuid NOT NULL REFERENCES app_user (id) ON DELETE CASCADE,
    kind         text NOT NULL CHECK (kind IN ('new_match', 'price_change', 'removed', 'message')),
    event_id     uuid NOT NULL,          -- the message / source record / price change behind it
    group_id     uuid REFERENCES user_group (id) ON DELETE CASCADE,
    listing_id   uuid REFERENCES listing (id),
    title        text NOT NULL CHECK (char_length(title) <= 200),  -- never a private message body
    status       text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'deferred', 'delivered', 'suppressed')),
    email_status text NOT NULL DEFAULT 'none' CHECK (email_status IN ('none', 'pending', 'sent', 'failed')),
    created_at   timestamptz NOT NULL DEFAULT now(),
    delivered_at timestamptz,
    read_at      timestamptz,
    -- R-6.2: at most one alert per recipient for each event; retries hit this key.
    CONSTRAINT notification_once_key UNIQUE (recipient_id, kind, event_id)
);
CREATE INDEX notification_inbox_idx ON notification (recipient_id, created_at DESC) WHERE status = 'delivered';
CREATE INDEX notification_email_queue_idx ON notification (created_at) WHERE email_status = 'pending';
