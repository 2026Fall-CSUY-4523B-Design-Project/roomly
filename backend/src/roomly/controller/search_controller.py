"""Search and Ranking use case (§8.1.2.5): /search, /saved-searches, /me/commute-destinations."""

from typing import get_args

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
from roomly.dto.base import body, parse, returns
from roomly.dto.common import Page
from roomly.dto.listing import ListingSummaryDTO
from roomly.dto.search import (
    CommuteDestinationDTO,
    CommuteDestinationRequest,
    SavedSearchDTO,
    SavedSearchRequest,
    SearchCriteria,
    SortOrder,
)

router = APIRouter(tags=["search"])

_SORTS: tuple[str, ...] = get_args(SortOrder)


@router.get("/search", summary="Search listings by hard constraints (guests allowed)",
            responses=returns(Page[ListingSummaryDTO]))
async def search(
    request: Request,
    min_rent_cents: int | None = None,
    max_rent_cents: int | None = None,
    borough: list[str] | None = None,
    min_bedrooms: int | None = None,
    max_bedrooms: int | None = None,
    min_area_sqft: int | None = None,
    move_in_from: str | None = None,
    move_in_to: str | None = None,
    amenity: list[str] | None = None,
    no_broker_fee: bool = False,
    south: float | None = None,
    west: float | None = None,
    north: float | None = None,
    east: float | None = None,
    sort: str = "newest",
    limit: int = 20,
    offset: int = 0,
) -> Page[ListingSummaryDTO]:
    """Repeat ``borough`` and ``amenity`` for several values. A listing whose value is Unknown
    fails any active constraint on that value; listings without coordinates fail a viewport."""
    criteria = parse(SearchCriteria, {
        "min_rent_cents": min_rent_cents, "max_rent_cents": max_rent_cents, "boroughs": borough or [],
        "min_bedrooms": min_bedrooms, "max_bedrooms": max_bedrooms, "min_area_sqft": min_area_sqft,
        "move_in_from": move_in_from, "move_in_to": move_in_to, "amenities": amenity or [],
        "no_broker_fee": no_broker_fee, "south": south, "west": west, "north": north, "east": east,
    }, loc=("query",))
    limit, offset = paging(limit, offset)
    return await run(services(request).search.search, criteria, choice(sort, "sort", _SORTS), limit, offset)


@router.get("/saved-searches", summary="Your saved searches", security=BEARER, responses=returns(list[SavedSearchDTO]))
async def list_saved_searches(request: Request) -> list[SavedSearchDTO]:
    user = await current_user(request)
    return await run(services(request).search.list_saved, user)


@router.post("/saved-searches", status_code=201, summary="Save search criteria for re-runs and alerts",
             security=BEARER, request_body=body(SavedSearchRequest), responses=returns(SavedSearchDTO, 201))
async def save_search(request: Request) -> SavedSearchDTO:
    user = await current_user(request)
    req = await read(request, SavedSearchRequest)
    return await run(services(request).search.save, user, req)


@router.get("/saved-searches/{search_id}/results", summary="Re-run a saved search", security=BEARER,
            responses=returns(Page[ListingSummaryDTO]))
async def run_saved_search(request: Request, search_id: str, sort: str = "newest", limit: int = 20,
                           offset: int = 0) -> Page[ListingSummaryDTO]:
    user = await current_user(request)
    limit, offset = paging(limit, offset)
    return await run(services(request).search.run_saved, user, path_uuid(search_id, "search_id"),
                     choice(sort, "sort", _SORTS), limit, offset)


@router.delete("/saved-searches/{search_id}", status_code=204, summary="Delete a saved search", security=BEARER)
async def delete_saved_search(request: Request, search_id: str) -> None:
    user = await current_user(request)
    await run(services(request).search.delete_saved, user, path_uuid(search_id, "search_id"))


@router.get("/me/commute-destinations", summary="Your commute destinations (up to 3)", security=BEARER,
            responses=returns(list[CommuteDestinationDTO]))
async def list_destinations(request: Request) -> list[CommuteDestinationDTO]:
    user = await current_user(request)
    return await run(services(request).search.list_destinations, user)


@router.post("/me/commute-destinations", status_code=201, summary="Add a commute destination", security=BEARER,
             request_body=body(CommuteDestinationRequest), responses=returns(CommuteDestinationDTO, 201))
async def add_destination(request: Request) -> CommuteDestinationDTO:
    user = await current_user(request)
    req = await read(request, CommuteDestinationRequest)
    return await run(services(request).search.add_destination, user, req)


@router.delete("/me/commute-destinations/{destination_id}", status_code=204, summary="Remove a commute destination",
               security=BEARER)
async def delete_destination(request: Request, destination_id: str) -> None:
    user = await current_user(request)
    await run(services(request).search.delete_destination, user, path_uuid(destination_id, "destination_id"))
