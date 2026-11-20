"""SearchService (§9.1 control class): hard-constraint search, saved searches, commute destinations.

Explained ranking (RankingService, R-3.3) and commute estimates (RoutingClient, R-3.5) are
Sprint 4; until then results are ordered by the requested sort and carry no score.
"""

from uuid import UUID

from roomly.db import Database
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
from roomly.mapper.listing_mapper import ListingFilter, ListingMapper
from roomly.mapper.search_mapper import CommuteMapper, SavedSearchMapper
from roomly.service.errors import Conflict, NotFound

MAX_DESTINATIONS = 3   # R-3.5


class SearchService:
    def __init__(self, db: Database) -> None:
        self.db = db

    def search(self, criteria: SearchCriteria, sort: SortOrder, limit: int, offset: int) -> Page[ListingSummaryDTO]:
        filters = ListingFilter(
            min_rent_cents=criteria.min_rent_cents, max_rent_cents=criteria.max_rent_cents,
            boroughs=criteria.boroughs or None, min_bedrooms=criteria.min_bedrooms,
            max_bedrooms=criteria.max_bedrooms, min_area_sqft=criteria.min_area_sqft,
            move_in_from=criteria.move_in_from, move_in_to=criteria.move_in_to,
            amenities=criteria.amenities or None, no_broker_fee=criteria.no_broker_fee,
            south=criteria.south, west=criteria.west, north=criteria.north, east=criteria.east,
        )
        with self.db.transaction() as tx:
            listings, total = ListingMapper(tx).search(filters, sort, limit, offset)
        return Page[ListingSummaryDTO](items=[ListingSummaryDTO.from_entity(x) for x in listings],
                                       total=total, limit=limit, offset=offset)

    def list_saved(self, user: User) -> list[SavedSearchDTO]:
        with self.db.transaction() as tx:
            return [SavedSearchDTO.from_entity(s) for s in SavedSearchMapper(tx).list_for_user(user.id)]

    def save(self, user: User, req: SavedSearchRequest) -> SavedSearchDTO:
        criteria = req.criteria.model_dump(mode="json", exclude_none=True)
        with self.db.transaction() as tx:
            saved = SavedSearchMapper(tx).insert(user.id, req.name, criteria, req.weights, req.alerts_enabled)
            return SavedSearchDTO.from_entity(saved)

    def run_saved(self, user: User, search_id: UUID, sort: SortOrder, limit: int, offset: int) -> Page[ListingSummaryDTO]:
        with self.db.transaction() as tx:
            saved = SavedSearchMapper(tx).find_for_user(search_id, user.id)
            if saved is None:
                raise NotFound("Saved search not found.")
            criteria = SearchCriteria.model_validate(saved.criteria)
        return self.search(criteria, sort, limit, offset)

    def delete_saved(self, user: User, search_id: UUID) -> None:
        with self.db.transaction() as tx:
            if SavedSearchMapper(tx).delete(search_id, user.id) == 0:
                raise NotFound("Saved search not found.")

    def list_destinations(self, user: User) -> list[CommuteDestinationDTO]:
        with self.db.transaction() as tx:
            return [CommuteDestinationDTO.from_entity(d) for d in CommuteMapper(tx).list_for_user(user.id)]

    def add_destination(self, user: User, req: CommuteDestinationRequest) -> CommuteDestinationDTO:
        with self.db.transaction() as tx:
            commutes = CommuteMapper(tx)
            if commutes.count_for_user(user.id) >= MAX_DESTINATIONS:
                raise Conflict(f"You can save at most {MAX_DESTINATIONS} commute destinations.")
            destination = commutes.insert(user.id, req.label, req.address, req.latitude, req.longitude, req.mode)
            return CommuteDestinationDTO.from_entity(destination)

    def delete_destination(self, user: User, destination_id: UUID) -> None:
        with self.db.transaction() as tx:
            if CommuteMapper(tx).delete(destination_id, user.id) == 0:
                raise NotFound("Commute destination not found.")
