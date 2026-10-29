"""Listing cards, manual Listing Submission and data reports (R-2.1, R-2.2, R-2.3).

Feed ingestion (IngestionService, SourceAdapter, the SampleFeed simulator) reuses
``normalize_address`` / ``in_search_scope`` / ``hold_if_possible_duplicate`` when it lands.
"""

from uuid import UUID

from roomly.db import Database
from roomly.dto.listing import (
    ListingCardDTO,
    ManualListingRequest,
    ReportDTO,
    ReportRequest,
)
from roomly.entity import User


class ListingService:
    def __init__(self, db: Database) -> None:
        self.db = db

    def card(self, listing_id: UUID) -> ListingCardDTO:
        raise NotImplementedError

    def submit_manual(self, user: User, req: ManualListingRequest) -> ListingCardDTO:
        """§8.1.2.3 basic flow for a manual entry: store the record, normalize, check for duplicates."""
        raise NotImplementedError

    def report(self, user: User, listing_id: UUID, req: ReportRequest) -> ReportDTO:
        raise NotImplementedError
