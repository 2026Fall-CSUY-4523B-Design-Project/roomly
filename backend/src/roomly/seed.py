"""Fill the development database with one coherent demo world.

Run: ``script/seed.sh`` (or ``uv run python -m roomly.seed`` from ``backend/``).
``--reset`` empties every table except ``schema_migration`` first; that is a development
shortcut and is refused in prod.

The demo accounts all use the password ``roomly1234``. Maya owns the group, Alex and Sam are
members, Priya has invited Maya to a second group, and the listings cover a full card, a
studio with Unknown values, a three-bedroom, and a held duplicate.
"""

import argparse
import datetime as dt
import os
import sys
from uuid import UUID

from roomly.config import Settings
from roomly.db import Database, Tx
from roomly.dto.notification import NotificationSettingsDTO
from roomly.mapper.account_mapper import UserMapper
from roomly.mapper.comparison_mapper import ComparisonMapper
from roomly.mapper.group_mapper import GroupMapper, InvitationMapper, MembershipMapper
from roomly.mapper.listing_mapper import (
    DuplicateMapper,
    ListingMapper,
    PriceHistoryMapper,
    ReportMapper,
    SourceMapper,
    SourceRecordMapper,
)
from roomly.mapper.notification_mapper import NotificationMapper
from roomly.mapper.room_mapper import MessageMapper, PollMapper, ReactionMapper
from roomly.mapper.search_mapper import CommuteMapper, SavedSearchMapper
from roomly.service.account_service import password_hash
from roomly.service.comparison_service import snapshot

PASSWORD = "roomly1234"
DOMAIN = "@roomly.test"
NOW = dt.datetime.now(dt.UTC)

# Children first: reset must not fight a foreign key.
_TABLES = [
    "message_reaction", "poll_vote", "poll_option", "poll", "message",
    "comparison_listing", "comparison", "notification",
    "duplicate_candidate", "data_report", "listing_price_history", "source_record", "listing",
    "group_invitation", "group_membership", "user_group",
    "saved_search", "commute_destination", "user_session", "auth_token", "app_user", "listing_source",
]


def _user(tx: Tx, email: str, name: str) -> UUID:
    user = UserMapper(tx).insert(email + DOMAIN, password_hash(PASSWORD), name, verified=True)
    return user.id


def _listing(tx: Tx, **values) -> UUID:
    listing = ListingMapper(tx).insert(values)
    return listing.id


def _record(tx: Tx, source_id: UUID, listing_id: UUID, external_id: str, url: str | None,
            collected_at: dt.datetime, values: dict) -> UUID:
    record = SourceRecordMapper(tx).insert(
        source_id=source_id, listing_id=listing_id, external_id=external_id, original_url=url,
        collected_at=collected_at, raw_values=values, submitted_by=None)
    assert record is not None
    return record.id


def _reset(tx: Tx) -> None:
    for table in _TABLES:
        tx.exec(f"DELETE FROM {table}")


def seed(tx: Tx) -> dict[str, int]:
    maya = _user(tx, "maya", "Maya Chen")
    alex = _user(tx, "alex", "Alex Rivera")
    sam = _user(tx, "sam", "Sam Okafor")
    priya = _user(tx, "priya", "Priya Nair")
    _user(tx, "admin", "Roomly Admin")
    UserMapper(tx).set_role("admin" + DOMAIN, "admin")
    UserMapper(tx).update_notification_settings(
        maya, kinds=list(NotificationSettingsDTO().kinds), email=True, digest=False,
        quiet_start=dt.time(22, 0), quiet_end=dt.time(7, 0))

    sources = SourceMapper(tx)
    feed = sources.find_by_name("SampleFeed") or sources.insert(
        "SampleFeed", "feed", enabled=True, is_synthetic=True,
        config={"url": "https://samplefeed.example/feed.json", "interval_minutes": 60})
    sources.find_by_name("Manual entry") or sources.insert(
        "Manual entry", "manual", enabled=True, is_synthetic=False, config={})

    knickerbocker = _listing(
        tx, status="searchable", title="Sunny 2BR near the Jefferson L",
        address_line="214 Knickerbocker Ave", unit="3F", borough="brooklyn", postal_code="11237",
        latitude=40.7046, longitude=-73.9213, advertised_rent_cents=320_000,
        net_effective_rent_cents=295_000, lease_term_months=13, broker_fee_cents=0,
        bedrooms=2, bathrooms=1.0, area_sqft=850, move_in_date=dt.date(2026, 12, 1),
        min_lease_days=365, amenities=["dishwasher", "laundry_in_building"],
        availability="available", is_synthetic=True)
    steinway = _listing(
        tx, status="searchable", title="Astoria studio",
        address_line="31-12 Steinway St", borough="queens", postal_code="11103",
        latitude=40.7605, longitude=-73.9150, advertised_rent_cents=210_000,
        bedrooms=0, area_sqft=None, move_in_date=None, min_lease_days=180,
        amenities=[], availability="unknown", is_synthetic=True)
    harlem = _listing(
        tx, status="searchable", title=None,
        address_line="560 W 144th St", unit="5B", borough="manhattan", postal_code="10031",
        advertised_rent_cents=415_000, bedrooms=3, bathrooms=1.5, area_sqft=1100,
        move_in_date=dt.date(2027, 1, 15), min_lease_days=365, amenities=["elevator"],
        availability="available", is_synthetic=True)
    harlem_duplicate = _listing(
        tx, status="under_review", title="3BR in Harlem",
        address_line="560 W 144th St", unit="5B", borough="manhattan", postal_code="10031",
        advertised_rent_cents=405_000, bedrooms=3, bathrooms=2.0, area_sqft=1150,
        move_in_date=dt.date(2027, 1, 1), min_lease_days=365, amenities=["elevator"],
        availability="available", is_synthetic=True)

    feed_url = "https://samplefeed.example/listings/"
    knickerbocker_record = _record(
        tx, feed.id, knickerbocker, "sf-20418", feed_url + "sf-20418", NOW - dt.timedelta(hours=2),
        {"rent": 320_000, "bedrooms": 2, "bathrooms": 1.0, "area_sqft": 850})
    _record(tx, feed.id, steinway, "sf-20419", feed_url + "sf-20419", NOW - dt.timedelta(days=1),
            {"rent": 210_000, "bedrooms": 0})
    _record(tx, feed.id, harlem, "sf-20420", feed_url + "sf-20420", NOW - dt.timedelta(days=3),
            {"rent": 415_000, "bedrooms": 3, "bathrooms": 1.5, "area_sqft": 1100})
    harlem_duplicate_record = _record(
        tx, feed.id, harlem_duplicate, "sf-20421", feed_url + "sf-20421", NOW - dt.timedelta(hours=1),
        {"rent": 405_000, "bedrooms": 3, "bathrooms": 2.0, "area_sqft": 1150})

    history = PriceHistoryMapper(tx)
    history.insert(knickerbocker, None, 335_000, NOW - dt.timedelta(days=10))
    history.insert(knickerbocker, knickerbocker_record, 320_000, NOW - dt.timedelta(hours=2))
    history.insert(steinway, None, 210_000, NOW - dt.timedelta(days=1))
    history.insert(harlem, None, 415_000, NOW - dt.timedelta(days=3))
    # The held record belongs to the Harlem pair; give it an earlier record to compare against.
    harlem_base = SourceRecordMapper(tx).latest_for_listing(harlem)
    assert harlem_base is not None
    DuplicateMapper(tx).insert(harlem_base.id, harlem_duplicate_record, 0.82)

    groups = GroupMapper(tx)
    crew = groups.insert("Bushwick crew")
    members = MembershipMapper(tx)
    for user_id, role in ((maya, "owner"), (alex, "member"), (sam, "member")):
        members.insert(crew.id, user_id, role)

    invitations = InvitationMapper(tx)
    accepted = invitations.insert(crew.id, "sam" + DOMAIN, maya, NOW + dt.timedelta(days=7))
    invitations.respond(accepted.id, "accepted")
    invitations.insert(crew.id, "jordan@example.com", maya, NOW + dt.timedelta(days=7))

    astoria = groups.insert("Astoria search")
    members.insert(astoria.id, priya, "owner")
    invitations.insert(astoria.id, "maya" + DOMAIN, priya, NOW + dt.timedelta(days=5))

    comparisons = ComparisonMapper(tx)
    shared = comparisons.insert(maya, crew.id, "Top three")
    for position, listing_id in enumerate((knickerbocker, steinway, harlem), start=1):
        listing = ListingMapper(tx).find(listing_id)
        assert listing is not None
        comparisons.add_listing(shared.id, position, listing_id, snapshot(listing))
    personal = comparisons.insert(alex, None, "Knickerbocker vs Steinway")
    for position, listing_id in enumerate((knickerbocker, steinway), start=1):
        listing = ListingMapper(tx).find(listing_id)
        assert listing is not None
        comparisons.add_listing(personal.id, position, listing_id, snapshot(listing))

    messages = MessageMapper(tx)
    first = messages.insert(crew.id, alex, "Rent dropped to $3,200 on the Knickerbocker one!",
                            knickerbocker, None)
    second = messages.insert(crew.id, sam, "Harlem is big but the broker fee hurts.",
                             None, shared.id)
    third = messages.insert(crew.id, maya, "Saturday 11am works for me.", None, None)
    tx.exec("UPDATE message SET sent_at = %(at)s WHERE id = %(id)s",
            {"id": first.id, "at": NOW - dt.timedelta(days=3)})
    tx.exec("UPDATE message SET sent_at = %(at)s WHERE id = %(id)s",
            {"id": second.id, "at": NOW - dt.timedelta(days=2)})
    tx.exec("UPDATE message SET sent_at = %(at)s WHERE id = %(id)s",
            {"id": third.id, "at": NOW - dt.timedelta(hours=1)})
    reactions = ReactionMapper(tx)
    reactions.upsert(first.id, alex, "🎉")
    reactions.upsert(first.id, sam, "🎉")
    reactions.upsert(second.id, maya, "👍")

    polls = PollMapper(tx)
    poll = polls.insert(crew.id, maya, "Which one do we tour first?")
    options = [polls.add_option(poll.id, index, text) for index, text in enumerate(
        ("214 Knickerbocker Ave", "560 W 144th St", "Keep looking"), start=1)]
    polls.upsert_vote(poll.id, maya, options[0].id)
    polls.upsert_vote(poll.id, alex, options[0].id)
    polls.upsert_vote(poll.id, sam, options[1].id)

    notifications = NotificationMapper(tx)
    for recipient, kind, event, title, group_id, listing_id, read in (
        (maya, "new_match", knickerbocker, "New match for “2BR in Brooklyn under $3.5k”", None, knickerbocker, True),
        (maya, "price_change", knickerbocker, "214 Knickerbocker Ave: $3,350 → $3,200", None, knickerbocker, False),
        (maya, "message", first.id, "Alex Rivera in Bushwick crew: Rent dropped to $3,200…", crew.id, None, False),
        (sam, "message", first.id, "Alex Rivera in Bushwick crew: Rent dropped to $3,200…", crew.id, None, False),
        (alex, "message", third.id, "Maya Chen in Bushwick crew: Saturday 11am works for me.", crew.id, None, False),
        (sam, "message", third.id, "Maya Chen in Bushwick crew: Saturday 11am works for me.", crew.id, None, False),
    ):
        row = notifications.insert_once(
            recipient_id=recipient, kind=kind, event_id=event, title=title, status="delivered",
            email_status="none", group_id=group_id, listing_id=listing_id)
        if row is not None and read:
            notifications.mark_read(row.id, recipient)

    ReportMapper(tx).insert(steinway, sam, "wrong_value", "The rent changed at the source.")

    searches = SavedSearchMapper(tx)
    searches.insert(maya, "2BR in Brooklyn under $3.5k",
                    {"boroughs": ["brooklyn"], "max_rent_cents": 350_000, "min_bedrooms": 2}, {}, True)
    searches.insert(maya, "Studios in Queens", {"boroughs": ["queens"], "max_bedrooms": 0}, {}, True)

    commutes = CommuteMapper(tx)
    commutes.insert(maya, "NYU Tandon", "6 MetroTech Center, Brooklyn, NY 11201",
                    40.6943, -73.9865, "transit")
    commutes.insert(maya, "Climbing gym", "575 Degraw St, Brooklyn, NY 11217", None, None, "bike")

    return {
        "users": 5,
        "listings": 4,
        "groups": 2,
        "messages": 3,
        "notifications": 6,
        "duplicate_candidates": 1,
        "saved_searches": 2,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Seed the development database with demo data.")
    parser.add_argument("--reset", action="store_true",
                        help="delete every row except schema_migration before seeding")
    args = parser.parse_args(argv)

    settings = Settings.from_env(os.environ)
    if settings.env == "prod":
        print("refusing to seed a prod database", file=sys.stderr)
        return 2
    database = Database(settings.database_url, fallback=settings.sqlite_fallback)
    database.open()
    try:
        database.migrate(settings.migrations_dir)
        with database.transaction() as tx:
            if args.reset:
                _reset(tx)
            elif UserMapper(tx).find_by_email("maya" + DOMAIN) is not None:
                print("demo data is already present; run script/seed.sh --reset to replace it")
                return 0
        with database.transaction() as tx:
            counts = seed(tx)
    finally:
        database.close()

    print("seeded " + ", ".join(f"{count} {name}" for name, count in counts.items()))
    print()
    print("sign in with any of these (password: roomly1234):")
    for email, role in (("maya", "owner of Bushwick crew"), ("alex", "member"),
                        ("sam", "member"), ("priya", "owner of Astoria search"),
                        ("admin", "administrator")):
        print(f"  {email + DOMAIN:<22} {role}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
