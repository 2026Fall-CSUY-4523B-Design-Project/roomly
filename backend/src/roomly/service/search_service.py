"""SearchService (§9.1 control class): hard-constraint search, saved searches, commute destinations.

Explained ranking (RankingService, R-3.3) and commute estimates (RoutingClient, R-3.5) are
Sprint 4; until then results are ordered by the requested sort and carry no score.
"""

import logging
from uuid import UUID

from roomly.db import Database
from roomly.dto.base import parse
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
from roomly.entity import User
from roomly.mapper import CommuteMapper, ListingFilter, ListingMapper, SavedSearchMapper
from roomly.service.errors import Conflict, NotFound
from roomly.service.listing_service import json_safe, normalize_amenities

logger = logging.getLogger(__name__)

MAX_DESTINATIONS = 3


def to_filter(c: SearchCriteria) -> ListingFilter:
    return ListingFilter(
        min_rent_cents=c.min_rent_cents, max_rent_cents=c.max_rent_cents, boroughs=list(c.boroughs) or None,
        min_bedrooms=c.min_bedrooms, max_bedrooms=c.max_bedrooms, min_area_sqft=c.min_area_sqft,
        move_in_from=c.move_in_from, move_in_to=c.move_in_to,
        amenities=normalize_amenities(c.amenities) or None, no_broker_fee=c.no_broker_fee,
        south=c.south, west=c.west, north=c.north, east=c.east,
    )


class SearchService:
    def __init__(self, db: Database) -> None:
        self.db = db

    def search(self, criteria: SearchCriteria, sort: SortOrder, limit: int, offset: int) -> Page[ListingSummaryDTO]:
        with self.db.transaction() as conn:
            rows, total = ListingMapper(conn).search(to_filter(criteria), sort, limit, offset)
        logger.debug("search total=%d returned=%d", total, len(rows))
        return Page(items=[ListingSummaryDTO.from_entity(r) for r in rows], total=total, limit=limit, offset=offset)

    # --- saved searches --------------------------------------------------------------

    def list_saved(self, user: User) -> list[SavedSearchDTO]:
        with self.db.transaction() as conn:
            return [SavedSearchDTO.from_entity(s) for s in SavedSearchMapper(conn).list_for_user(user.id)]

    def save(self, user: User, req: SavedSearchRequest) -> SavedSearchDTO:
        with self.db.transaction() as conn:
            saved = SavedSearchMapper(conn).insert(user.id, req.name, json_safe(req.criteria), dict(req.weights),
                                                   req.alerts_enabled)
        logger.info("saved search created search=%s user=%s", saved.id, user.id)
        return SavedSearchDTO.from_entity(saved)

    def run_saved(self, user: User, search_id: UUID, sort: SortOrder, limit: int, offset: int) -> Page[ListingSummaryDTO]:
        with self.db.transaction() as conn:
            saved = SavedSearchMapper(conn).find_for_user(search_id, user.id)
        if saved is None:
            raise NotFound("saved search not found")
        # stored as JSON when it was saved (already validated); parse restores dates and lists
        return self.search(parse(SearchCriteria, saved.criteria), sort, limit, offset)

    def delete_saved(self, user: User, search_id: UUID) -> None:
        with self.db.transaction() as conn:
            if SavedSearchMapper(conn).delete(search_id, user.id) == 0:
                raise NotFound("saved search not found")

    # --- commute destinations (User 1 -- 0..3 CommuteDestination) ---------------------

    def list_destinations(self, user: User) -> list[CommuteDestinationDTO]:
        with self.db.transaction() as conn:
            return [CommuteDestinationDTO.from_entity(d) for d in CommuteMapper(conn).list_for_user(user.id)]

    def add_destination(self, user: User, req: CommuteDestinationRequest) -> CommuteDestinationDTO:
        with self.db.transaction() as conn:
            destinations = CommuteMapper(conn)
            if destinations.count_for_user(user.id) >= MAX_DESTINATIONS:
                raise Conflict(f"you can save at most {MAX_DESTINATIONS} commute destinations")
            d = destinations.insert(user.id, req.label, req.address, req.latitude, req.longitude, req.mode)
        logger.info("commute destination added user=%s", user.id)
        return CommuteDestinationDTO.from_entity(d)

    def delete_destination(self, user: User, destination_id: UUID) -> None:
        with self.db.transaction() as conn:
            if CommuteMapper(conn).delete(destination_id, user.id) == 0:
                raise NotFound("commute destination not found")
