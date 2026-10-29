"""Entity classes of SSDS §9.1: one frozen dataclass per table row, field names = column names.

Mappers return these; services turn them into DTOs. ``None`` in a listing attribute means
"Unknown" and must be shown as such, never as 0 or "no".
"""

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from uuid import UUID

# --- accounts ------------------------------------------------------------------------


@dataclass(frozen=True)
class User:
    id: UUID
    email: str | None
    password_hash: str | None
    display_name: str | None
    role: str
    preferences: dict[str, Any]
    notify_kinds: list[str]
    notify_email: bool
    notify_digest: bool
    quiet_start: dt.time | None
    quiet_end: dt.time | None
    created_at: dt.datetime
    updated_at: dt.datetime
    deleted_at: dt.datetime | None

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"


@dataclass(frozen=True)
class Session:
    id: UUID
    user_id: UUID
    token_hash: bytes
    created_at: dt.datetime
    expires_at: dt.datetime
    revoked_at: dt.datetime | None


# --- groups --------------------------------------------------------------------------


@dataclass(frozen=True)
class Group:
    id: UUID
    name: str
    created_at: dt.datetime


@dataclass(frozen=True)
class Membership:
    id: UUID
    group_id: UUID
    user_id: UUID
    role: str
    joined_at: dt.datetime
    left_at: dt.datetime | None

    @property
    def is_owner(self) -> bool:
        return self.role == "owner"


@dataclass(frozen=True)
class Invitation:
    id: UUID
    group_id: UUID
    email: str
    invited_by: UUID | None
    status: str
    created_at: dt.datetime
    expires_at: dt.datetime
    responded_at: dt.datetime | None


# --- listings ------------------------------------------------------------------------


@dataclass(frozen=True)
class ListingSource:
    id: UUID
    name: str
    kind: str
    enabled: bool
    is_synthetic: bool
    config: dict[str, Any]
    last_run_at: dt.datetime | None
    last_error: str | None
    created_at: dt.datetime


@dataclass(frozen=True)
class Listing:
    id: UUID
    status: str
    merged_into_id: UUID | None
    title: str | None
    address_line: str | None
    unit: str | None
    borough: str | None
    postal_code: str | None
    latitude: float | None
    longitude: float | None
    advertised_rent_cents: int | None
    net_effective_rent_cents: int | None
    lease_term_months: int | None
    broker_fee_cents: int | None
    monthly_fees_cents: int | None
    bedrooms: int | None
    bathrooms: Decimal | None
    area_sqft: int | None
    move_in_date: dt.date | None
    min_lease_days: int | None
    amenities: list[str]
    availability: str
    conflicts: dict[str, Any]
    is_synthetic: bool
    created_at: dt.datetime
    updated_at: dt.datetime


@dataclass(frozen=True)
class SourceRecord:
    id: UUID
    source_id: UUID
    listing_id: UUID | None
    external_id: str
    original_url: str | None
    collected_at: dt.datetime
    raw_values: dict[str, Any]
    submitted_by: UUID | None
    created_at: dt.datetime


@dataclass(frozen=True)
class PricePoint:
    id: int
    listing_id: UUID
    source_record_id: UUID | None
    rent_cents: int
    observed_at: dt.datetime


@dataclass(frozen=True)
class DuplicateCandidate:
    id: UUID
    record_a_id: UUID
    record_b_id: UUID
    confidence: float
    status: str
    reviewed_by: UUID | None
    reviewed_at: dt.datetime | None
    created_at: dt.datetime


@dataclass(frozen=True)
class DataReport:
    id: UUID
    listing_id: UUID
    reporter_id: UUID | None
    reason: str
    details: str | None
    status: str
    created_at: dt.datetime
    resolved_by: UUID | None
    resolved_at: dt.datetime | None


# --- search and comparison -----------------------------------------------------------


@dataclass(frozen=True)
class CommuteDestination:
    id: UUID
    user_id: UUID
    label: str
    address: str | None
    latitude: float | None
    longitude: float | None
    mode: str
    created_at: dt.datetime


@dataclass(frozen=True)
class SavedSearch:
    id: UUID
    user_id: UUID
    name: str
    criteria: dict[str, Any]
    weights: dict[str, Any]
    alerts_enabled: bool
    last_matched_at: dt.datetime | None
    created_at: dt.datetime
    updated_at: dt.datetime


@dataclass(frozen=True)
class Comparison:
    id: UUID
    saved_by: UUID | None
    group_id: UUID | None
    title: str | None
    saved_at: dt.datetime
    shared_at: dt.datetime | None


@dataclass(frozen=True)
class ComparisonListing:
    comparison_id: UUID
    position: int
    listing_id: UUID
    snapshot: dict[str, Any]


# --- discussion ----------------------------------------------------------------------


@dataclass(frozen=True)
class Message:
    id: UUID
    group_id: UUID
    author_id: UUID | None
    listing_id: UUID | None
    comparison_id: UUID | None
    body: str
    sent_at: dt.datetime


@dataclass(frozen=True)
class Reaction:
    message_id: UUID
    user_id: UUID
    emoji: str
    reacted_at: dt.datetime


@dataclass(frozen=True)
class Poll:
    id: UUID
    group_id: UUID
    created_by: UUID | None
    question: str
    state: str
    created_at: dt.datetime
    closed_at: dt.datetime | None


@dataclass(frozen=True)
class PollOption:
    id: UUID
    poll_id: UUID
    position: int
    text: str


@dataclass(frozen=True)
class Vote:
    poll_id: UUID
    user_id: UUID
    option_id: UUID
    cast_at: dt.datetime


# --- notifications -------------------------------------------------------------------


@dataclass(frozen=True)
class Notification:
    id: UUID
    recipient_id: UUID
    kind: str
    event_id: UUID
    group_id: UUID | None
    listing_id: UUID | None
    title: str
    status: str
    email_status: str
    created_at: dt.datetime
    delivered_at: dt.datetime | None
    read_at: dt.datetime | None
