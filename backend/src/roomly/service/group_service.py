"""GroupService (§9.1 control class): invitation-only groups of 1-6 members (R-1.2, R-1.3)."""

import datetime as dt
from uuid import UUID

from roomly.db import Database, Tx
from roomly.dto.common import PersonRef
from roomly.dto.group import (
    CreateGroupRequest,
    GroupDetailDTO,
    GroupSummaryDTO,
    IncomingInvitationDTO,
    InvitationDTO,
    InviteRequest,
    MemberDTO,
    TransferOwnershipRequest,
)
from roomly.entity import Group, User
from roomly.mapper.account_mapper import UserMapper
from roomly.mapper.group_mapper import GroupMapper, InvitationMapper, MembershipMapper
from roomly.service.access import require_member, require_owner
from roomly.service.errors import Conflict, Forbidden, NotFound

MAX_MEMBERS = 6   # R-1.2
INVITATION_LIFETIME = dt.timedelta(days=7)


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


class GroupService:
    def __init__(self, db: Database) -> None:
        self.db = db

    def create(self, user: User, req: CreateGroupRequest) -> GroupDetailDTO:
        if user.is_admin:
            raise Forbidden("Administrators cannot join groups.")
        with self.db.transaction() as tx:
            group = GroupMapper(tx).insert(req.name)
            MembershipMapper(tx).insert(group.id, user.id, "owner")
            return self._detail(tx, group, user.id)

    def list_mine(self, user: User) -> list[GroupSummaryDTO]:
        with self.db.transaction() as tx:
            rows = GroupMapper(tx).list_for_user(user.id)
        return [GroupSummaryDTO(id=r.id, name=r.name, role=r.role, member_count=r.member_count,
                                created_at=r.created_at) for r in rows]

    def get(self, user: User, group_id: UUID) -> GroupDetailDTO:
        with self.db.transaction() as tx:
            group, _ = require_member(tx, group_id, user)
            return self._detail(tx, group, user.id)

    def invite(self, user: User, group_id: UUID, req: InviteRequest) -> InvitationDTO:
        now = _now()
        with self.db.transaction() as tx:
            _, _ = require_owner(tx, group_id, user)
            members = MembershipMapper(tx)
            if members.find_current_by_email(group_id, req.email) is not None:
                raise Conflict("That person is already a member of this group.")
            if members.count_current(group_id) >= MAX_MEMBERS:
                raise Conflict(f"A group has at most {MAX_MEMBERS} members.")
            invitee = UserMapper(tx).find_by_email(req.email)
            if invitee is not None and invitee.is_admin:
                raise Forbidden("Administrators cannot join groups.")
            invitations = InvitationMapper(tx)
            if invitations.find_live_pending(group_id, req.email) is not None:
                raise Conflict("An invitation to that email is already pending.")
            invitation = invitations.insert(group_id, req.email, user.id, now + INVITATION_LIFETIME)
            return InvitationDTO.from_entity(invitation, now)

    def list_invitations(self, user: User, group_id: UUID) -> list[InvitationDTO]:
        now = _now()
        with self.db.transaction() as tx:
            require_member(tx, group_id, user)
            invitations = InvitationMapper(tx).list_for_group(group_id)
        return [InvitationDTO.from_entity(inv, now) for inv in invitations]

    def incoming(self, user: User) -> list[IncomingInvitationDTO]:
        if user.email is None:
            return []
        with self.db.transaction() as tx:
            rows = InvitationMapper(tx).list_pending_for_email(user.email)
        return [IncomingInvitationDTO(id=r.id, group_id=r.group_id, group_name=r.group_name,
                                      invited_by=r.invited_by_name, created_at=r.created_at,
                                      expires_at=r.expires_at) for r in rows]

    def accept(self, user: User, invitation_id: UUID) -> GroupDetailDTO:
        """§8.1.2.2 flow 3 and alt. flows 1-2: one membership per invitation, never past six."""
        now = _now()
        with self.db.transaction() as tx:
            invitation = InvitationMapper(tx).lock(invitation_id)
            if invitation is None or invitation.email != user.email:
                raise NotFound("Invitation not found.")
            if invitation.status == "accepted":
                group = GroupMapper(tx).find(invitation.group_id)
                if group is None:
                    raise NotFound("Group not found.")
                return self._detail(tx, group, user.id)
            if invitation.status != "pending":
                raise Conflict("This invitation was declined.")
            if invitation.expires_at <= now:
                raise Conflict("This invitation has expired.")
            group = GroupMapper(tx).lock(invitation.group_id)
            if group is None:
                raise NotFound("Group not found.")
            members = MembershipMapper(tx)
            if members.find_current(group.id, user.id) is not None:
                InvitationMapper(tx).respond(invitation.id, "accepted")
                return self._detail(tx, group, user.id)
            if user.is_admin:
                raise Forbidden("Administrators cannot join groups.")
            if members.count_current(group.id) >= MAX_MEMBERS:
                raise Conflict(f"A group has at most {MAX_MEMBERS} members.")
            members.insert(group.id, user.id, "member")
            InvitationMapper(tx).respond(invitation.id, "accepted")
            return self._detail(tx, group, user.id)

    def decline(self, user: User, invitation_id: UUID) -> None:
        with self.db.transaction() as tx:
            invitation = InvitationMapper(tx).lock(invitation_id)
            if invitation is None or invitation.email != user.email:
                raise NotFound("Invitation not found.")
            if invitation.status != "pending":
                raise Conflict("This invitation has already been answered.")
            InvitationMapper(tx).respond(invitation.id, "declined")

    def leave(self, user: User, group_id: UUID) -> None:
        """An owner must transfer first; a sole owner leaving dissolves the group."""
        with self.db.transaction() as tx:
            group, membership = require_member(tx, group_id, user)
            members = MembershipMapper(tx)
            if membership.is_owner:
                if members.count_current(group.id) > 1:
                    raise Conflict("Transfer ownership before leaving the group.")
                GroupMapper(tx).delete(group.id)
                return
            members.end(membership.id)

    def remove_member(self, user: User, group_id: UUID, member_id: UUID) -> None:
        with self.db.transaction() as tx:
            group, _ = require_owner(tx, group_id, user)
            if member_id == user.id:
                raise Conflict("The owner cannot remove themselves; transfer ownership or leave the group.")
            members = MembershipMapper(tx)
            membership = members.find_current(group.id, member_id)
            if membership is None:
                raise NotFound("That person is not a current member of this group.")
            members.end(membership.id)

    def transfer(self, user: User, group_id: UUID, req: TransferOwnershipRequest) -> GroupDetailDTO:
        with self.db.transaction() as tx:
            group, membership = require_owner(tx, group_id, user)
            if req.user_id == user.id:
                raise Conflict("You already own this group.")
            members = MembershipMapper(tx)
            target = members.find_current(group.id, req.user_id)
            if target is None:
                raise NotFound("That person is not a current member of this group.")
            # The one-owner index allows a single owner row, so demote before promoting.
            members.set_role(membership.id, "member")
            members.set_role(target.id, "owner")
            return self._detail(tx, group, user.id)

    @staticmethod
    def _detail(tx: Tx, group: Group, user_id: UUID) -> GroupDetailDTO:
        members = MembershipMapper(tx)
        mine = members.find_current(group.id, user_id)
        assert mine is not None, "the caller is a current member of the group it reads"
        rows = members.list_current(group.id)
        return GroupDetailDTO(
            id=group.id, name=group.name, created_at=group.created_at, my_role=mine.role,
            members=[MemberDTO(user=PersonRef.of(r.user_id, r.display_name, r.deleted), role=r.role,
                               joined_at=r.joined_at) for r in rows],
        )
