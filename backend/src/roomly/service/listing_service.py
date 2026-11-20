"""Listing cards, manual Listing Submission and data reports (R-2.1, R-2.2, R-2.3).

Feed ingestion (IngestionService, SourceAdapter, the SampleFeed simulator) reuses
``normalize_address`` / ``in_search_scope`` / ``hold_if_possible_duplicate`` when it lands.
"""

import datetime as dt
from uuid import UUID, uuid4

from roomly.db import Database, Tx
from roomly.dto.listing import (
    DerivedValue,
    ListingCardDTO,
    ManualListingRequest,
    PricePointDTO,
    ReportDTO,
    ReportRequest,
    SourceRefDTO,
)
from roomly.entity import Listing, ListingSource, User
from roomly.mapper.listing_mapper import (
    DuplicateMapper,
    ListingMapper,
    PriceHistoryMapper,
    ReportMapper,
    SourceMapper,
    SourceRecordMapper,
)
from roomly.service.errors import NotFound

MIN_LEASE_DAYS = 30   # R-2.1
MANUAL_SOURCE = "Manual entry"
PRICE_PER_SQFT_FORMULA = "advertised monthly rent ÷ area in sq ft"


def normalize_address(address: str) -> str:
    """One spelling for matching: trimmed, single spaces."""
    return " ".join(address.split())


def in_search_scope(listing: Listing) -> bool:
    """R-2.1: a searchable listing is in a borough and leases for at least 30 days."""
    return listing.borough is not None and listing.min_lease_days is not None and listing.min_lease_days >= MIN_LEASE_DAYS


def price_per_sqft(listing: Listing) -> DerivedValue:
    rent, area = listing.advertised_rent_cents, listing.area_sqft
    value = None if rent is None or area is None or area <= 0 else round(rent / area)
    return DerivedValue(value=value, formula=PRICE_PER_SQFT_FORMULA)


class ListingService:
    def __init__(self, db: Database) -> None:
        self.db = db

    def card(self, listing_id: UUID) -> ListingCardDTO:
        with self.db.transaction() as tx:
            listing = ListingMapper(tx).find(listing_id)
            if listing is None:
                raise NotFound("Listing not found.")
            return self._card(tx, listing)

    def submit_manual(self, user: User, req: ManualListingRequest) -> ListingCardDTO:
        """§8.1.2.3 basic flow for a manual entry: store the record, normalize, check for duplicates."""
        address = normalize_address(req.address_line)
        values = req.model_dump(exclude={"original_url"}, mode="python")
        values["address_line"] = address
        values["is_synthetic"] = False
        now = dt.datetime.now(dt.UTC)
        with self.db.transaction() as tx:
            listings = ListingMapper(tx)
            candidates = listings.find_same_unit(req.postal_code, address, req.unit)
            values["status"] = "under_review" if candidates else (
                "searchable" if _scope_values(values) else "excluded")
            listing = listings.insert(values)

            source = self._manual_source(tx)
            record = SourceRecordMapper(tx).insert(
                source_id=source.id, listing_id=listing.id, external_id=uuid4().hex,
                original_url=req.original_url, collected_at=now, raw_values=req.model_dump(mode="json"),
                submitted_by=user.id)
            assert record is not None, "a fresh external_id cannot collide"
            if req.advertised_rent_cents is not None:
                PriceHistoryMapper(tx).insert(listing.id, record.id, req.advertised_rent_cents, now)

            duplicates = DuplicateMapper(tx)
            for candidate in candidates:
                previous = SourceRecordMapper(tx).latest_for_listing(candidate.id)
                if previous is not None and not duplicates.exists_pair(previous.id, record.id):
                    duplicates.insert(previous.id, record.id, 0.8)
            return self._card(tx, listing)

    def report(self, user: User, listing_id: UUID, req: ReportRequest) -> ReportDTO:
        with self.db.transaction() as tx:
            if ListingMapper(tx).find(listing_id) is None:
                raise NotFound("Listing not found.")
            report = ReportMapper(tx).insert(listing_id, user.id, req.reason, req.details)
            return ReportDTO.from_entity(report)

    @staticmethod
    def _manual_source(tx: Tx) -> ListingSource:
        sources = SourceMapper(tx)
        source = sources.find_by_name(MANUAL_SOURCE)
        if source is None:
            source = sources.insert(MANUAL_SOURCE, "manual", enabled=True, is_synthetic=False, config={})
        return source

    @staticmethod
    def _card(tx: Tx, listing: Listing) -> ListingCardDTO:
        sources = [SourceRefDTO(source_name=v.source_name, source_kind=v.source_kind,
                                is_synthetic=v.is_synthetic, external_id=v.external_id,
                                original_url=v.original_url, collected_at=v.collected_at)
                   for v in SourceRecordMapper(tx).views_for_card(listing.id)]
        history = [PricePointDTO(rent_cents=p.rent_cents, observed_at=p.observed_at)
                   for p in PriceHistoryMapper(tx).list_for_listing(listing.id)]
        return ListingCardDTO.build(listing, price_per_sqft(listing), sources, history)


def _scope_values(values: dict[str, object]) -> bool:
    borough, min_lease_days = values.get("borough"), values.get("min_lease_days")
    return borough is not None and isinstance(min_lease_days, int) and min_lease_days >= MIN_LEASE_DAYS
