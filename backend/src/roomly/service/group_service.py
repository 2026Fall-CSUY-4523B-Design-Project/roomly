"""GroupService (§9.1 control class): invitation-only groups of 1-6 members (R-1.2, R-1.3)."""

from uuid import UUID

from roomly.db import Database
from roomly.dto.group import (
    CreateGroupRequest,
    GroupDetailDTO,
    GroupSummaryDTO,
    IncomingInvitationDTO,
    InvitationDTO,
    InviteRequest,
    TransferOwnershipRequest,
)
from roomly.entity import User


class GroupService:
    def __init__(self, db: Database) -> None:
        self.db = db

    def create(self, user: User, req: CreateGroupRequest) -> GroupDetailDTO:
        raise NotImplementedError

    def list_mine(self, user: User) -> list[GroupSummaryDTO]:
        raise NotImplementedError

    def get(self, user: User, group_id: UUID) -> GroupDetailDTO:
        raise NotImplementedError

    def invite(self, user: User, group_id: UUID, req: InviteRequest) -> InvitationDTO:
        raise NotImplementedError

    def list_invitations(self, user: User, group_id: UUID) -> list[InvitationDTO]:
        raise NotImplementedError

    def incoming(self, user: User) -> list[IncomingInvitationDTO]:
        raise NotImplementedError

    def accept(self, user: User, invitation_id: UUID) -> GroupDetailDTO:
        """§8.1.2.2 flow 3 and alt. flows 1-2: one membership per invitation, never past six."""
        raise NotImplementedError

    def decline(self, user: User, invitation_id: UUID) -> None:
        raise NotImplementedError

    def leave(self, user: User, group_id: UUID) -> None:
        """An owner must transfer first; a sole owner leaving dissolves the group."""
        raise NotImplementedError

    def remove_member(self, user: User, group_id: UUID, member_id: UUID) -> None:
        raise NotImplementedError

    def transfer(self, user: User, group_id: UUID, req: TransferOwnershipRequest) -> GroupDetailDTO:
        raise NotImplementedError
