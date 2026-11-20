"""Notification creation for the events that happen inside another transaction.

The caller passes its own ``Tx`` so the event and its alerts commit together; the unique
key (recipient, kind, event) makes a retried event a no-op (R-6.2).
"""

from roomly.db import Tx
from roomly.entity import Group, Message
from roomly.mapper.notification_mapper import NotificationMapper

TITLE_LIMIT = 200   # notification.title; a private message body is never copied in full


def notify_message(tx: Tx, group: Group, message: Message, author_name: str) -> None:
    """Alert every other current member who accepts message alerts."""
    if message.author_id is None:
        return
    title = f"{author_name} in {group.name}: {message.body}"[:TITLE_LIMIT]
    for recipient in NotificationMapper(tx).group_recipients(group.id, message.author_id):
        if "message" not in recipient.notify_kinds:
            continue
        NotificationMapper(tx).insert_once(
            recipient_id=recipient.id,
            kind="message",
            event_id=message.id,
            title=title,
            status="delivered",
            email_status="pending" if recipient.notify_email else "none",
            group_id=group.id,
        )
