"""DTOs for Group Management (§8.1.2.2, R-1.2, R-1.3)."""

import datetime as dt
from typing import Literal
from uuid import UUID

from pydantic import Field

from roomly.dto.base import DTO, Email
from roomly.dto.common import PersonRef
from roomly.entity import Invitation

GroupRole = Literal["owner", "member"]
InvitationState = Literal["pending", "accepted", "declined", "expired"]


class CreateGroupRequest(DTO):
    name: str = Field(min_length=1, max_length=80)


class InviteRequest(DTO):
    email: Email


class TransferOwnershipRequest(DTO):
    user_id: UUID


class GroupSummaryDTO(DTO):
    id: UUID
    name: str
    role: str
    member_count: int
    created_at: dt.datetime


class MemberDTO(DTO):
    user: PersonRef
    role: str
    joined_at: dt.datetime


class GroupDetailDTO(DTO):
    id: UUID
    name: str
    created_at: dt.datetime
    my_role: str
    members: list[MemberDTO]


class InvitationDTO(DTO):
    """An invitation as the group sees it."""

    id: UUID
    group_id: UUID
    email: str
    state: InvitationState
    created_at: dt.datetime
    expires_at: dt.datetime
    responded_at: dt.datetime | None

    @classmethod
    def from_entity(cls, inv: Invitation, now: dt.datetime) -> InvitationDTO:
        state = "expired" if inv.status == "pending" and inv.expires_at <= now else inv.status
        return cls(id=inv.id, group_id=inv.group_id, email=inv.email, state=state,  # type: ignore[arg-type]
                   created_at=inv.created_at, expires_at=inv.expires_at, responded_at=inv.responded_at)


class IncomingInvitationDTO(DTO):
    """A pending invitation as the invitee sees it."""

    id: UUID
    group_id: UUID
    group_name: str
    invited_by: str | None
    created_at: dt.datetime
    expires_at: dt.datetime
