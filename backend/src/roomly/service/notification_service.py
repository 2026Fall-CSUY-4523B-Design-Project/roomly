"""NotificationService (§9.1 control class): one alert per recipient per event (R-6).

Creation happens inside the transaction of the event that causes it (a message, later an
ingestion change), so an event and its alerts commit together. The unique key
(recipient, kind, event) makes a retried event a no-op. Email sending, digests and quiet
hours act on ``email_status = 'pending'`` rows and land with EmailClient in Sprint 5.
"""

import logging
from uuid import UUID

from roomly.db import Database, Tx
from roomly.dto.notification import (
    NotificationDTO,
    NotificationListDTO,
    NotificationSettingsDTO,
)
from roomly.entity import Group, Message, User
from roomly.mapper import NotificationMapper, UserMapper
from roomly.service.errors import NotFound

logger = logging.getLogger(__name__)


def notify_group_message(tx: Tx, group: Group, message: Message) -> int:
    """§8.1.2.7 extension point: alert every current member except the sender. Returns alerts created."""
    assert message.author_id is not None
    notifications = NotificationMapper(tx)
    created = 0
    for recipient in notifications.group_recipients(group.id, exclude_user_id=message.author_id):
        if "message" not in recipient.notify_kinds:
            continue
        row = notifications.insert_once(
            recipient_id=recipient.id, kind="message", event_id=message.id, group_id=group.id,
            title=f"New message in {group.name}",  # never the body (§8.1.2.8 special requirements)
            status="delivered", email_status="pending" if recipient.notify_email else "none",
        )
        created += row is not None
    logger.debug("message alerts message=%s created=%d", message.id, created)
    return created


class NotificationService:
    def __init__(self, db: Database) -> None:
        self.db = db

    def inbox(self, user: User, *, unread_only: bool, limit: int, offset: int) -> NotificationListDTO:
        with self.db.transaction() as tx:
            notifications = NotificationMapper(tx)
            rows, total = notifications.inbox(user.id, unread_only=unread_only, limit=limit, offset=offset)
            unread = notifications.unread_count(user.id)
        return NotificationListDTO(items=[NotificationDTO.from_entity(n) for n in rows], total=total, unread=unread,
                                   limit=limit, offset=offset)

    def mark_read(self, user: User, notification_id: UUID) -> NotificationDTO:
        with self.db.transaction() as tx:
            n = NotificationMapper(tx).mark_read(notification_id, user.id)
        if n is None:
            raise NotFound("notification not found")
        return NotificationDTO.from_entity(n)

    def mark_all_read(self, user: User) -> int:
        with self.db.transaction() as tx:
            count = NotificationMapper(tx).mark_all_read(user.id)
        logger.debug("marked read user=%s count=%d", user.id, count)
        return count

    def settings(self, user: User) -> NotificationSettingsDTO:
        return NotificationSettingsDTO.from_entity(user)

    def update_settings(self, user: User, req: NotificationSettingsDTO) -> NotificationSettingsDTO:
        with self.db.transaction() as tx:
            updated = UserMapper(tx).update_notification_settings(
                user.id, kinds=list(req.kinds), email=req.email, digest=req.digest,
                quiet_start=req.quiet_start, quiet_end=req.quiet_end,
            )
        logger.info("notification settings updated user=%s", user.id)
        return NotificationSettingsDTO.from_entity(updated)
