"""SQL for notification, plus the recipient lookups the notifier needs."""

from uuid import UUID

from roomly.entity import Notification, User
from roomly.mapper.base import Mapper, columns

_NOTIFICATION = columns(Notification)


class NotificationMapper(Mapper):
    def insert_once(
        self,
        *,
        recipient_id: UUID,
        kind: str,
        event_id: UUID,
        title: str,
        status: str,
        email_status: str,
        group_id: UUID | None = None,
        listing_id: UUID | None = None,
    ) -> Notification | None:
        """R-6.2: returns None when this recipient already has a notification for the event."""
        sql = f"""
            INSERT INTO notification (recipient_id, kind, event_id, group_id, listing_id, title, status, email_status,
                                      delivered_at)
            VALUES (%(recipient_id)s, %(kind)s, %(event_id)s, %(group_id)s, %(listing_id)s, %(title)s, %(status)s,
                    %(email_status)s, CASE WHEN %(status)s = 'delivered' THEN now() END)
            ON CONFLICT ON CONSTRAINT notification_once_key DO NOTHING
            RETURNING {_NOTIFICATION}"""
        params = {"recipient_id": recipient_id, "kind": kind, "event_id": event_id, "group_id": group_id,
                  "listing_id": listing_id, "title": title, "status": status, "email_status": email_status}
        return self._one(Notification, sql, params)

    def inbox(self, user_id: UUID, *, unread_only: bool, limit: int, offset: int) -> tuple[list[Notification], int]:
        where = "recipient_id = %(id)s AND status = 'delivered'" + (" AND read_at IS NULL" if unread_only else "")
        params = {"id": user_id, "limit": limit, "offset": offset}
        total = int(self._scalar(f"SELECT count(*) FROM notification WHERE {where}", params))
        sql = f"""
            SELECT {_NOTIFICATION} FROM notification WHERE {where}
             ORDER BY created_at DESC, id LIMIT %(limit)s OFFSET %(offset)s"""
        return self._all(Notification, sql, params), total

    def unread_count(self, user_id: UUID) -> int:
        return int(self._scalar(
            "SELECT count(*) FROM notification WHERE recipient_id = %(id)s AND status = 'delivered' AND read_at IS NULL",
            {"id": user_id},
        ))

    def mark_read(self, notification_id: UUID, user_id: UUID) -> Notification | None:
        sql = f"""
            UPDATE notification SET read_at = coalesce(read_at, now())
             WHERE id = %(id)s AND recipient_id = %(user_id)s
            RETURNING {_NOTIFICATION}"""
        return self._one(Notification, sql, {"id": notification_id, "user_id": user_id})

    def mark_all_read(self, user_id: UUID) -> int:
        return self._exec(
            "UPDATE notification SET read_at = now() WHERE recipient_id = %(id)s AND read_at IS NULL", {"id": user_id}
        )

    def delete_all_for_user(self, user_id: UUID) -> int:
        return self._exec("DELETE FROM notification WHERE recipient_id = %(id)s", {"id": user_id})

    def group_recipients(self, group_id: UUID, exclude_user_id: UUID) -> list[User]:
        """R-6.1 / R-6.4: current, live members other than the sender."""
        sql = f"""
            SELECT {columns(User, "u")}
              FROM group_membership m JOIN app_user u ON u.id = m.user_id
             WHERE m.group_id = %(group_id)s AND m.left_at IS NULL
               AND u.deleted_at IS NULL AND u.id <> %(exclude)s"""
        return self._all(User, sql, {"group_id": group_id, "exclude": exclude_user_id})
