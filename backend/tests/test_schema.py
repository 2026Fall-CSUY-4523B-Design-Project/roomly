"""DDL invariants on both engines: the database rejects what the SSDS forbids, even if a service forgot."""

import uuid

import pytest

from roomly.db import Database, IntegrityError, Tx, constraint_name

from conftest import MIGRATIONS

pytestmark = pytest.mark.integration


def _user(tx: Tx, role: str = "user") -> uuid.UUID:
    return tx.scalar("INSERT INTO app_user (email, password_hash, role) VALUES (%(email)s, 'x', %(role)s) RETURNING id",
                     {"email": f"{uuid.uuid4().hex[:8]}@example.com", "role": role}, as_type=uuid.UUID)


def _group(tx: Tx) -> uuid.UUID:
    return tx.scalar("INSERT INTO user_group (name) VALUES ('G') RETURNING id", as_type=uuid.UUID)


def _violates(db: Database, sql: str, params: dict, constraint: str, sqlite_text: str | None = None) -> None:
    """Postgres names the constraint; SQLite names it for CHECKs and triggers, and lists columns for UNIQUE."""
    with pytest.raises(IntegrityError) as info, db.transaction() as tx:
        tx.exec(sql, params)
    if db.dialect == "postgres" or sqlite_text is None:
        assert constraint_name(info.value) == constraint
    else:
        assert sqlite_text in str(info.value)


def test_migrations_are_idempotent(db: Database) -> None:
    assert db.migrate(MIGRATIONS) == []


def test_group_has_at_most_six_current_members(db: Database) -> None:
    with db.transaction() as tx:
        group = _group(tx)
        for _ in range(6):
            tx.exec("INSERT INTO group_membership (group_id, user_id) VALUES (%(g)s, %(u)s)", {"g": group, "u": _user(tx)})
        seventh = _user(tx)
    _violates(db, "INSERT INTO group_membership (group_id, user_id) VALUES (%(g)s, %(u)s)", {"g": group, "u": seventh},
              "group_membership_max_six")


def test_administrators_are_never_members(db: Database) -> None:
    with db.transaction() as tx:
        group, admin = _group(tx), _user(tx, "admin")
    _violates(db, "INSERT INTO group_membership (group_id, user_id) VALUES (%(g)s, %(u)s)", {"g": group, "u": admin},
              "group_membership_eligible")


def test_one_current_owner_per_group(db: Database) -> None:
    with db.transaction() as tx:
        group = _group(tx)
        tx.exec("INSERT INTO group_membership (group_id, user_id, role) VALUES (%(g)s, %(u)s, 'owner')",
                {"g": group, "u": _user(tx)})
        other = _user(tx)
    _violates(db, "INSERT INTO group_membership (group_id, user_id, role) VALUES (%(g)s, %(u)s, 'owner')",
              {"g": group, "u": other}, "group_membership_one_owner_key", "group_membership.group_id")


def test_at_most_three_commute_destinations(db: Database) -> None:
    with db.transaction() as tx:
        user = _user(tx)
        for i in range(3):
            tx.exec("INSERT INTO commute_destination (user_id, label, address) VALUES (%(u)s, %(l)s, 'x')",
                    {"u": user, "l": f"d{i}"})
    _violates(db, "INSERT INTO commute_destination (user_id, label, address) VALUES (%(u)s, 'd4', 'x')", {"u": user},
              "commute_destination_max_three")


def test_searchable_listings_are_in_scope(db: Database) -> None:
    """R-2.1: no borough or a short stay cannot be searchable."""
    insert = "INSERT INTO listing (status, borough, min_lease_days) VALUES (%(s)s, %(b)s, %(d)s)"
    _violates(db, insert, {"s": "searchable", "b": None, "d": 365}, "listing_searchable_in_scope")
    _violates(db, insert, {"s": "searchable", "b": "queens", "d": 7}, "listing_searchable_in_scope")
    with db.transaction() as tx:
        tx.exec(insert, {"s": "excluded", "b": None, "d": 7})


def test_postal_codes_and_urls_are_checked(db: Database) -> None:
    for bad in ("1121", "11211-1234", "abcde"):
        with pytest.raises(IntegrityError), db.transaction() as tx:
            tx.exec("INSERT INTO listing (status, postal_code) VALUES ('excluded', %(p)s)", {"p": bad})
    with db.transaction() as tx:
        tx.exec("INSERT INTO listing (status, postal_code) VALUES ('excluded', '11211')")


def test_closed_poll_rejects_votes(db: Database) -> None:
    with db.transaction() as tx:
        group, user = _group(tx), _user(tx)
        poll = tx.scalar("INSERT INTO poll (group_id, question, state, closed_at) VALUES (%(g)s, 'Q', 'closed', now()) "
                         "RETURNING id", {"g": group}, as_type=uuid.UUID)
        option = tx.scalar("INSERT INTO poll_option (poll_id, position, text) VALUES (%(p)s, 1, 'A') RETURNING id",
                           {"p": poll}, as_type=uuid.UUID)
    _violates(db, "INSERT INTO poll_vote (poll_id, user_id, option_id) VALUES (%(p)s, %(u)s, %(o)s)",
              {"p": poll, "u": user, "o": option}, "poll_vote_poll_open")


def test_vote_option_must_belong_to_its_poll(db: Database) -> None:
    with db.transaction() as tx:
        group, user = _group(tx), _user(tx)
        p1, p2 = (tx.scalar("INSERT INTO poll (group_id, question) VALUES (%(g)s, 'Q') RETURNING id", {"g": group},
                            as_type=uuid.UUID) for _ in range(2))
        other = tx.scalar("INSERT INTO poll_option (poll_id, position, text) VALUES (%(p)s, 1, 'A') RETURNING id",
                          {"p": p2}, as_type=uuid.UUID)
    with pytest.raises(IntegrityError), db.transaction() as tx:
        tx.exec("INSERT INTO poll_vote (poll_id, user_id, option_id) VALUES (%(p)s, %(u)s, %(o)s)",
                {"p": p1, "u": user, "o": other})


def test_notification_once_per_recipient_and_event(db: Database) -> None:
    insert = ("INSERT INTO notification (recipient_id, kind, event_id, title) "
              "VALUES (%(u)s, 'message', %(e)s, 't')")
    with db.transaction() as tx:
        params = {"u": _user(tx), "e": uuid.uuid4()}
        tx.exec(insert, params)
    _violates(db, insert, params, "notification_once_key", "notification.recipient_id")


def test_retried_fetch_is_not_a_second_record(db: Database) -> None:
    insert = ("INSERT INTO source_record (source_id, external_id, collected_at, raw_values) "
              "VALUES (%(s)s, 'abc', '2026-10-29T12:00:00.000000+00:00', '{}')")
    with db.transaction() as tx:
        source = tx.scalar("INSERT INTO listing_source (name, kind) VALUES ('SampleFeed', 'feed') RETURNING id",
                           as_type=uuid.UUID)
        tx.exec(insert, {"s": source})
    _violates(db, insert, {"s": source}, "source_record_fetch_key", "source_record.source_id")


def test_notification_kinds_are_known(db: Database) -> None:
    with pytest.raises(IntegrityError), db.transaction() as tx:
        tx.exec("UPDATE app_user SET notify_kinds = %(k)s WHERE id = %(id)s", {"k": ["gossip"], "id": _user(tx)})


def test_deleted_accounts_hold_no_personal_data(db: Database) -> None:
    with pytest.raises(IntegrityError), db.transaction() as tx:
        tx.exec("UPDATE app_user SET deleted_at = now() WHERE id = %(id)s", {"id": _user(tx)})
