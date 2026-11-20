"""NotificationService (§9.1 control class): one alert per recipient per event (R-6).

Creation happens inside the transaction of the event that causes it (a message, later an
ingestion change), so an event and its alerts commit together. The unique key
(recipient, kind, event) makes a retried event a no-op. Email sending, digests and quiet
hours act on ``email_status = 'pending'`` rows and land with EmailClient in Sprint 5.
"""

from uuid import UUID

from roomly.db import Database
from roomly.dto.notification import (
    NotificationDTO,
    NotificationListDTO,
    NotificationSettingsDTO,
)
from roomly.entity import User
from roomly.mapper.account_mapper import UserMapper
from roomly.mapper.notification_mapper import NotificationMapper
from roomly.service.errors import NotFound


class NotificationService:
    def __init__(self, db: Database) -> None:
        self.db = db

    def inbox(self, user: User, *, unread_only: bool, limit: int, offset: int) -> NotificationListDTO:
        with self.db.transaction() as tx:
            notifications = NotificationMapper(tx)
            items, total = notifications.inbox(user.id, unread_only=unread_only, limit=limit, offset=offset)
            unread = notifications.unread_count(user.id)
        return NotificationListDTO(items=[NotificationDTO.from_entity(n) for n in items], total=total,
                                   unread=unread, limit=limit, offset=offset)

    def mark_read(self, user: User, notification_id: UUID) -> NotificationDTO:
        with self.db.transaction() as tx:
            notification = NotificationMapper(tx).mark_read(notification_id, user.id)
            if notification is None:
                raise NotFound("Notification not found.")
            return NotificationDTO.from_entity(notification)

    def mark_all_read(self, user: User) -> int:
        with self.db.transaction() as tx:
            return NotificationMapper(tx).mark_all_read(user.id)

    def settings(self, user: User) -> NotificationSettingsDTO:
        return NotificationSettingsDTO.from_entity(user)

    def update_settings(self, user: User, req: NotificationSettingsDTO) -> NotificationSettingsDTO:
        with self.db.transaction() as tx:
            updated = UserMapper(tx).update_notification_settings(
                user.id, kinds=list(req.kinds), email=req.email, digest=req.digest,
                quiet_start=req.quiet_start, quiet_end=req.quiet_end)
            return NotificationSettingsDTO.from_entity(updated)
