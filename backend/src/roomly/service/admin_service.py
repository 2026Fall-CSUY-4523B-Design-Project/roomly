"""Listing Administration (§8.1.2.4): sources, the duplicate review queue, data reports (R-2.3, R-2.4).

Merging never moves source records: the newcomer's listing is marked ``merged`` and points
at the surviving listing, whose card then shows both records. A split clears that pointer,
so an incorrect merge is fully reversible.
"""

from uuid import UUID

from roomly.db import Database
from roomly.dto.admin import (
    CreateSourceRequest,
    DuplicateDTO,
    ResolveReportRequest,
    SourceDTO,
    UpdateSourceRequest,
)
from roomly.dto.common import Page
from roomly.dto.listing import ReportDTO
from roomly.entity import User


class AdminService:
    def __init__(self, db: Database) -> None:
        self.db = db

    def list_sources(self, admin: User) -> list[SourceDTO]:
        raise NotImplementedError

    def create_source(self, admin: User, req: CreateSourceRequest) -> SourceDTO:
        raise NotImplementedError

    def update_source(self, admin: User, source_id: UUID, req: UpdateSourceRequest) -> SourceDTO:
        raise NotImplementedError

    def list_duplicates(self, admin: User, status: str, limit: int, offset: int) -> Page[DuplicateDTO]:
        raise NotImplementedError

    def merge(self, admin: User, candidate_id: UUID) -> DuplicateDTO:
        raise NotImplementedError

    def keep_separate(self, admin: User, candidate_id: UUID) -> DuplicateDTO:
        raise NotImplementedError

    def split(self, admin: User, candidate_id: UUID) -> DuplicateDTO:
        """§8.1.2.4 alt. flow 3: undo an incorrect merge after a user report."""
        raise NotImplementedError

    def list_reports(self, admin: User, status: str, limit: int, offset: int) -> Page[ReportDTO]:
        raise NotImplementedError

    def resolve_report(self, admin: User, report_id: UUID, req: ResolveReportRequest) -> ReportDTO:
        raise NotImplementedError
