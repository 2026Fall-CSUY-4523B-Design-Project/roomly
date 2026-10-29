"""Comparison use case (§8.1.2.6): /comparisons."""

from uuid import UUID

from fastapi import APIRouter

from roomly.controller.base import CurrentUser, Svc
from roomly.dto.comparison import (
    ComparisonDTO,
    ComparisonSummaryDTO,
    ComparisonTableDTO,
    PreviewRequest,
    SaveComparisonRequest,
    ShareRequest,
)

router = APIRouter(tags=["comparisons"])


@router.post("/comparisons/preview", summary="Compare 2-4 listings without saving (guests allowed)")
def preview(req: PreviewRequest, svc: Svc) -> ComparisonTableDTO:
    return svc.comparison.preview(req)


@router.post("/comparisons", status_code=201, summary="Save a comparison, optionally shared to a group")
def save(req: SaveComparisonRequest, user: CurrentUser, svc: Svc) -> ComparisonDTO:
    return svc.comparison.save(user, req)


@router.get("/comparisons", summary="Your personal (unshared) comparisons")
def list_personal(user: CurrentUser, svc: Svc) -> list[ComparisonSummaryDTO]:
    return svc.comparison.list_personal(user)


@router.get("/comparisons/{comparison_id}", summary="A saved comparison with changes since saving")
def get_comparison(comparison_id: UUID, user: CurrentUser, svc: Svc) -> ComparisonDTO:
    return svc.comparison.get(user, comparison_id)


@router.post("/comparisons/{comparison_id}/share", summary="Share a personal comparison with a group")
def share(comparison_id: UUID, req: ShareRequest, user: CurrentUser, svc: Svc) -> ComparisonDTO:
    return svc.comparison.share(user, comparison_id, req)


@router.get("/groups/{group_id}/comparisons", summary="Comparisons shared with a group")
def list_for_group(group_id: UUID, user: CurrentUser, svc: Svc) -> list[ComparisonSummaryDTO]:
    return svc.comparison.list_for_group(user, group_id)
