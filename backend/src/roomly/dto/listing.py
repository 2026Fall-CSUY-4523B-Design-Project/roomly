"""DTOs for Listing Submission and listing cards (§8.1.2.3, R-2.1, R-2.2).

Every listing attribute that may be Unknown is ``X | None``; ``unknown`` names the ones that
are, so the client labels them "Unknown" instead of guessing.
"""

import datetime as dt
import re
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import Field, StrictFloat, StrictInt, StringConstraints

from roomly.dto.base import DTO
from roomly.entity import DataReport, Listing

Borough = Literal["manhattan", "brooklyn", "queens", "bronx", "staten_island"]
Availability = Literal["available", "unavailable", "unknown"]
ReportReason = Literal["wrong_merge", "wrong_value", "unavailable", "other"]

ZIP_PATTERN = re.compile(r"^[0-9]{5}$")
URL_PATTERN = re.compile(r"^https?://\S+$")
MIN_LEASE_DAYS = 30  # R-2.1


class ManualListingRequest(DTO):
    """A listing typed in by a signed-in user. Leave a field out when it is not known."""

    address_line: str = Field(min_length=1, max_length=200)
    borough: Borough | None = None
    unit: str | None = Field(default=None, min_length=1, max_length=20)
    postal_code: str | None = Field(default=None, pattern=ZIP_PATTERN)
    title: str | None = Field(default=None, min_length=1, max_length=200)
    latitude: StrictFloat | None = Field(default=None, ge=-90, le=90)
    longitude: StrictFloat | None = Field(default=None, ge=-180, le=180)
    advertised_rent_cents: StrictInt | None = Field(default=None, ge=1, le=10_000_000)
    net_effective_rent_cents: StrictInt | None = Field(default=None, ge=1, le=10_000_000)
    lease_term_months: StrictInt | None = Field(default=None, ge=1, le=60)
    broker_fee_cents: StrictInt | None = Field(default=None, ge=0, le=10_000_000)
    monthly_fees_cents: StrictInt | None = Field(default=None, ge=0, le=1_000_000)
    bedrooms: StrictInt | None = Field(default=None, ge=0, le=20)
    bathrooms: StrictFloat | None = Field(default=None, ge=0, le=20)
    area_sqft: StrictInt | None = Field(default=None, ge=1, le=100_000)
    move_in_date: dt.date | None = None
    min_lease_days: StrictInt | None = Field(default=None, ge=1, le=3650)
    amenities: list[Annotated[str, StringConstraints(min_length=1, max_length=40)]] = Field(
        default_factory=list, max_length=40)
    availability: Availability = "unknown"
    original_url: str | None = Field(default=None, pattern=URL_PATTERN, max_length=2000)

    def check(self) -> list[tuple[str, str]]:
        problems = []
        if (self.latitude is None) != (self.longitude is None):
            problems.append(("longitude", "latitude and longitude must be given together"))
        if self.net_effective_rent_cents is not None and self.lease_term_months is None:
            problems.append(("lease_term_months", "net-effective rent needs the lease term it is spread over"))
        return problems


class ReportRequest(DTO):
    reason: ReportReason
    details: str | None = Field(default=None, min_length=1, max_length=2000)


class Coordinates(DTO):
    latitude: float
    longitude: float


class DerivedValue(DTO):
    """A calculated value with the formula that produced it (R-4.3). ``value`` is None when an input is Unknown."""

    value: int | None
    formula: str


class SourceRefDTO(DTO):
    """Provenance of one source record (R-2.2)."""

    source_name: str
    source_kind: str
    is_synthetic: bool
    external_id: str
    original_url: str | None
    collected_at: dt.datetime


class PricePointDTO(DTO):
    rent_cents: int
    observed_at: dt.datetime


_SUMMARY_UNKNOWABLE = ("advertised_rent_cents", "bedrooms", "bathrooms", "area_sqft", "move_in_date", "borough")
_CARD_UNKNOWABLE = _SUMMARY_UNKNOWABLE + (
    "net_effective_rent_cents", "lease_term_months", "broker_fee_cents", "monthly_fees_cents",
    "min_lease_days", "postal_code", "unit",
)


def _unknown(listing: Listing, names: tuple[str, ...]) -> list[str]:
    out = [n for n in names if getattr(listing, n) is None]
    if listing.latitude is None:
        out.append("coordinates")
    return out


class ListingSummaryDTO(DTO):
    """A search result or comparison column."""

    id: UUID
    title: str | None
    address_line: str | None
    unit: str | None
    borough: str | None
    advertised_rent_cents: int | None
    net_effective_rent_cents: int | None
    bedrooms: int | None
    bathrooms: float | None
    area_sqft: int | None
    move_in_date: dt.date | None
    amenities: list[str]
    coordinates: Coordinates | None
    availability: str
    is_synthetic: bool
    has_conflicts: bool
    updated_at: dt.datetime
    unknown: list[str]

    @classmethod
    def from_entity(cls, listing: Listing) -> ListingSummaryDTO:
        return cls(**_summary_fields(listing), unknown=_unknown(listing, _SUMMARY_UNKNOWABLE))


def _summary_fields(listing: Listing) -> dict[str, Any]:
    coords = None if listing.latitude is None else Coordinates(
        latitude=listing.latitude, longitude=listing.longitude)  # type: ignore[arg-type]
    return {
        "id": listing.id, "title": listing.title, "address_line": listing.address_line, "unit": listing.unit,
        "borough": listing.borough, "advertised_rent_cents": listing.advertised_rent_cents,
        "net_effective_rent_cents": listing.net_effective_rent_cents, "bedrooms": listing.bedrooms,
        "bathrooms": None if listing.bathrooms is None else float(listing.bathrooms), "area_sqft": listing.area_sqft,
        "move_in_date": listing.move_in_date, "amenities": list(listing.amenities), "coordinates": coords,
        "availability": listing.availability, "is_synthetic": listing.is_synthetic,
        "has_conflicts": bool(listing.conflicts), "updated_at": listing.updated_at,
    }


class ListingCardDTO(ListingSummaryDTO):
    """The full card: every value with its sources, conflicts and collection times (R-2.2)."""

    status: str
    merged_into_id: UUID | None
    postal_code: str | None
    lease_term_months: int | None
    broker_fee_cents: int | None
    monthly_fees_cents: int | None
    min_lease_days: int | None
    conflicts: dict[str, Any]
    price_per_sqft_cents: DerivedValue
    sources: list[SourceRefDTO]
    price_history: list[PricePointDTO]
    created_at: dt.datetime

    @classmethod
    def build(
        cls, listing: Listing, price_per_sqft: DerivedValue, sources: list[SourceRefDTO], history: list[PricePointDTO]
    ) -> ListingCardDTO:
        return cls(
            **_summary_fields(listing), unknown=_unknown(listing, _CARD_UNKNOWABLE),
            status=listing.status, merged_into_id=listing.merged_into_id, postal_code=listing.postal_code,
            lease_term_months=listing.lease_term_months, broker_fee_cents=listing.broker_fee_cents,
            monthly_fees_cents=listing.monthly_fees_cents, min_lease_days=listing.min_lease_days,
            conflicts=listing.conflicts, price_per_sqft_cents=price_per_sqft, sources=sources,
            price_history=history, created_at=listing.created_at,
        )


class ReportDTO(DTO):
    id: UUID
    listing_id: UUID
    reason: str
    details: str | None
    status: str
    created_at: dt.datetime
    resolved_at: dt.datetime | None

    @classmethod
    def from_entity(cls, r: DataReport) -> ReportDTO:
        return cls(id=r.id, listing_id=r.listing_id, reason=r.reason, details=r.details, status=r.status,
                   created_at=r.created_at, resolved_at=r.resolved_at)
