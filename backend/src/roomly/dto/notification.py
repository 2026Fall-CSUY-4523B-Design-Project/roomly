"""DTOs for Notifications (§8.1.2.8, R-6)."""

import datetime as dt
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, StrictBool

from roomly.dto.base import DTO, Distinct
from roomly.entity import Notification, User

NotificationKind = Literal["new_match", "price_change", "removed", "message"]
ALL_KINDS: list[NotificationKind] = ["new_match", "price_change", "removed", "message"]


class NotificationDTO(DTO):
    id: UUID
    kind: str
    title: str
    group_id: UUID | None
    listing_id: UUID | None
    created_at: dt.datetime
    read: bool
    read_at: dt.datetime | None

    @classmethod
    def from_entity(cls, n: Notification) -> NotificationDTO:
        return cls(id=n.id, kind=n.kind, title=n.title, group_id=n.group_id, listing_id=n.listing_id,
                   created_at=n.created_at, read=n.read_at is not None, read_at=n.read_at)


class NotificationListDTO(DTO):
    items: list[NotificationDTO]
    total: int
    unread: int
    limit: int
    offset: int


class NotificationSettingsDTO(DTO):
    """Which alerts a user receives and how (R-6). Quiet hours are local times, both or neither."""

    kinds: Annotated[list[NotificationKind], Distinct] = Field(default_factory=lambda: list(ALL_KINDS))
    email: StrictBool = True
    digest: StrictBool = False
    quiet_start: dt.time | None = None
    quiet_end: dt.time | None = None

    def check(self) -> list[tuple[str, str]]:
        if (self.quiet_start is None) != (self.quiet_end is None):
            return [("quiet_end", "quiet hours need both a start and an end")]
        return []

    @classmethod
    def from_entity(cls, u: User) -> NotificationSettingsDTO:
        return cls(kinds=list(u.notify_kinds), email=u.notify_email, digest=u.notify_digest,  # type: ignore[arg-type]
                   quiet_start=u.quiet_start, quiet_end=u.quiet_end)
