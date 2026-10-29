"""Sample responses for endpoints whose service method is still a stub (ROOMLY_FIXTURES).

When a stub raises NotImplementedError and fixtures are on, the API answers with the sample
below for that route, with the route's normal status code and an ``X-Roomly-Fixture: 1``
header. Implemented methods return real data; stubs keep answering with samples.

The samples form one small, consistent world, so ids line up across endpoints: Maya (the
signed-in user) owns the group "Bushwick crew" with Alex and Sam, and they are comparing
three listings. Path ids and request bodies are not used: every call to a route returns the
same sample. Every value is built from the response DTOs, so a renamed or missing field
fails at import time.
"""

import datetime as dt
from typing import Any
from uuid import UUID

from roomly.dto.account import SessionDTO, UserDTO
from roomly.dto.admin import DuplicateDTO, DuplicateSideDTO, SourceDTO
from roomly.dto.common import Page, PersonRef
from roomly.dto.comparison import (
    ComparisonCell,
    ComparisonDTO,
    ComparisonRow,
    ComparisonSummaryDTO,
    ComparisonTableDTO,
    Direction,
    ListingChangeDTO,
)
from roomly.dto.group import (
    GroupDetailDTO,
    GroupSummaryDTO,
    IncomingInvitationDTO,
    InvitationDTO,
    MemberDTO,
)
from roomly.dto.listing import (
    Coordinates,
    DerivedValue,
    ListingCardDTO,
    ListingSummaryDTO,
    PricePointDTO,
    ReportDTO,
    SourceRefDTO,
)
from roomly.dto.notification import (
    NotificationDTO,
    NotificationListDTO,
    NotificationSettingsDTO,
)
from roomly.dto.room import MessageDTO, PollDTO, PollOptionDTO, ReactionCountDTO
from roomly.dto.search import CommuteDestinationDTO, SavedSearchDTO
from roomly.entity import User


def _id(kind: int, n: int) -> UUID:
    """Readable fixed ids: kind 1 users, 2 groups, 3 listings, 4 invitations, 5 sources and
    records, 6 admin items, 7 searches and destinations, 8 comparisons, 9 room, 10 notifications."""
    return UUID(f"{kind:08x}-0000-4000-8000-{n:012x}")


def _at(day: int, hour: int = 12, minute: int = 0) -> dt.datetime:
    return dt.datetime(2026, 10, day, hour, minute, tzinfo=dt.UTC)


# --- people --------------------------------------------------------------------------

MAYA, ALEX, SAM = _id(1, 1), _id(1, 2), _id(1, 3)

ME = UserDTO(id=MAYA, email="maya@example.com", display_name="Maya Chen", role="user", created_at=_at(12))

USER = User(  # the caller of every authenticated route while fixtures are on
    id=MAYA, email=ME.email, password_hash=None, display_name=ME.display_name, role=ME.role, preferences={},
    notify_kinds=["new_match", "price_change", "removed", "message"], notify_email=True, notify_digest=False,
    quiet_start=None, quiet_end=None, created_at=ME.created_at, updated_at=ME.created_at, deleted_at=None,
)

SESSION = SessionDTO(token="fixture-session-token", expires_at=dt.datetime(2026, 11, 12, 12, tzinfo=dt.UTC), user=ME)


def _person(user_id: UUID | None, name: str) -> PersonRef:
    return PersonRef(id=user_id, name=name, deleted=False)


# --- group ---------------------------------------------------------------------------

CREW = _id(2, 1)

GROUP = GroupDetailDTO(id=CREW, name="Bushwick crew", created_at=_at(20), my_role="owner", members=[
    MemberDTO(user=_person(MAYA, "Maya Chen"), role="owner", joined_at=_at(20)),
    MemberDTO(user=_person(ALEX, "Alex Rivera"), role="member", joined_at=_at(21, 9)),
    MemberDTO(user=_person(SAM, "Sam Okafor"), role="member", joined_at=_at(22, 18)),
])

GROUPS = [GroupSummaryDTO(id=CREW, name=GROUP.name, role="owner", member_count=3, created_at=GROUP.created_at)]

SENT_INVITATIONS = [
    InvitationDTO(id=_id(4, 1), group_id=CREW, email="jordan@example.com", state="pending", created_at=_at(27),
                  expires_at=dt.datetime(2026, 11, 3, 12, tzinfo=dt.UTC), responded_at=None),
    InvitationDTO(id=_id(4, 2), group_id=CREW, email="sam@example.com", state="accepted", created_at=_at(22),
                  expires_at=_at(29), responded_at=_at(22, 18)),
]

INCOMING_INVITATIONS = [
    IncomingInvitationDTO(id=_id(4, 3), group_id=_id(2, 2), group_name="Astoria search", invited_by="Priya Nair",
                          created_at=_at(28), expires_at=dt.datetime(2026, 11, 4, 12, tzinfo=dt.UTC)),
]

# --- listings ------------------------------------------------------------------------

KNICKERBOCKER, STEINWAY, HARLEM, KNICKERBOCKER_DUP = _id(3, 1), _id(3, 2), _id(3, 3), _id(3, 4)

LISTINGS = [
    ListingSummaryDTO(
        id=KNICKERBOCKER, title="Sunny 2BR near the Jefferson L", address_line="214 Knickerbocker Ave", unit="3F",
        borough="brooklyn", advertised_rent_cents=320_000, net_effective_rent_cents=295_000, bedrooms=2,
        bathrooms=1.0, area_sqft=850, move_in_date=dt.date(2026, 12, 1), amenities=["dishwasher", "laundry_in_building"],
        coordinates=Coordinates(40.7046, -73.9213), availability="available", is_synthetic=True,
        has_conflicts=True, updated_at=_at(28, 9), unknown=[],
    ),
    ListingSummaryDTO(
        id=STEINWAY, title="Astoria studio", address_line="31-12 Steinway St", unit=None, borough="queens",
        advertised_rent_cents=210_000, net_effective_rent_cents=None, bedrooms=0, bathrooms=None, area_sqft=None,
        move_in_date=None, amenities=[], coordinates=Coordinates(40.7605, -73.9150), availability="unknown",
        is_synthetic=True, has_conflicts=False, updated_at=_at(26, 15),
        unknown=["bathrooms", "area_sqft", "move_in_date"],
    ),
    ListingSummaryDTO(
        id=HARLEM, title=None, address_line="560 W 144th St", unit="5B", borough="manhattan",
        advertised_rent_cents=415_000, net_effective_rent_cents=None, bedrooms=3, bathrooms=1.5, area_sqft=1100,
        move_in_date=dt.date(2027, 1, 15), amenities=["elevator"], coordinates=None, availability="available",
        is_synthetic=True, has_conflicts=False, updated_at=_at(25, 11), unknown=["coordinates"],
    ),
]

SAMPLEFEED, MANUAL = _id(5, 1), _id(5, 2)

CARD = ListingCardDTO(
    **{**vars(LISTINGS[0]), "unknown": ["monthly_fees_cents"]},
    status="searchable", merged_into_id=None, postal_code="11237", lease_term_months=13, broker_fee_cents=0,
    monthly_fees_cents=None, min_lease_days=365,
    conflicts={"bathrooms": [{"source_record_id": str(_id(5, 101)), "value": 1},
                             {"source_record_id": str(_id(5, 102)), "value": 1.5}]},
    price_per_sqft_cents=DerivedValue(value=376, formula="advertised monthly rent ÷ area in sq ft"),
    sources=[
        SourceRefDTO(source_name="SampleFeed", source_kind="feed", is_synthetic=True, external_id="sf-20418",
                     original_url="https://samplefeed.example/listings/sf-20418", collected_at=_at(28, 9)),
        SourceRefDTO(source_name="Manual entry", source_kind="manual", is_synthetic=False,
                     external_id="c874c76e15bc450f", original_url=None, collected_at=_at(24, 20)),
    ],
    price_history=[PricePointDTO(rent_cents=335_000, observed_at=_at(18)),
                   PricePointDTO(rent_cents=320_000, observed_at=_at(28, 9))],
    created_at=_at(18),
)

REPORT = ReportDTO(id=_id(6, 11), listing_id=KNICKERBOCKER, reason="wrong_value",
                   details="The bathroom count is 1, not 1.5.", status="open", created_at=_at(28, 21), resolved_at=None)

# --- administration ------------------------------------------------------------------

SOURCES = [
    SourceDTO(id=SAMPLEFEED, name="SampleFeed", kind="feed", enabled=True, is_synthetic=True,
              config={"url": "https://samplefeed.example/feed.json", "interval_minutes": 60},
              last_run_at=_at(29, 6), last_error=None, created_at=_at(10)),
    SourceDTO(id=MANUAL, name="Manual entry", kind="manual", enabled=True, is_synthetic=False, config={},
              last_run_at=None, last_error=None, created_at=_at(10)),
]

DUPLICATE = DuplicateDTO(
    id=_id(6, 1), confidence=0.8, status="queued", created_at=_at(28, 9), reviewed_at=None,
    a=DuplicateSideDTO(record_id=_id(5, 101), original_url="https://samplefeed.example/listings/sf-20418",
                       collected_at=_at(28, 9), listing=LISTINGS[0], listing_status="searchable"),
    b=DuplicateSideDTO(record_id=_id(5, 103), original_url=None, collected_at=_at(28, 10),
                       listing=ListingSummaryDTO(**{**vars(LISTINGS[0]), "id": KNICKERBOCKER_DUP, "title": None,
                                                    "has_conflicts": False}),
                       listing_status="under_review"),
)

# --- search --------------------------------------------------------------------------

SEARCH_RESULTS = Page(items=LISTINGS, total=3, limit=20, offset=0)

SAVED_SEARCHES = [
    SavedSearchDTO(id=_id(7, 1), name="2BR in Brooklyn under $3.5k",
                   criteria={"boroughs": ["brooklyn"], "max_rent_cents": 350_000, "min_bedrooms": 2},
                   weights={}, alerts_enabled=True, created_at=_at(21), updated_at=_at(21)),
]

DESTINATIONS = [
    CommuteDestinationDTO(id=_id(7, 11), label="NYU Tandon", address="6 MetroTech Center, Brooklyn, NY 11201",
                          latitude=40.6943, longitude=-73.9865, mode="transit", created_at=_at(21)),
    CommuteDestinationDTO(id=_id(7, 12), label="Climbing gym", address="575 Degraw St, Brooklyn, NY 11217",
                          latitude=None, longitude=None, mode="bike", created_at=_at(23)),
]

# --- comparison ----------------------------------------------------------------------

_COMPARED = [KNICKERBOCKER, STEINWAY, HARLEM]


def _row(key: str, label: str, direction: Direction | None, values: list[Any], best: tuple[int, ...] = (),
         formula: str | None = None) -> ComparisonRow:
    cells = [ComparisonCell(listing_id=lid, value=v, known=v is not None, best=i in best)
             for i, (lid, v) in enumerate(zip(_COMPARED, values, strict=True))]
    return ComparisonRow(key=key, label=label, direction=direction, formula=formula, cells=cells)


TABLE = ComparisonTableDTO(
    listings=LISTINGS,
    rows=[
        _row("advertised_rent_cents", "Advertised monthly rent", "lower", [320_000, 210_000, 415_000], best=(1,)),
        _row("net_effective_rent_cents", "Net-effective monthly rent", "lower", [295_000, None, None]),
        _row("broker_fee_cents", "Broker fee", "lower", [0, None, 415_000], best=(0,)),
        _row("price_per_sqft_cents", "Price per sq ft", "lower", [376, None, 377], best=(0,),
             formula="advertised monthly rent ÷ area in sq ft"),
        _row("borough", "Borough", None, ["brooklyn", "queens", "manhattan"]),
        _row("bedrooms", "Bedrooms", None, [2, 0, 3]),
        _row("area_sqft", "Area (sq ft)", "higher", [850, None, 1100], best=(2,)),
        _row("move_in_date", "Move-in date", None, [dt.date(2026, 12, 1), None, dt.date(2027, 1, 15)]),
        _row("commute", "Commute", None, [None, None, None]),
    ],
    notes=["Commute estimates are not available yet."],
)

_COMPARISON_FIELDS = {"id": _id(8, 1), "title": "Top three", "group_id": CREW,
                      "saved_by": _person(MAYA, "Maya Chen"), "saved_at": _at(26, 20), "shared_at": _at(26, 20),
                      "listing_ids": _COMPARED}

COMPARISON = ComparisonDTO(
    **_COMPARISON_FIELDS, table=TABLE, stale=True,
    changes=[ListingChangeDTO(listing_id=KNICKERBOCKER, state="changed", changed_fields=["advertised_rent_cents"]),
             ListingChangeDTO(listing_id=STEINWAY, state="unchanged", changed_fields=[]),
             ListingChangeDTO(listing_id=HARLEM, state="unchanged", changed_fields=[])],
)

COMPARISONS = [ComparisonSummaryDTO(**_COMPARISON_FIELDS)]

# --- room ----------------------------------------------------------------------------

MESSAGES = [  # newest first
    MessageDTO(id=_id(9, 3), group_id=CREW, author=_person(ALEX, "Alex Rivera"), listing_id=KNICKERBOCKER,
               comparison_id=None, body="Rent dropped to $3,200 on the Knickerbocker one!", sent_at=_at(28, 9, 40),
               reactions=[ReactionCountDTO(emoji="🎉", count=2, mine=True)]),
    MessageDTO(id=_id(9, 2), group_id=CREW, author=_person(SAM, "Sam Okafor"), listing_id=None,
               comparison_id=_id(8, 1), body="Harlem is big but the broker fee hurts.", sent_at=_at(27, 19, 5),
               reactions=[]),
    MessageDTO(id=_id(9, 1), group_id=CREW, author=PersonRef(id=None, name="Deleted user", deleted=True),
               listing_id=None, comparison_id=None, body="Count me out of Queens, sorry.", sent_at=_at(26, 22, 30),
               reactions=[ReactionCountDTO(emoji="👍", count=1, mine=False)]),
]

POLL = PollDTO(
    id=_id(9, 11), group_id=CREW, question="Which one do we tour first?", state="open", created_by=MAYA,
    created_at=_at(27, 20), closed_at=None, total_votes=3, my_vote=_id(9, 21),
    options=[PollOptionDTO(id=_id(9, 21), position=1, text="214 Knickerbocker Ave", votes=2),
             PollOptionDTO(id=_id(9, 22), position=2, text="560 W 144th St", votes=1),
             PollOptionDTO(id=_id(9, 23), position=3, text="Keep looking", votes=0)],
)

# --- notifications -------------------------------------------------------------------

NOTIFICATIONS = NotificationListDTO(total=3, unread=2, limit=20, offset=0, items=[
    NotificationDTO(id=_id(10, 3), kind="message", title="Alex Rivera in Bushwick crew: Rent dropped to $3,200…",
                    group_id=CREW, listing_id=None, created_at=_at(28, 9, 40), read=False, read_at=None),
    NotificationDTO(id=_id(10, 2), kind="price_change", title="214 Knickerbocker Ave: $3,350 → $3,200",
                    group_id=None, listing_id=KNICKERBOCKER, created_at=_at(28, 9), read=False, read_at=None),
    NotificationDTO(id=_id(10, 1), kind="new_match", title="New match for “2BR in Brooklyn under $3.5k”",
                    group_id=None, listing_id=KNICKERBOCKER, created_at=_at(18, 7), read=True, read_at=_at(18, 8)),
])

NOTIFICATION_SETTINGS = NotificationSettingsDTO(kinds=["new_match", "price_change", "removed", "message"],
                                                email=True, digest=False,
                                                quiet_start=dt.time(22, 0), quiet_end=dt.time(7, 0))

# --- route -> sample -----------------------------------------------------------------
# 204 routes need no entry: they answer 204 with no body.

FIXTURES: dict[str, Any] = {
    "POST /auth/sign-up": SESSION,
    "POST /auth/sign-in": SESSION,
    "GET /me": ME,
    "POST /groups": GROUP,
    "GET /groups": GROUPS,
    "GET /groups/{group_id}": GROUP,
    "POST /groups/{group_id}/invitations": SENT_INVITATIONS[0],
    "GET /groups/{group_id}/invitations": SENT_INVITATIONS,
    "POST /groups/{group_id}/transfer": GroupDetailDTO(**{**vars(GROUP), "my_role": "member", "members": [
        MemberDTO(user=m.user, role="member" if m.user.id == MAYA else "owner" if m.user.id == ALEX else m.role,
                  joined_at=m.joined_at) for m in GROUP.members]}),
    "GET /invitations": INCOMING_INVITATIONS,
    "POST /invitations/{invitation_id}/accept": GroupDetailDTO(
        id=_id(2, 2), name="Astoria search", created_at=_at(25), my_role="member",
        members=[MemberDTO(user=_person(_id(1, 4), "Priya Nair"), role="owner", joined_at=_at(25)),
                 MemberDTO(user=_person(MAYA, "Maya Chen"), role="member", joined_at=_at(29, 10))]),
    "POST /listings": CARD,
    "GET /listings/{listing_id}": CARD,
    "POST /listings/{listing_id}/reports": REPORT,
    "GET /admin/sources": SOURCES,
    "POST /admin/sources": SOURCES[0],
    "PATCH /admin/sources/{source_id}": SOURCES[0],
    "GET /admin/duplicates": Page(items=[DUPLICATE], total=1, limit=20, offset=0),
    "POST /admin/duplicates/{candidate_id}/merge": DuplicateDTO(**{**vars(DUPLICATE), "status": "merged",
                                                                   "reviewed_at": _at(29, 10)}),
    "POST /admin/duplicates/{candidate_id}/keep-separate": DuplicateDTO(**{**vars(DUPLICATE), "status": "separate",
                                                                           "reviewed_at": _at(29, 10)}),
    "POST /admin/duplicates/{candidate_id}/split": DuplicateDTO(**{**vars(DUPLICATE), "status": "separate",
                                                                   "reviewed_at": _at(29, 11)}),
    "GET /admin/reports": Page(items=[REPORT], total=1, limit=20, offset=0),
    "POST /admin/reports/{report_id}/resolve": ReportDTO(**{**vars(REPORT), "status": "resolved",
                                                            "resolved_at": _at(29, 10)}),
    "GET /search": SEARCH_RESULTS,
    "GET /saved-searches": SAVED_SEARCHES,
    "POST /saved-searches": SAVED_SEARCHES[0],
    "GET /saved-searches/{search_id}/results": Page(items=[LISTINGS[0]], total=1, limit=20, offset=0),
    "GET /me/commute-destinations": DESTINATIONS,
    "POST /me/commute-destinations": DESTINATIONS[0],
    "POST /comparisons/preview": TABLE,
    "POST /comparisons": COMPARISON,
    "GET /comparisons": COMPARISONS,
    "GET /comparisons/{comparison_id}": COMPARISON,
    "POST /comparisons/{comparison_id}/share": COMPARISON,
    "GET /groups/{group_id}/comparisons": COMPARISONS,
    "GET /groups/{group_id}/messages": MESSAGES,
    "POST /groups/{group_id}/messages": MESSAGES[0],
    "PUT /messages/{message_id}/reaction": MESSAGES[0].reactions,
    "DELETE /messages/{message_id}/reaction": [],
    "POST /groups/{group_id}/polls": POLL,
    "GET /groups/{group_id}/polls": [POLL],
    "GET /polls/{poll_id}": POLL,
    "PUT /polls/{poll_id}/vote": POLL,
    "POST /polls/{poll_id}/close": PollDTO(**{**vars(POLL), "state": "closed", "closed_at": _at(29, 10)}),
    "GET /notifications": NOTIFICATIONS,
    "POST /notifications/read-all": {"marked": 2},
    "POST /notifications/{notification_id}/read": NotificationDTO(**{**vars(NOTIFICATIONS.items[0]), "read": True,
                                                                    "read_at": _at(29, 10)}),
    "GET /me/notification-settings": NOTIFICATION_SETTINGS,
    "PUT /me/notification-settings": NOTIFICATION_SETTINGS,
}
