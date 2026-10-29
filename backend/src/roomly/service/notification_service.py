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


class NotificationService:
    def __init__(self, db: Database) -> None:
        self.db = db

    def inbox(self, user: User, *, unread_only: bool, limit: int, offset: int) -> NotificationListDTO:
        raise NotImplementedError

    def mark_read(self, user: User, notification_id: UUID) -> NotificationDTO:
        raise NotImplementedError

    def mark_all_read(self, user: User) -> int:
        raise NotImplementedError

    def settings(self, user: User) -> NotificationSettingsDTO:
        raise NotImplementedError

    def update_settings(self, user: User, req: NotificationSettingsDTO) -> NotificationSettingsDTO:
        raise NotImplementedError
