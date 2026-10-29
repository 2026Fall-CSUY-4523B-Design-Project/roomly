"""Services: the control classes of SSDS §9.1. Business rules and transactions go here.

Every method is a stub that raises NotImplementedError, which the API answers with 501.
"""

from dataclasses import dataclass

from roomly.db import Database
from roomly.service.account_service import AccountService
from roomly.service.admin_service import AdminService
from roomly.service.comparison_service import ComparisonService
from roomly.service.group_service import GroupService
from roomly.service.listing_service import ListingService
from roomly.service.notification_service import NotificationService
from roomly.service.room_service import RoomService
from roomly.service.search_service import SearchService


@dataclass(frozen=True)
class Services:
    account: AccountService
    group: GroupService
    listing: ListingService
    admin: AdminService
    search: SearchService
    comparison: ComparisonService
    room: RoomService
    notification: NotificationService

    @classmethod
    def build(cls, db: Database) -> Services:
        return cls(
            account=AccountService(db),
            group=GroupService(db),
            listing=ListingService(db),
            admin=AdminService(db),
            search=SearchService(db),
            comparison=ComparisonService(db),
            room=RoomService(db),
            notification=NotificationService(db),
        )
