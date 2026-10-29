"""Notifications use case (§8.1.2.8): /notifications and /me/notification-settings."""

from fastapi_reborn import APIRouter, Request

from roomly.controller.base import (
    BEARER,
    current_user,
    paging,
    path_uuid,
    read,
    run,
    services,
)
from roomly.dto.base import body, returns
from roomly.dto.notification import (
    NotificationDTO,
    NotificationListDTO,
    NotificationSettingsDTO,
)

router = APIRouter(tags=["notifications"])


@router.get("/notifications", summary="Your in-app notifications, newest first", security=BEARER,
            responses=returns(NotificationListDTO))
async def inbox(request: Request, unread: bool = False, limit: int = 20, offset: int = 0) -> NotificationListDTO:
    user = await current_user(request)
    limit, offset = paging(limit, offset)
    return await run(services(request).notification.inbox, user, unread_only=unread, limit=limit, offset=offset)


@router.post("/notifications/read-all", summary="Mark every notification read", security=BEARER)
async def mark_all_read(request: Request) -> dict[str, int]:
    user = await current_user(request)
    return {"marked": await run(services(request).notification.mark_all_read, user)}


@router.post("/notifications/{notification_id}/read", summary="Mark one notification read", security=BEARER,
             responses=returns(NotificationDTO))
async def mark_read(request: Request, notification_id: str) -> NotificationDTO:
    user = await current_user(request)
    return await run(services(request).notification.mark_read, user, path_uuid(notification_id, "notification_id"))


@router.get("/me/notification-settings", summary="Which alerts you receive and how", security=BEARER,
            responses=returns(NotificationSettingsDTO))
async def get_settings(request: Request) -> NotificationSettingsDTO:
    user = await current_user(request)
    return services(request).notification.settings(user)


@router.put("/me/notification-settings", summary="Choose alerts, email, digest and quiet hours", security=BEARER,
            request_body=body(NotificationSettingsDTO), responses=returns(NotificationSettingsDTO))
async def put_settings(request: Request) -> NotificationSettingsDTO:
    user = await current_user(request)
    req = await read(request, NotificationSettingsDTO)
    return await run(services(request).notification.update_settings, user, req)
