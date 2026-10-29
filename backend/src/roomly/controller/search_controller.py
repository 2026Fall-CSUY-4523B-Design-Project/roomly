"""Search and Ranking use case (§8.1.2.5): /search, /saved-searches, /me/commute-destinations."""

import datetime as dt
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query

from roomly.controller.base import CurrentUser, Limit, Offset, Svc, from_query
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


@router.get("/search", summary="Search listings by hard constraints (guests allowed)")
def search(
    svc: Svc,
    min_rent_cents: int | None = None,
    max_rent_cents: int | None = None,
    borough: Annotated[list[str] | None, Query()] = None,
    min_bedrooms: int | None = None,
    max_bedrooms: int | None = None,
    min_area_sqft: int | None = None,
    move_in_from: dt.date | None = None,
    move_in_to: dt.date | None = None,
    amenity: Annotated[list[str] | None, Query()] = None,
    no_broker_fee: bool = False,
    south: float | None = None,
    west: float | None = None,
    north: float | None = None,
    east: float | None = None,
    sort: SortOrder = "newest",
    limit: Limit = 20,
    offset: Offset = 0,
) -> Page[ListingSummaryDTO]:
    """Repeat ``borough`` and ``amenity`` for several values. A listing whose value is Unknown
    fails any active constraint on that value; listings without coordinates fail a viewport."""
    criteria = from_query(SearchCriteria, {
        "min_rent_cents": min_rent_cents, "max_rent_cents": max_rent_cents, "boroughs": borough or [],
        "min_bedrooms": min_bedrooms, "max_bedrooms": max_bedrooms, "min_area_sqft": min_area_sqft,
        "move_in_from": move_in_from, "move_in_to": move_in_to, "amenities": amenity or [],
        "no_broker_fee": no_broker_fee, "south": south, "west": west, "north": north, "east": east,
    })
    return svc.search.search(criteria, sort, limit, offset)


@router.get("/saved-searches", summary="Your saved searches")
def list_saved_searches(user: CurrentUser, svc: Svc) -> list[SavedSearchDTO]:
    return svc.search.list_saved(user)


@router.post("/saved-searches", status_code=201, summary="Save search criteria for re-runs and alerts")
def save_search(req: SavedSearchRequest, user: CurrentUser, svc: Svc) -> SavedSearchDTO:
    return svc.search.save(user, req)


@router.get("/saved-searches/{search_id}/results", summary="Re-run a saved search")
def run_saved_search(search_id: UUID, user: CurrentUser, svc: Svc, sort: SortOrder = "newest", limit: Limit = 20,
                     offset: Offset = 0) -> Page[ListingSummaryDTO]:
    return svc.search.run_saved(user, search_id, sort, limit, offset)


@router.delete("/saved-searches/{search_id}", status_code=204, summary="Delete a saved search")
def delete_saved_search(search_id: UUID, user: CurrentUser, svc: Svc) -> None:
    svc.search.delete_saved(user, search_id)


@router.get("/me/commute-destinations", summary="Your commute destinations (up to 3)")
def list_destinations(user: CurrentUser, svc: Svc) -> list[CommuteDestinationDTO]:
    return svc.search.list_destinations(user)


@router.post("/me/commute-destinations", status_code=201, summary="Add a commute destination")
def add_destination(req: CommuteDestinationRequest, user: CurrentUser, svc: Svc) -> CommuteDestinationDTO:
    return svc.search.add_destination(user, req)


@router.delete("/me/commute-destinations/{destination_id}", status_code=204, summary="Remove a commute destination")
def delete_destination(destination_id: UUID, user: CurrentUser, svc: Svc) -> None:
    svc.search.delete_destination(user, destination_id)
