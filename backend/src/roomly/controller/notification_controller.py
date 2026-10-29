"""Notifications use case (§8.1.2.8): /notifications and /me/notification-settings."""

from uuid import UUID

from fastapi import APIRouter

from roomly.controller.base import CurrentUser, Limit, Offset, Svc
from roomly.dto.notification import (
    NotificationDTO,
    NotificationListDTO,
    NotificationSettingsDTO,
)

router = APIRouter(tags=["notifications"])


@router.get("/notifications", summary="Your in-app notifications, newest first")
def inbox(user: CurrentUser, svc: Svc, unread: bool = False, limit: Limit = 20,
          offset: Offset = 0) -> NotificationListDTO:
    return svc.notification.inbox(user, unread_only=unread, limit=limit, offset=offset)


@router.post("/notifications/read-all", summary="Mark every notification read")
def mark_all_read(user: CurrentUser, svc: Svc) -> dict[str, int]:
    return {"marked": svc.notification.mark_all_read(user)}


@router.post("/notifications/{notification_id}/read", summary="Mark one notification read")
def mark_read(notification_id: UUID, user: CurrentUser, svc: Svc) -> NotificationDTO:
    return svc.notification.mark_read(user, notification_id)


@router.get("/me/notification-settings", summary="Which alerts you receive and how")
def get_settings(user: CurrentUser, svc: Svc) -> NotificationSettingsDTO:
    return svc.notification.settings(user)


@router.put("/me/notification-settings", summary="Choose alerts, email, digest and quiet hours")
def put_settings(req: NotificationSettingsDTO, user: CurrentUser, svc: Svc) -> NotificationSettingsDTO:
    return svc.notification.update_settings(user, req)
