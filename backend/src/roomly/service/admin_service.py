"""Listing Administration (§8.1.2.4): sources, the duplicate review queue, data reports (R-2.3, R-2.4).

Merging never moves source records: the newcomer's listing is marked ``merged`` and points
at the surviving listing, whose card then shows both records. A split clears that pointer,
so an incorrect merge is fully reversible.
"""

import logging
from uuid import UUID

from roomly.db import Database, Tx
from roomly.dto.admin import (
    CreateSourceRequest,
    DuplicateDTO,
    DuplicateSideDTO,
    ResolveReportRequest,
    SourceDTO,
    UpdateSourceRequest,
)
from roomly.dto.common import Page
from roomly.dto.listing import ListingSummaryDTO, ReportDTO
from roomly.entity import DuplicateCandidate, Listing, User
from roomly.mapper import (
    DuplicateMapper,
    ListingMapper,
    ReportMapper,
    SourceMapper,
    SourceRecordMapper,
)
from roomly.service.access import require_admin
from roomly.service.errors import Conflict, NotFound
from roomly.service.listing_service import in_search_scope

logger = logging.getLogger(__name__)


class AdminService:
    def __init__(self, db: Database) -> None:
        self.db = db

    # --- sources ---------------------------------------------------------------------

    def list_sources(self, admin: User) -> list[SourceDTO]:
        require_admin(admin)
        with self.db.transaction() as tx:
            return [SourceDTO.from_entity(s) for s in SourceMapper(tx).list_all()]

    def create_source(self, admin: User, req: CreateSourceRequest) -> SourceDTO:
        require_admin(admin)
        with self.db.transaction() as tx:
            sources = SourceMapper(tx)
            if sources.find_by_name(req.name) is not None:
                raise Conflict("a source with that name already exists")
            source = sources.insert(req.name, req.kind, enabled=req.enabled, is_synthetic=req.is_synthetic,
                                    config=req.config)
        logger.info("admin=%s created source=%s kind=%s", admin.id, source.id, source.kind)
        return SourceDTO.from_entity(source)

    def update_source(self, admin: User, source_id: UUID, req: UpdateSourceRequest) -> SourceDTO:
        require_admin(admin)
        with self.db.transaction() as tx:
            sources = SourceMapper(tx)
            if req.name is not None:
                same = sources.find_by_name(req.name)
                if same is not None and same.id != source_id:
                    raise Conflict("a source with that name already exists")
            source = sources.update(source_id, name=req.name, enabled=req.enabled, config=req.config)
            if source is None:
                raise NotFound("source not found")
        logger.info("admin=%s updated source=%s enabled=%s", admin.id, source.id, source.enabled)
        return SourceDTO.from_entity(source)

    # --- duplicate review ------------------------------------------------------------

    def list_duplicates(self, admin: User, status: str, limit: int, offset: int) -> Page[DuplicateDTO]:
        require_admin(admin)
        with self.db.transaction() as tx:
            rows, total = DuplicateMapper(tx).list_by_status(status, limit, offset)
            items = [self._candidate_dto(tx, c) for c in rows]
        return Page(items=items, total=total, limit=limit, offset=offset)

    def merge(self, admin: User, candidate_id: UUID) -> DuplicateDTO:
        require_admin(admin)
        with self.db.transaction() as tx:
            candidate, keep, absorb = self._pair(tx, candidate_id, expect="queued")
            if keep.status == "merged":
                raise Conflict("the surviving listing was itself merged; review that pair first")
            ListingMapper(tx).set_status(absorb.id, "merged", merged_into_id=keep.id)
            candidate = DuplicateMapper(tx).set_status(candidate.id, "merged", admin.id)
            dto = self._candidate_dto(tx, candidate)
        logger.info("admin=%s merged candidate=%s listing=%s into=%s", admin.id, candidate_id, absorb.id, keep.id)
        return dto

    def keep_separate(self, admin: User, candidate_id: UUID) -> DuplicateDTO:
        require_admin(admin)
        with self.db.transaction() as tx:
            candidate, _, held = self._pair(tx, candidate_id, expect="queued")
            candidate = DuplicateMapper(tx).set_status(candidate.id, "separate", admin.id)
            if held.status == "under_review" and DuplicateMapper(tx).count_queued_for_listing(held.id) == 0:
                self._release(tx, held)
            dto = self._candidate_dto(tx, candidate)
        logger.info("admin=%s kept candidate=%s separate", admin.id, candidate_id)
        return dto

    def split(self, admin: User, candidate_id: UUID) -> DuplicateDTO:
        """§8.1.2.4 alt. flow 3: undo an incorrect merge after a user report."""
        require_admin(admin)
        with self.db.transaction() as tx:
            candidate, keep, absorbed = self._pair(tx, candidate_id, expect="merged")
            if absorbed.merged_into_id != keep.id:
                raise Conflict("that merge was already changed")
            self._release(tx, absorbed)
            candidate = DuplicateMapper(tx).set_status(candidate.id, "separate", admin.id)
            dto = self._candidate_dto(tx, candidate)
        logger.info("admin=%s split candidate=%s listing=%s", admin.id, candidate_id, absorbed.id)
        return dto

    # --- data reports ----------------------------------------------------------------

    def list_reports(self, admin: User, status: str, limit: int, offset: int) -> Page[ReportDTO]:
        require_admin(admin)
        with self.db.transaction() as tx:
            rows, total = ReportMapper(tx).list_by_status(status, limit, offset)
        return Page(items=[ReportDTO.from_entity(r) for r in rows], total=total, limit=limit, offset=offset)

    def resolve_report(self, admin: User, report_id: UUID, req: ResolveReportRequest) -> ReportDTO:
        require_admin(admin)
        with self.db.transaction() as tx:
            report = ReportMapper(tx).resolve(report_id, req.status, admin.id)
            if report is None:
                raise NotFound("no open report with that id")
        logger.info("admin=%s %s report=%s", admin.id, req.status, report_id)
        return ReportDTO.from_entity(report)

    # --- helpers ---------------------------------------------------------------------

    def _pair(self, tx: Tx, candidate_id: UUID, *, expect: str) -> tuple[DuplicateCandidate, Listing, Listing]:
        candidate = DuplicateMapper(tx).lock(candidate_id)
        if candidate is None:
            raise NotFound("duplicate candidate not found")
        if candidate.status != expect:
            raise Conflict(f"candidate is {candidate.status}, expected {expect}")
        records = SourceRecordMapper(tx)
        a, b = records.find(candidate.record_a_id), records.find(candidate.record_b_id)
        if a is None or b is None or a.listing_id is None or b.listing_id is None or a.listing_id == b.listing_id:
            raise Conflict("candidate records no longer point at two listings")
        listings = ListingMapper(tx)
        keep, other = listings.lock(a.listing_id), listings.lock(b.listing_id)
        assert keep is not None and other is not None
        return candidate, keep, other

    def _release(self, tx: Tx, listing: Listing) -> None:
        status = "searchable" if in_search_scope(listing.borough, listing.min_lease_days) else "excluded"
        ListingMapper(tx).set_status(listing.id, status)

    def _candidate_dto(self, tx: Tx, c: DuplicateCandidate) -> DuplicateDTO:
        records = SourceRecordMapper(tx)
        listings = ListingMapper(tx)

        def side(record_id: UUID) -> DuplicateSideDTO:
            record = records.find(record_id)
            assert record is not None
            listing = listings.find(record.listing_id) if record.listing_id else None
            return DuplicateSideDTO(record_id=record.id, original_url=record.original_url,
                                    collected_at=record.collected_at,
                                    listing=ListingSummaryDTO.from_entity(listing) if listing else None,
                                    listing_status=listing.status if listing else None)

        return DuplicateDTO(id=c.id, confidence=c.confidence, status=c.status, created_at=c.created_at,
                            reviewed_at=c.reviewed_at, a=side(c.record_a_id), b=side(c.record_b_id))
