"""Listing cards, manual Listing Submission and data reports (R-2.1, R-2.2, R-2.3).

Feed ingestion (IngestionService, SourceAdapter, the SampleFeed simulator) reuses
``normalize_address`` / ``in_search_scope`` / ``hold_if_possible_duplicate`` when it lands.
"""

import dataclasses
import datetime as dt
import json
import logging
import re
import uuid
from typing import Any
from uuid import UUID

from roomly.db import Database, Tx
from roomly.dto.listing import (
    MIN_LEASE_DAYS,
    DerivedValue,
    ListingCardDTO,
    ManualListingRequest,
    PricePointDTO,
    ReportDTO,
    ReportRequest,
    SourceRefDTO,
)
from roomly.entity import Listing, ListingSource, SourceRecord, User
from roomly.mapper import (
    DuplicateMapper,
    ListingMapper,
    PriceHistoryMapper,
    ReportMapper,
    SourceMapper,
    SourceRecordMapper,
)
from roomly.service.errors import Forbidden, NotFound

logger = logging.getLogger(__name__)

MANUAL_SOURCE = "Manual entry"
SAME_UNIT_CONFIDENCE = 0.8   # same address and unit: likely, never confirmed (glossary: Deduplication)
PRICE_PER_SQFT_FORMULA = "advertised monthly rent ÷ area in sq ft"

_SPACES = re.compile(r"\s+")


def normalize_address(text: str) -> str:
    return _SPACES.sub(" ", text).strip()


def normalize_amenities(items: list[str]) -> list[str]:
    return sorted({_SPACES.sub(" ", a).strip().lower() for a in items if a.strip()})


def in_search_scope(borough: str | None, min_lease_days: int | None) -> bool:
    """R-2.1: an identified NYC rental of at least 30 days. Unknown borough or term is not identified."""
    return borough is not None and min_lease_days is not None and min_lease_days >= MIN_LEASE_DAYS


def price_per_sqft(rent_cents: int | None, area_sqft: int | None) -> DerivedValue:
    """R-4.3: known monthly advertised rent over known positive area, rounded half up to a cent."""
    if rent_cents is None or area_sqft is None or area_sqft <= 0:
        return DerivedValue(value=None, formula=PRICE_PER_SQFT_FORMULA)
    return DerivedValue(value=(2 * rent_cents + area_sqft) // (2 * area_sqft), formula=PRICE_PER_SQFT_FORMULA)


def json_safe(value: Any) -> Any:
    """Dataclass / dates / UUIDs -> plain JSON values, for jsonb columns."""
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        value = dataclasses.asdict(value)
    return json.loads(json.dumps(value, default=str))


def hold_if_possible_duplicate(tx: Tx, listing: Listing, record: SourceRecord) -> bool:
    """§8.1.2.3 alt. flow 3: an uncertain match stays separate and goes to the review queue."""
    if listing.address_line is None:
        return False
    matches = [m for m in ListingMapper(tx).find_same_unit(listing.postal_code, listing.address_line, listing.unit)
               if m.id != listing.id]
    if not matches:
        return False
    existing = SourceRecordMapper(tx).latest_for_listing(matches[0].id)
    if existing is None:
        return False
    ListingMapper(tx).set_status(listing.id, "under_review")
    DuplicateMapper(tx).insert(existing.id, record.id, SAME_UNIT_CONFIDENCE)
    logger.info("possible duplicate queued listing=%s matches=%s", listing.id, matches[0].id)
    return True


def build_card(tx: Tx, listing: Listing) -> ListingCardDTO:
    sources = [SourceRefDTO(source_name=v.source_name, source_kind=v.source_kind, is_synthetic=v.is_synthetic,
                            external_id=v.external_id, original_url=v.original_url, collected_at=v.collected_at)
               for v in SourceRecordMapper(tx).views_for_card(listing.id)]
    history = [PricePointDTO(rent_cents=p.rent_cents, observed_at=p.observed_at)
               for p in PriceHistoryMapper(tx).list_for_listing(listing.id)]
    return ListingCardDTO.build(listing, price_per_sqft(listing.advertised_rent_cents, listing.area_sqft),
                                sources, history)


class ListingService:
    def __init__(self, db: Database) -> None:
        self.db = db

    def card(self, listing_id: UUID) -> ListingCardDTO:
        with self.db.transaction() as tx:
            listing = ListingMapper(tx).find(listing_id)
            if listing is None:
                raise NotFound("listing not found")
            return build_card(tx, listing)

    def submit_manual(self, user: User, req: ManualListingRequest) -> ListingCardDTO:
        """§8.1.2.3 basic flow for a manual entry: store the record, normalize, check for duplicates."""
        now = dt.datetime.now(dt.UTC)
        address = normalize_address(req.address_line)
        searchable = in_search_scope(req.borough, req.min_lease_days)
        with self.db.transaction() as tx:
            source = self._manual_source(tx)
            listing = ListingMapper(tx).insert({
                "status": "searchable" if searchable else "excluded",
                "title": req.title, "address_line": address, "unit": req.unit, "borough": req.borough,
                "postal_code": req.postal_code, "latitude": req.latitude, "longitude": req.longitude,
                "advertised_rent_cents": req.advertised_rent_cents,
                "net_effective_rent_cents": req.net_effective_rent_cents, "lease_term_months": req.lease_term_months,
                "broker_fee_cents": req.broker_fee_cents, "monthly_fees_cents": req.monthly_fees_cents,
                "bedrooms": req.bedrooms, "bathrooms": req.bathrooms, "area_sqft": req.area_sqft,
                "move_in_date": req.move_in_date, "min_lease_days": req.min_lease_days,
                "amenities": normalize_amenities(req.amenities), "availability": req.availability,
                "is_synthetic": source.is_synthetic,
            })
            record = SourceRecordMapper(tx).insert(
                source_id=source.id, listing_id=listing.id, external_id=uuid.uuid4().hex,
                original_url=req.original_url, collected_at=now, raw_values=json_safe(req), submitted_by=user.id,
            )
            assert record is not None  # fresh external id: cannot collide
            if req.advertised_rent_cents is not None:
                PriceHistoryMapper(tx).insert(listing.id, record.id, req.advertised_rent_cents, now)
            if searchable:
                hold_if_possible_duplicate(tx, listing, record)
            listing = ListingMapper(tx).find(listing.id)
            assert listing is not None
            card = build_card(tx, listing)
        logger.info("manual listing submitted listing=%s status=%s by=%s", card.id, card.status, user.id)
        return card

    def report(self, user: User, listing_id: UUID, req: ReportRequest) -> ReportDTO:
        with self.db.transaction() as tx:
            if ListingMapper(tx).find(listing_id) is None:
                raise NotFound("listing not found")
            report = ReportMapper(tx).insert(listing_id, user.id, req.reason, req.details)
        logger.info("data report filed report=%s listing=%s reason=%s", report.id, listing_id, req.reason)
        return ReportDTO.from_entity(report)

    def _manual_source(self, tx: Tx) -> ListingSource:
        sources = SourceMapper(tx)
        source = sources.find_by_name(MANUAL_SOURCE)
        if source is None:
            source = sources.insert(MANUAL_SOURCE, "manual", enabled=True, is_synthetic=False, config={})
        if not source.enabled:
            raise Forbidden("manual entry is turned off by the administrators")
        return source
