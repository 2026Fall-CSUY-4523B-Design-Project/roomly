"""DDL invariants: the database rejects what the SSDS forbids, even if a service forgot to check."""

import uuid

import psycopg
import pytest

from roomly.config import Settings
from roomly.db import Database, migrate

pytestmark = pytest.mark.integration


def _user(conn: psycopg.Connection, role: str = "user") -> uuid.UUID:
    n = uuid.uuid4().hex[:8]
    return conn.execute("INSERT INTO app_user (email, password_hash, role) VALUES (%s, 'x', %s) RETURNING id",
                        (f"{n}@example.com", role)).fetchone()[0]


def _group(conn: psycopg.Connection) -> uuid.UUID:
    return conn.execute("INSERT INTO user_group (name) VALUES ('G') RETURNING id").fetchone()[0]


def _violates(db: Database, sql: str, params: tuple, constraint: str) -> None:
    with pytest.raises(psycopg.errors.IntegrityError) as info, db.transaction() as conn:
        conn.execute(sql, params)
    assert info.value.diag.constraint_name == constraint


def test_migrations_are_idempotent(database_url: str) -> None:
    assert migrate(database_url, Settings.from_env({}).migrations_dir) == []


def test_group_has_at_most_six_current_members(db: Database) -> None:
    with db.transaction() as conn:
        group = _group(conn)
        for _ in range(6):
            conn.execute("INSERT INTO group_membership (group_id, user_id) VALUES (%s, %s)", (group, _user(conn)))
        seventh = _user(conn)
    _violates(db, "INSERT INTO group_membership (group_id, user_id) VALUES (%s, %s)", (group, seventh),
              "group_membership_max_six")


def test_administrators_are_never_members(db: Database) -> None:
    with db.transaction() as conn:
        group, admin = _group(conn), _user(conn, "admin")
    _violates(db, "INSERT INTO group_membership (group_id, user_id) VALUES (%s, %s)", (group, admin),
              "group_membership_eligible")


def test_one_current_owner_per_group(db: Database) -> None:
    with db.transaction() as conn:
        group = _group(conn)
        conn.execute("INSERT INTO group_membership (group_id, user_id, role) VALUES (%s, %s, 'owner')",
                     (group, _user(conn)))
        other = _user(conn)
    _violates(db, "INSERT INTO group_membership (group_id, user_id, role) VALUES (%s, %s, 'owner')", (group, other),
              "group_membership_one_owner_key")


def test_at_most_three_commute_destinations(db: Database) -> None:
    with db.transaction() as conn:
        user = _user(conn)
        for i in range(3):
            conn.execute("INSERT INTO commute_destination (user_id, label, address) VALUES (%s, %s, 'x')", (user, f"d{i}"))
    _violates(db, "INSERT INTO commute_destination (user_id, label, address) VALUES (%s, 'd4', 'x')", (user,),
              "commute_destination_max_three")


def test_searchable_listings_are_in_scope(db: Database) -> None:
    """R-2.1: no borough or a short stay cannot be searchable."""
    _violates(db, "INSERT INTO listing (status, borough, min_lease_days) VALUES ('searchable', NULL, 365)", (),
              "listing_searchable_in_scope")
    _violates(db, "INSERT INTO listing (status, borough, min_lease_days) VALUES ('searchable', 'queens', 7)", (),
              "listing_searchable_in_scope")
    with db.transaction() as conn:
        conn.execute("INSERT INTO listing (status, borough, min_lease_days) VALUES ('excluded', NULL, 7)")


def test_closed_poll_rejects_votes(db: Database) -> None:
    with db.transaction() as conn:
        group, user = _group(conn), _user(conn)
        poll = conn.execute("INSERT INTO poll (group_id, question, state, closed_at) VALUES (%s, 'Q', 'closed', now()) "
                            "RETURNING id", (group,)).fetchone()[0]
        option = conn.execute("INSERT INTO poll_option (poll_id, position, text) VALUES (%s, 1, 'A') RETURNING id",
                              (poll,)).fetchone()[0]
    _violates(db, "INSERT INTO poll_vote (poll_id, user_id, option_id) VALUES (%s, %s, %s)", (poll, user, option),
              "poll_vote_poll_open")


def test_vote_option_must_belong_to_its_poll(db: Database) -> None:
    with db.transaction() as conn:
        group, user = _group(conn), _user(conn)
        p1, p2 = (conn.execute("INSERT INTO poll (group_id, question) VALUES (%s, 'Q') RETURNING id", (group,)).fetchone()[0]
                  for _ in range(2))
        other = conn.execute("INSERT INTO poll_option (poll_id, position, text) VALUES (%s, 1, 'A') RETURNING id",
                             (p2,)).fetchone()[0]
    with pytest.raises(psycopg.errors.ForeignKeyViolation), db.transaction() as conn:
        conn.execute("INSERT INTO poll_vote (poll_id, user_id, option_id) VALUES (%s, %s, %s)", (p1, user, other))


def test_notification_once_per_recipient_and_event(db: Database) -> None:
    event = uuid.uuid4()
    with db.transaction() as conn:
        user = _user(conn)
        conn.execute("INSERT INTO notification (recipient_id, kind, event_id, title) VALUES (%s, 'message', %s, 't')",
                     (user, event))
    _violates(db, "INSERT INTO notification (recipient_id, kind, event_id, title) VALUES (%s, 'message', %s, 't')",
              (user, event), "notification_once_key")


def test_retried_fetch_is_not_a_second_record(db: Database) -> None:
    with db.transaction() as conn:
        source = conn.execute("INSERT INTO listing_source (name, kind) VALUES ('SampleFeed', 'feed') RETURNING id"
                              ).fetchone()[0]
        conn.execute("INSERT INTO source_record (source_id, external_id, collected_at, raw_values) "
                     "VALUES (%s, 'abc', '2026-10-29T12:00Z', '{}')", (source,))
    _violates(db, "INSERT INTO source_record (source_id, external_id, collected_at, raw_values) "
                  "VALUES (%s, 'abc', '2026-10-29T12:00Z', '{}')", (source,), "source_record_fetch_key")


def test_deleted_accounts_hold_no_personal_data(db: Database) -> None:
    with pytest.raises(psycopg.errors.CheckViolation), db.transaction() as conn:
        conn.execute("UPDATE app_user SET deleted_at = now() WHERE id = %s", (_user(conn),))
