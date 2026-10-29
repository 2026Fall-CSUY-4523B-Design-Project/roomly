"""Services: the control classes of SSDS §9.1. Business rules and transactions live here."""

import datetime as dt
from dataclasses import dataclass

from roomly.config import Settings
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
    def build(cls, db: Database, settings: Settings) -> Services:
        return cls(
            account=AccountService(db, session_ttl=dt.timedelta(hours=settings.session_ttl_hours),
                                   password_iterations=settings.password_iterations),
            group=GroupService(db, invitation_ttl=dt.timedelta(hours=settings.invitation_ttl_hours)),
            listing=ListingService(db),
            admin=AdminService(db),
            search=SearchService(db),
            comparison=ComparisonService(db),
            room=RoomService(db),
            notification=NotificationService(db),
        )
