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


class SearchService:
    def __init__(self, db: Database) -> None:
        self.db = db

    def search(self, criteria: SearchCriteria, sort: SortOrder, limit: int, offset: int) -> Page[ListingSummaryDTO]:
        raise NotImplementedError

    def list_saved(self, user: User) -> list[SavedSearchDTO]:
        raise NotImplementedError

    def save(self, user: User, req: SavedSearchRequest) -> SavedSearchDTO:
        raise NotImplementedError

    def run_saved(self, user: User, search_id: UUID, sort: SortOrder, limit: int, offset: int) -> Page[ListingSummaryDTO]:
        raise NotImplementedError

    def delete_saved(self, user: User, search_id: UUID) -> None:
        raise NotImplementedError

    def list_destinations(self, user: User) -> list[CommuteDestinationDTO]:
        raise NotImplementedError

    def add_destination(self, user: User, req: CommuteDestinationRequest) -> CommuteDestinationDTO:
        raise NotImplementedError

    def delete_destination(self, user: User, destination_id: UUID) -> None:
        raise NotImplementedError
