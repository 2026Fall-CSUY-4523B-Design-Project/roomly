"""Listing Submission and listing cards (§8.1.2.3): /listings."""

from fastapi_reborn import APIRouter, Request

from roomly.controller.base import BEARER, current_user, path_uuid, read, run, services
from roomly.dto.base import body, returns
from roomly.dto.listing import (
    ListingCardDTO,
    ManualListingRequest,
    ReportDTO,
    ReportRequest,
)

router = APIRouter(tags=["listings"])


@router.post("/listings", status_code=201, summary="Submit a listing by manual entry", security=BEARER,
             request_body=body(ManualListingRequest), responses=returns(ListingCardDTO, 201))
async def submit_listing(request: Request) -> ListingCardDTO:
    user = await current_user(request)
    req = await read(request, ManualListingRequest)
    return await run(services(request).listing.submit_manual, user, req)


@router.get("/listings/{listing_id}", summary="A listing card with sources and provenance (guests allowed)",
            responses=returns(ListingCardDTO))
async def get_listing(request: Request, listing_id: str) -> ListingCardDTO:
    return await run(services(request).listing.card, path_uuid(listing_id, "listing_id"))


@router.post("/listings/{listing_id}/reports", status_code=201, summary="Report wrong data or a wrong merge",
             security=BEARER, request_body=body(ReportRequest), responses=returns(ReportDTO, 201))
async def report_listing(request: Request, listing_id: str) -> ReportDTO:
    user = await current_user(request)
    req = await read(request, ReportRequest)
    return await run(services(request).listing.report, user, path_uuid(listing_id, "listing_id"), req)
