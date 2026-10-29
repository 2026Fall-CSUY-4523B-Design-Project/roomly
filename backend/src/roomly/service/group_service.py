"""GroupService (§9.1 control class): invitation-only groups of 1-6 members (R-1.2, R-1.3)."""

import datetime as dt
import logging
from uuid import UUID

import psycopg

from roomly.db import Database
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
from roomly.entity import Invitation, User
from roomly.mapper import GroupMapper, InvitationMapper, MembershipMapper
from roomly.service.access import require_member, require_owner
from roomly.service.errors import Conflict, Forbidden, NotFound

logger = logging.getLogger(__name__)

MAX_MEMBERS = 6


class GroupService:
    def __init__(self, db: Database, *, invitation_ttl: dt.timedelta) -> None:
        self.db = db
        self.invitation_ttl = invitation_ttl

    def create(self, user: User, req: CreateGroupRequest) -> GroupDetailDTO:
        if user.is_admin:
            raise Forbidden("administrators cannot be group members")
        with self.db.transaction() as conn:
            group = GroupMapper(conn).insert(req.name)
            MembershipMapper(conn).insert(group.id, user.id, "owner")
            detail = self._detail(conn, group.id, "owner")
        logger.info("group created group=%s owner=%s", group.id, user.id)
        return detail

    def list_mine(self, user: User) -> list[GroupSummaryDTO]:
        with self.db.transaction() as conn:
            rows = GroupMapper(conn).list_for_user(user.id)
        return [GroupSummaryDTO(id=r.id, name=r.name, role=r.role, member_count=r.member_count, created_at=r.created_at)
                for r in rows]

    def get(self, user: User, group_id: UUID) -> GroupDetailDTO:
        with self.db.transaction() as conn:
            _, membership = require_member(conn, user, group_id)
            return self._detail(conn, group_id, membership.role)

    def invite(self, user: User, group_id: UUID, req: InviteRequest) -> InvitationDTO:
        with self.db.transaction() as conn:
            require_owner(conn, user, group_id, lock=True)
            if MembershipMapper(conn).count_current(group_id) >= MAX_MEMBERS:
                raise Conflict(f"the group already has {MAX_MEMBERS} members")
            if MembershipMapper(conn).find_current_by_email(group_id, req.email) is not None:
                raise Conflict("that person is already a member")
            invitations = InvitationMapper(conn)
            if invitations.find_live_pending(group_id, req.email) is not None:
                raise Conflict("an invitation to that address is already pending")
            now = dt.datetime.now(dt.UTC)
            invitation = invitations.insert(group_id, req.email, user.id, now + self.invitation_ttl)
        logger.info("invitation created group=%s invitation=%s", group_id, invitation.id)
        return InvitationDTO.from_entity(invitation, now)

    def list_invitations(self, user: User, group_id: UUID) -> list[InvitationDTO]:
        with self.db.transaction() as conn:
            require_member(conn, user, group_id)
            rows = InvitationMapper(conn).list_for_group(group_id)
        now = dt.datetime.now(dt.UTC)
        return [InvitationDTO.from_entity(i, now) for i in rows]

    def incoming(self, user: User) -> list[IncomingInvitationDTO]:
        assert user.email is not None
        with self.db.transaction() as conn:
            rows = InvitationMapper(conn).list_pending_for_email(user.email)
        return [IncomingInvitationDTO(id=r.id, group_id=r.group_id, group_name=r.group_name,
                                      invited_by=r.invited_by_name, created_at=r.created_at, expires_at=r.expires_at)
                for r in rows]

    def accept(self, user: User, invitation_id: UUID) -> GroupDetailDTO:
        """§8.1.2.2 flow 3 and alt. flows 1-2: one membership per invitation, never past six."""
        with self.db.transaction() as conn:
            invitations = InvitationMapper(conn)
            invitation = self._own_pending(invitations, user, invitation_id)
            if GroupMapper(conn).lock(invitation.group_id) is None:
                raise NotFound("invitation not found")
            memberships = MembershipMapper(conn)
            if memberships.find_current(invitation.group_id, user.id) is not None:
                raise Conflict("you are already a member of this group")
            if memberships.count_current(invitation.group_id) >= MAX_MEMBERS:
                raise Conflict(f"the group already has {MAX_MEMBERS} members")
            if user.is_admin:
                raise Forbidden("administrators cannot be group members")
            memberships.insert(invitation.group_id, user.id, "member")
            invitations.respond(invitation.id, "accepted")
            detail = self._detail(conn, invitation.group_id, "member")
        logger.info("invitation accepted group=%s user=%s", invitation.group_id, user.id)
        return detail

    def decline(self, user: User, invitation_id: UUID) -> None:
        with self.db.transaction() as conn:
            invitations = InvitationMapper(conn)
            invitation = self._own_pending(invitations, user, invitation_id)
            invitations.respond(invitation.id, "declined")
        logger.info("invitation declined invitation=%s", invitation_id)

    def leave(self, user: User, group_id: UUID) -> None:
        """An owner must transfer first; a sole owner leaving dissolves the group."""
        with self.db.transaction() as conn:
            _, membership = require_member(conn, user, group_id, lock=True)
            memberships = MembershipMapper(conn)
            if membership.is_owner:
                if memberships.count_current(group_id) > 1:
                    raise Conflict("transfer ownership to another member before leaving")
                GroupMapper(conn).delete(group_id)
                logger.info("group dissolved by its last member group=%s", group_id)
                return
            memberships.end(membership.id)
        logger.info("member left group=%s user=%s", group_id, user.id)

    def remove_member(self, user: User, group_id: UUID, member_id: UUID) -> None:
        with self.db.transaction() as conn:
            require_owner(conn, user, group_id, lock=True)
            if member_id == user.id:
                raise Conflict("owners leave through /leave after transferring ownership")
            memberships = MembershipMapper(conn)
            target = memberships.find_current(group_id, member_id)
            if target is None:
                raise NotFound("that user is not a current member")
            memberships.end(target.id)
        logger.info("member removed group=%s user=%s", group_id, member_id)

    def transfer(self, user: User, group_id: UUID, req: TransferOwnershipRequest) -> GroupDetailDTO:
        with self.db.transaction() as conn:
            _, mine = require_owner(conn, user, group_id, lock=True)
            if req.user_id == user.id:
                raise Conflict("you already own this group")
            memberships = MembershipMapper(conn)
            target = memberships.find_current(group_id, req.user_id)
            if target is None:
                raise NotFound("the new owner must be a current member")
            memberships.set_role(mine.id, "member")   # demote first: one current owner per group
            memberships.set_role(target.id, "owner")
            detail = self._detail(conn, group_id, "member")
        logger.info("ownership transferred group=%s to=%s", group_id, req.user_id)
        return detail

    def _own_pending(self, invitations: InvitationMapper, user: User, invitation_id: UUID) -> Invitation:
        invitation = invitations.lock(invitation_id)
        if invitation is None or invitation.email != user.email:
            raise NotFound("invitation not found")  # never confirm invitations addressed to others
        if invitation.status != "pending":
            raise Conflict(f"this invitation was already {invitation.status}")
        if invitation.expires_at <= dt.datetime.now(dt.UTC):
            raise Conflict("this invitation has expired")
        return invitation

    def _detail(self, conn: psycopg.Connection, group_id: UUID, my_role: str) -> GroupDetailDTO:
        group = GroupMapper(conn).find(group_id)
        assert group is not None
        members = [MemberDTO(user=PersonRef.of(m.user_id, m.display_name, m.deleted), role=m.role, joined_at=m.joined_at)
                   for m in MembershipMapper(conn).list_current(group_id)]
        return GroupDetailDTO(id=group.id, name=group.name, created_at=group.created_at, my_role=my_role, members=members)
