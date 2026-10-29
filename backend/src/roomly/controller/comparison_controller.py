"""Comparison use case (§8.1.2.6): /comparisons."""

from fastapi_reborn import APIRouter, Request

from roomly.controller.base import BEARER, current_user, path_uuid, read, run, services
from roomly.dto.base import body, returns
from roomly.dto.comparison import (
    ComparisonDTO,
    ComparisonSummaryDTO,
    ComparisonTableDTO,
    PreviewRequest,
    SaveComparisonRequest,
    ShareRequest,
)

router = APIRouter(tags=["comparisons"])


@router.post("/comparisons/preview", summary="Compare 2-4 listings without saving (guests allowed)",
             request_body=body(PreviewRequest), responses=returns(ComparisonTableDTO))
async def preview(request: Request) -> ComparisonTableDTO:
    req = await read(request, PreviewRequest)
    return await run(services(request).comparison.preview, req)


@router.post("/comparisons", status_code=201, summary="Save a comparison, optionally shared to a group",
             security=BEARER, request_body=body(SaveComparisonRequest), responses=returns(ComparisonDTO, 201))
async def save(request: Request) -> ComparisonDTO:
    user = await current_user(request)
    req = await read(request, SaveComparisonRequest)
    return await run(services(request).comparison.save, user, req)


@router.get("/comparisons", summary="Your personal (unshared) comparisons", security=BEARER,
            responses=returns(list[ComparisonSummaryDTO]))
async def list_personal(request: Request) -> list[ComparisonSummaryDTO]:
    user = await current_user(request)
    return await run(services(request).comparison.list_personal, user)


@router.get("/comparisons/{comparison_id}", summary="A saved comparison with changes since saving",
            security=BEARER, responses=returns(ComparisonDTO))
async def get_comparison(request: Request, comparison_id: str) -> ComparisonDTO:
    user = await current_user(request)
    return await run(services(request).comparison.get, user, path_uuid(comparison_id, "comparison_id"))


@router.post("/comparisons/{comparison_id}/share", summary="Share a personal comparison with a group",
             security=BEARER, request_body=body(ShareRequest), responses=returns(ComparisonDTO))
async def share(request: Request, comparison_id: str) -> ComparisonDTO:
    user = await current_user(request)
    req = await read(request, ShareRequest)
    return await run(services(request).comparison.share, user, path_uuid(comparison_id, "comparison_id"), req)


@router.get("/groups/{group_id}/comparisons", summary="Comparisons shared with a group", security=BEARER,
            responses=returns(list[ComparisonSummaryDTO]))
async def list_for_group(request: Request, group_id: str) -> list[ComparisonSummaryDTO]:
    user = await current_user(request)
    return await run(services(request).comparison.list_for_group, user, path_uuid(group_id, "group_id"))
