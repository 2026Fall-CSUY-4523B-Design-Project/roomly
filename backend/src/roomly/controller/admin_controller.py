"""Listing Administration use case (§8.1.2.4): /admin. Every route requires the administrator role.

Administrators have no route into group rooms: group endpoints check current membership and
an administrator can never be a member (enforced in GroupService and by a database trigger).
"""

from typing import Literal
from uuid import UUID

from fastapi import APIRouter

from roomly.controller.base import CurrentUser, Limit, Offset, Svc
from roomly.dto.admin import (
    CreateSourceRequest,
    DuplicateDTO,
    ResolveReportRequest,
    SourceDTO,
    UpdateSourceRequest,
)
from roomly.dto.common import Page
from roomly.dto.listing import ReportDTO

router = APIRouter(prefix="/admin", tags=["admin"])

CandidateState = Literal["queued", "merged", "separate"]
ReportState = Literal["open", "resolved", "dismissed"]


@router.get("/sources", summary="Configured listing sources")
def list_sources(user: CurrentUser, svc: Svc) -> list[SourceDTO]:
    return svc.admin.list_sources(user)


@router.post("/sources", status_code=201, summary="Add a listing source")
def create_source(req: CreateSourceRequest, user: CurrentUser, svc: Svc) -> SourceDTO:
    return svc.admin.create_source(user, req)


@router.patch("/sources/{source_id}", summary="Enable, disable, rename or reconfigure a source")
def update_source(source_id: UUID, req: UpdateSourceRequest, user: CurrentUser, svc: Svc) -> SourceDTO:
    return svc.admin.update_source(user, source_id, req)


@router.get("/duplicates", summary="The duplicate review queue")
def list_duplicates(user: CurrentUser, svc: Svc, status: CandidateState = "queued", limit: Limit = 20,
                    offset: Offset = 0) -> Page[DuplicateDTO]:
    return svc.admin.list_duplicates(user, status, limit, offset)


@router.post("/duplicates/{candidate_id}/merge", summary="Merge the pair into one listing")
def merge(candidate_id: UUID, user: CurrentUser, svc: Svc) -> DuplicateDTO:
    return svc.admin.merge(user, candidate_id)


@router.post("/duplicates/{candidate_id}/keep-separate", summary="Keep the pair as two listings")
def keep_separate(candidate_id: UUID, user: CurrentUser, svc: Svc) -> DuplicateDTO:
    return svc.admin.keep_separate(user, candidate_id)


@router.post("/duplicates/{candidate_id}/split", summary="Undo an incorrect merge")
def split(candidate_id: UUID, user: CurrentUser, svc: Svc) -> DuplicateDTO:
    return svc.admin.split(user, candidate_id)


@router.get("/reports", summary="Data reports from users")
def list_reports(user: CurrentUser, svc: Svc, status: ReportState = "open", limit: Limit = 20,
                 offset: Offset = 0) -> Page[ReportDTO]:
    return svc.admin.list_reports(user, status, limit, offset)


@router.post("/reports/{report_id}/resolve", summary="Resolve or dismiss a report")
def resolve_report(report_id: UUID, req: ResolveReportRequest, user: CurrentUser, svc: Svc) -> ReportDTO:
    return svc.admin.resolve_report(user, report_id, req)
