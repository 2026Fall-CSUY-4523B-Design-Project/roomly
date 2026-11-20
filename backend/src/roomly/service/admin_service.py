"""Listing Administration (§8.1.2.4): sources, the duplicate review queue, data reports (R-2.3, R-2.4).

Merging never moves source records: the newcomer's listing is marked ``merged`` and points
at the surviving listing, whose card then shows both records. A split clears that pointer and
withdraws the conflicts the merge recorded, so an incorrect merge can be undone.
"""

import datetime as dt
from decimal import Decimal
from typing import Any
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
from roomly.mapper.listing_mapper import (
    DuplicateMapper,
    ListingMapper,
    ReportMapper,
    SourceMapper,
    SourceRecordMapper,
)
from roomly.service.errors import Conflict, Forbidden, NotFound
from roomly.service.listing_service import in_search_scope

# Values a merge reconciles: fill what the survivor does not know, record what disagrees.
_MERGE_FIELDS = (
    "title", "address_line", "unit", "borough", "postal_code", "latitude", "longitude",
    "advertised_rent_cents", "net_effective_rent_cents", "lease_term_months", "broker_fee_cents",
    "monthly_fees_cents", "bedrooms", "bathrooms", "area_sqft", "move_in_date", "min_lease_days",
    "availability",
)


def _json_value(value: Any) -> Any:
    if isinstance(value, dt.date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


class AdminService:
    def __init__(self, db: Database) -> None:
        self.db = db

    def list_sources(self, admin: User) -> list[SourceDTO]:
        self._require_admin(admin)
        with self.db.transaction() as tx:
            return [SourceDTO.from_entity(s) for s in SourceMapper(tx).list_all()]

    def create_source(self, admin: User, req: CreateSourceRequest) -> SourceDTO:
        self._require_admin(admin)
        with self.db.transaction() as tx:
            sources = SourceMapper(tx)
            if sources.find_by_name(req.name) is not None:
                raise Conflict("A listing source with this name already exists.")
            source = sources.insert(req.name, req.kind, enabled=req.enabled, is_synthetic=req.is_synthetic,
                                    config=req.config)
            return SourceDTO.from_entity(source)

    def update_source(self, admin: User, source_id: UUID, req: UpdateSourceRequest) -> SourceDTO:
        self._require_admin(admin)
        present = req.model_fields_set
        with self.db.transaction() as tx:
            sources = SourceMapper(tx)
            if sources.find(source_id) is None:
                raise NotFound("Listing source not found.")
            name = req.name if "name" in present else None
            if name is not None:
                clash = sources.find_by_name(name)
                if clash is not None and clash.id != source_id:
                    raise Conflict("A listing source with this name already exists.")
            source = sources.update(
                source_id, name=name,
                enabled=req.enabled if "enabled" in present else None,
                config=req.config if "config" in present else None,
            )
            assert source is not None
            return SourceDTO.from_entity(source)

    def list_duplicates(self, admin: User, status: str, limit: int, offset: int) -> Page[DuplicateDTO]:
        self._require_admin(admin)
        with self.db.transaction() as tx:
            candidates, total = DuplicateMapper(tx).list_by_status(status, limit, offset)
            return Page[DuplicateDTO](items=[self._duplicate(tx, c) for c in candidates], total=total,
                                      limit=limit, offset=offset)

    def merge(self, admin: User, candidate_id: UUID) -> DuplicateDTO:
        self._require_admin(admin)
        with self.db.transaction() as tx:
            candidate = self._queued(tx, candidate_id)
            listings = ListingMapper(tx)
            records = SourceRecordMapper(tx)
            first = records.find(candidate.record_a_id)
            second = records.find(candidate.record_b_id)
            if first is None or second is None:
                raise NotFound("Source record not found.")
            survivors = listings.find(first.listing_id) if first.listing_id else None
            newcomers = listings.find(second.listing_id) if second.listing_id else None
            if survivors is None and newcomers is None:
                raise Conflict("Neither record belongs to a listing yet.")
            if survivors is None:
                survivors, newcomers = newcomers, None
            assert survivors is not None
            survivor = self._root(tx, listings, survivors)
            newcomer = self._root(tx, listings, newcomers) if newcomers is not None else None
            if newcomer is not None and newcomer.id != survivor.id:
                self._merge_into(tx, survivor, newcomer, first.id, second.id)
            reviewed = DuplicateMapper(tx).set_status(candidate.id, "merged", admin.id)
            return self._duplicate(tx, reviewed)

    def keep_separate(self, admin: User, candidate_id: UUID) -> DuplicateDTO:
        self._require_admin(admin)
        with self.db.transaction() as tx:
            candidate = self._queued(tx, candidate_id)
            listings = ListingMapper(tx)
            records = SourceRecordMapper(tx)
            for record_id in (candidate.record_a_id, candidate.record_b_id):
                record = records.find(record_id)
                listing = listings.find(record.listing_id) if record and record.listing_id else None
                if listing is not None and listing.status == "under_review":
                    listings.update(listing.id, {"status": "searchable" if in_search_scope(listing) else "excluded"})
            reviewed = DuplicateMapper(tx).set_status(candidate.id, "separate", admin.id)
            return self._duplicate(tx, reviewed)

    def split(self, admin: User, candidate_id: UUID) -> DuplicateDTO:
        """§8.1.2.4 alt. flow 3: undo an incorrect merge after a user report."""
        self._require_admin(admin)
        with self.db.transaction() as tx:
            candidate = DuplicateMapper(tx).lock(candidate_id)
            if candidate is None:
                raise NotFound("Duplicate candidate not found.")
            if candidate.status != "merged":
                raise Conflict("Only a merged pair can be split.")
            listings = ListingMapper(tx)
            records = SourceRecordMapper(tx)
            split_listing = None
            for record_id in (candidate.record_a_id, candidate.record_b_id):
                record = records.find(record_id)
                listing = listings.find(record.listing_id) if record and record.listing_id else None
                if listing is not None and listing.status == "merged":
                    split_listing = listing
                    break
            if split_listing is None:
                raise Conflict("The merged listing no longer points at a surviving listing.")
            self._drop_conflicts(tx, split_listing, candidate)
            listings.update(split_listing.id, {
                "status": "searchable" if in_search_scope(split_listing) else "excluded",
                "merged_into_id": None,
            })
            reviewed = DuplicateMapper(tx).set_status(candidate.id, "separate", admin.id)
            return self._duplicate(tx, reviewed)

    def list_reports(self, admin: User, status: str, limit: int, offset: int) -> Page[ReportDTO]:
        self._require_admin(admin)
        with self.db.transaction() as tx:
            reports, total = ReportMapper(tx).list_by_status(status, limit, offset)
            return Page[ReportDTO](items=[ReportDTO.from_entity(r) for r in reports], total=total,
                                   limit=limit, offset=offset)

    def resolve_report(self, admin: User, report_id: UUID, req: ResolveReportRequest) -> ReportDTO:
        self._require_admin(admin)
        with self.db.transaction() as tx:
            reports = ReportMapper(tx)
            report = reports.resolve(report_id, req.status, admin.id)
            if report is None:
                if reports.find(report_id) is None:
                    raise NotFound("Report not found.")
                raise Conflict("This report has already been closed.")
            return ReportDTO.from_entity(report)

    @staticmethod
    def _require_admin(admin: User) -> None:
        if not admin.is_admin:
            raise Forbidden("Administrators only.")

    @staticmethod
    def _queued(tx: Tx, candidate_id: UUID) -> DuplicateCandidate:
        candidate = DuplicateMapper(tx).lock(candidate_id)
        if candidate is None:
            raise NotFound("Duplicate candidate not found.")
        if candidate.status != "queued":
            raise Conflict("This pair has already been reviewed.")
        return candidate

    @staticmethod
    def _root(tx: Tx, listings: ListingMapper, listing: Listing) -> Listing:
        """Follow a merge pointer to the listing that actually owns the card."""
        seen: set[UUID] = set()
        while listing.status == "merged" and listing.merged_into_id is not None and listing.id not in seen:
            seen.add(listing.id)
            parent = listings.find(listing.merged_into_id)
            if parent is None:
                break
            listing = parent
        return listing

    @staticmethod
    def _drop_conflicts(tx: Tx, merged_listing: Listing, candidate: DuplicateCandidate) -> None:
        """A split withdraws the disagreements that came from the pair."""
        survivor = ListingMapper(tx).find(merged_listing.merged_into_id) if merged_listing.merged_into_id else None
        if survivor is None or not survivor.conflicts:
            return
        records = {str(candidate.record_a_id), str(candidate.record_b_id)}
        cleaned: dict[str, Any] = {}
        for field, rows in survivor.conflicts.items():
            if not isinstance(rows, list):
                cleaned[field] = rows
                continue
            kept = [row for row in rows if not (isinstance(row, dict) and str(row.get("source_record_id")) in records)]
            if kept:
                cleaned[field] = kept
        if cleaned != survivor.conflicts:
            ListingMapper(tx).update(survivor.id, {"conflicts": cleaned})

    @staticmethod
    def _merge_into(tx: Tx, survivor: Listing, newcomer: Listing, first_record: UUID, second_record: UUID) -> None:
        """Fill the survivor's Unknown values and record disagreements, then mark the other listing merged."""
        update: dict[str, Any] = {}
        conflicts: dict[str, Any] = dict(survivor.conflicts)
        for field in _MERGE_FIELDS:
            mine, theirs = getattr(survivor, field), getattr(newcomer, field)
            if mine is None and theirs is not None:
                update[field] = theirs
            elif mine is not None and theirs is not None and mine != theirs:
                rows = conflicts.get(field, [])
                if not any(row.get("value") == _json_value(theirs) for row in rows):
                    conflicts[field] = [
                        *rows,
                        {"source_record_id": str(first_record), "value": _json_value(mine)},
                        {"source_record_id": str(second_record), "value": _json_value(theirs)},
                    ]
        if conflicts != survivor.conflicts:
            update["conflicts"] = conflicts
        if update:
            ListingMapper(tx).update(survivor.id, update)
        ListingMapper(tx).set_status(newcomer.id, "merged", survivor.id)

    @staticmethod
    def _duplicate(tx: Tx, candidate: DuplicateCandidate) -> DuplicateDTO:
        return DuplicateDTO(
            id=candidate.id, confidence=candidate.confidence, status=candidate.status,
            created_at=candidate.created_at, reviewed_at=candidate.reviewed_at,
            a=AdminService._side(tx, candidate.record_a_id),
            b=AdminService._side(tx, candidate.record_b_id),
        )

    @staticmethod
    def _side(tx: Tx, record_id: UUID) -> DuplicateSideDTO:
        record = SourceRecordMapper(tx).find(record_id)
        if record is None:
            raise NotFound("Source record not found.")
        listing = ListingMapper(tx).find(record.listing_id) if record.listing_id else None
        return DuplicateSideDTO(
            record_id=record.id, original_url=record.original_url, collected_at=record.collected_at,
            listing=None if listing is None else ListingSummaryDTO.from_entity(listing),
            listing_status=None if listing is None else listing.status,
        )
