"""Listing Administration use case (§8.1.2.4): /admin. Every route requires the administrator role.

Administrators have no route into group rooms: group endpoints check current membership and
an administrator can never be a member (enforced in GroupService and by a database trigger).
"""

from fastapi_reborn import APIRouter, Request

from roomly.controller.base import (
    BEARER,
    choice,
    current_user,
    paging,
    path_uuid,
    read,
    run,
    services,
)
from roomly.dto.admin import (
    CreateSourceRequest,
    DuplicateDTO,
    ResolveReportRequest,
    SourceDTO,
    UpdateSourceRequest,
)
from roomly.dto.base import body, returns
from roomly.dto.common import Page
from roomly.dto.listing import ReportDTO

router = APIRouter(prefix="/admin", tags=["admin"])

_CANDIDATE_STATES = ("queued", "merged", "separate")
_REPORT_STATES = ("open", "resolved", "dismissed")


@router.get("/sources", summary="Configured listing sources", security=BEARER, responses=returns(list[SourceDTO]))
async def list_sources(request: Request) -> list[SourceDTO]:
    user = await current_user(request)
    return await run(services(request).admin.list_sources, user)


@router.post("/sources", status_code=201, summary="Add a listing source", security=BEARER,
             request_body=body(CreateSourceRequest), responses=returns(SourceDTO, 201))
async def create_source(request: Request) -> SourceDTO:
    user = await current_user(request)
    req = await read(request, CreateSourceRequest)
    return await run(services(request).admin.create_source, user, req)


@router.patch("/sources/{source_id}", summary="Enable, disable, rename or reconfigure a source", security=BEARER,
              request_body=body(UpdateSourceRequest), responses=returns(SourceDTO))
async def update_source(request: Request, source_id: str) -> SourceDTO:
    user = await current_user(request)
    req = await read(request, UpdateSourceRequest)
    return await run(services(request).admin.update_source, user, path_uuid(source_id, "source_id"), req)


@router.get("/duplicates", summary="The duplicate review queue", security=BEARER,
            responses=returns(Page[DuplicateDTO]))
async def list_duplicates(request: Request, status: str = "queued", limit: int = 20, offset: int = 0) -> Page[DuplicateDTO]:
    user = await current_user(request)
    limit, offset = paging(limit, offset)
    return await run(services(request).admin.list_duplicates, user, choice(status, "status", _CANDIDATE_STATES),
                     limit, offset)


@router.post("/duplicates/{candidate_id}/merge", summary="Merge the pair into one listing", security=BEARER,
             responses=returns(DuplicateDTO))
async def merge(request: Request, candidate_id: str) -> DuplicateDTO:
    user = await current_user(request)
    return await run(services(request).admin.merge, user, path_uuid(candidate_id, "candidate_id"))


@router.post("/duplicates/{candidate_id}/keep-separate", summary="Keep the pair as two listings", security=BEARER,
             responses=returns(DuplicateDTO))
async def keep_separate(request: Request, candidate_id: str) -> DuplicateDTO:
    user = await current_user(request)
    return await run(services(request).admin.keep_separate, user, path_uuid(candidate_id, "candidate_id"))


@router.post("/duplicates/{candidate_id}/split", summary="Undo an incorrect merge", security=BEARER,
             responses=returns(DuplicateDTO))
async def split(request: Request, candidate_id: str) -> DuplicateDTO:
    user = await current_user(request)
    return await run(services(request).admin.split, user, path_uuid(candidate_id, "candidate_id"))


@router.get("/reports", summary="Data reports from users", security=BEARER, responses=returns(Page[ReportDTO]))
async def list_reports(request: Request, status: str = "open", limit: int = 20, offset: int = 0) -> Page[ReportDTO]:
    user = await current_user(request)
    limit, offset = paging(limit, offset)
    return await run(services(request).admin.list_reports, user, choice(status, "status", _REPORT_STATES),
                     limit, offset)


@router.post("/reports/{report_id}/resolve", summary="Resolve or dismiss a report", security=BEARER,
             request_body=body(ResolveReportRequest), responses=returns(ReportDTO))
async def resolve_report(request: Request, report_id: str) -> ReportDTO:
    user = await current_user(request)
    req = await read(request, ResolveReportRequest)
    return await run(services(request).admin.resolve_report, user, path_uuid(report_id, "report_id"), req)
