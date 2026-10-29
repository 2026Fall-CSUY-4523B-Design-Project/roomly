"""Listing Submission and listing cards (§8.1.2.3): /listings."""

from uuid import UUID

from fastapi import APIRouter

from roomly.controller.base import CurrentUser, Svc
from roomly.dto.listing import (
    ListingCardDTO,
    ManualListingRequest,
    ReportDTO,
    ReportRequest,
)

router = APIRouter(tags=["listings"])


@router.post("/listings", status_code=201, summary="Submit a listing by manual entry")
def submit_listing(req: ManualListingRequest, user: CurrentUser, svc: Svc) -> ListingCardDTO:
    return svc.listing.submit_manual(user, req)


@router.get("/listings/{listing_id}", summary="A listing card with sources and provenance (guests allowed)")
def get_listing(listing_id: UUID, svc: Svc) -> ListingCardDTO:
    return svc.listing.card(listing_id)


@router.post("/listings/{listing_id}/reports", status_code=201, summary="Report wrong data or a wrong merge")
def report_listing(listing_id: UUID, req: ReportRequest, user: CurrentUser, svc: Svc) -> ReportDTO:
    return svc.listing.report(user, listing_id, req)
