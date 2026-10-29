"""SQL for user_group, group_membership and group_invitation."""

import datetime as dt
from dataclasses import dataclass
from uuid import UUID

from roomly.entity import Group, Invitation, Membership
from roomly.mapper.base import Mapper, columns

_GROUP = columns(Group)
_GROUP_G = columns(Group, "g")
_MEMBERSHIP = columns(Membership)
_INVITATION = columns(Invitation)


@dataclass(frozen=True)
class GroupWithRole:
    id: UUID
    name: str
    created_at: dt.datetime
    role: str
    member_count: int


@dataclass(frozen=True)
class MemberRow:
    user_id: UUID
    display_name: str | None
    role: str
    joined_at: dt.datetime
    deleted: bool


@dataclass(frozen=True)
class InvitationForInvitee:
    id: UUID
    group_id: UUID
    group_name: str
    invited_by_name: str | None
    created_at: dt.datetime
    expires_at: dt.datetime


class GroupMapper(Mapper):
    def insert(self, name: str) -> Group:
        group = self._one(Group, f"INSERT INTO user_group (name) VALUES (%(name)s) RETURNING {_GROUP}", {"name": name})
        assert group is not None
        return group

    def find(self, group_id: UUID) -> Group | None:
        return self._one(Group, f"SELECT {_GROUP} FROM user_group WHERE id = %(id)s", {"id": group_id})

    def lock(self, group_id: UUID) -> Group | None:
        """Row lock that serializes membership changes for one group."""
        return self._one(Group, f"SELECT {_GROUP} FROM user_group WHERE id = %(id)s FOR UPDATE", {"id": group_id})

    def delete(self, group_id: UUID) -> int:
        return self._exec("DELETE FROM user_group WHERE id = %(id)s", {"id": group_id})

    def list_for_user(self, user_id: UUID) -> list[GroupWithRole]:
        sql = f"""
            SELECT {_GROUP_G}, m.role,
                   (SELECT count(*) FROM group_membership c WHERE c.group_id = g.id AND c.left_at IS NULL) AS member_count
              FROM group_membership m JOIN user_group g ON g.id = m.group_id
             WHERE m.user_id = %(user_id)s AND m.left_at IS NULL
             ORDER BY g.created_at DESC"""
        return self._all(GroupWithRole, sql, {"user_id": user_id})


class MembershipMapper(Mapper):
    def insert(self, group_id: UUID, user_id: UUID, role: str) -> Membership:
        sql = f"""
            INSERT INTO group_membership (group_id, user_id, role)
            VALUES (%(group_id)s, %(user_id)s, %(role)s)
            RETURNING {_MEMBERSHIP}"""
        membership = self._one(Membership, sql, {"group_id": group_id, "user_id": user_id, "role": role})
        assert membership is not None
        return membership

    def find_current(self, group_id: UUID, user_id: UUID) -> Membership | None:
        sql = f"""
            SELECT {_MEMBERSHIP} FROM group_membership
             WHERE group_id = %(group_id)s AND user_id = %(user_id)s AND left_at IS NULL"""
        return self._one(Membership, sql, {"group_id": group_id, "user_id": user_id})

    def find_current_by_email(self, group_id: UUID, email: str) -> Membership | None:
        sql = f"""
            SELECT {columns(Membership, "m")}
              FROM group_membership m JOIN app_user u ON u.id = m.user_id
             WHERE m.group_id = %(group_id)s AND u.email = %(email)s AND m.left_at IS NULL"""
        return self._one(Membership, sql, {"group_id": group_id, "email": email})

    def count_current(self, group_id: UUID) -> int:
        return int(self._scalar(
            "SELECT count(*) FROM group_membership WHERE group_id = %(id)s AND left_at IS NULL", {"id": group_id}
        ))

    def list_current(self, group_id: UUID) -> list[MemberRow]:
        sql = """
            SELECT m.user_id, u.display_name, m.role, m.joined_at, u.deleted_at IS NOT NULL AS deleted
              FROM group_membership m JOIN app_user u ON u.id = m.user_id
             WHERE m.group_id = %(group_id)s AND m.left_at IS NULL
             ORDER BY (m.role = 'owner') DESC, m.joined_at"""
        return self._all(MemberRow, sql, {"group_id": group_id})

    def end(self, membership_id: UUID) -> int:
        return self._exec(
            "UPDATE group_membership SET left_at = now() WHERE id = %(id)s AND left_at IS NULL", {"id": membership_id}
        )

    def set_role(self, membership_id: UUID, role: str) -> int:
        return self._exec("UPDATE group_membership SET role = %(role)s WHERE id = %(id)s", {"id": membership_id, "role": role})

    def current_for_user(self, user_id: UUID) -> list[Membership]:
        sql = f"SELECT {_MEMBERSHIP} FROM group_membership WHERE user_id = %(id)s AND left_at IS NULL"
        return self._all(Membership, sql, {"id": user_id})

    def end_all_for_user(self, user_id: UUID) -> int:
        return self._exec(
            "UPDATE group_membership SET left_at = now() WHERE user_id = %(id)s AND left_at IS NULL", {"id": user_id}
        )


class InvitationMapper(Mapper):
    def insert(self, group_id: UUID, email: str, invited_by: UUID, expires_at: dt.datetime) -> Invitation:
        sql = f"""
            INSERT INTO group_invitation (group_id, email, invited_by, expires_at)
            VALUES (%(group_id)s, %(email)s, %(invited_by)s, %(expires_at)s)
            RETURNING {_INVITATION}"""
        params = {"group_id": group_id, "email": email, "invited_by": invited_by, "expires_at": expires_at}
        invitation = self._one(Invitation, sql, params)
        assert invitation is not None
        return invitation

    def find(self, invitation_id: UUID) -> Invitation | None:
        return self._one(Invitation, f"SELECT {_INVITATION} FROM group_invitation WHERE id = %(id)s", {"id": invitation_id})

    def lock(self, invitation_id: UUID) -> Invitation | None:
        sql = f"SELECT {_INVITATION} FROM group_invitation WHERE id = %(id)s FOR UPDATE"
        return self._one(Invitation, sql, {"id": invitation_id})

    def find_live_pending(self, group_id: UUID, email: str) -> Invitation | None:
        sql = f"""
            SELECT {_INVITATION} FROM group_invitation
             WHERE group_id = %(group_id)s AND email = %(email)s AND status = 'pending' AND expires_at > now()"""
        return self._one(Invitation, sql, {"group_id": group_id, "email": email})

    def list_for_group(self, group_id: UUID) -> list[Invitation]:
        sql = f"SELECT {_INVITATION} FROM group_invitation WHERE group_id = %(id)s ORDER BY created_at DESC"
        return self._all(Invitation, sql, {"id": group_id})

    def list_pending_for_email(self, email: str) -> list[InvitationForInvitee]:
        sql = """
            SELECT i.id, i.group_id, g.name AS group_name, u.display_name AS invited_by_name, i.created_at, i.expires_at
              FROM group_invitation i
              JOIN user_group g ON g.id = i.group_id
              LEFT JOIN app_user u ON u.id = i.invited_by
             WHERE i.email = %(email)s AND i.status = 'pending' AND i.expires_at > now()
             ORDER BY i.created_at DESC"""
        return self._all(InvitationForInvitee, sql, {"email": email})

    def respond(self, invitation_id: UUID, status: str) -> int:
        return self._exec(
            """UPDATE group_invitation SET status = %(status)s, responded_at = now()
                WHERE id = %(id)s AND status = 'pending'""",
            {"id": invitation_id, "status": status},
        )

    def delete_pending_for_email(self, email: str) -> int:
        return self._exec("DELETE FROM group_invitation WHERE email = %(email)s AND status = 'pending'", {"email": email})
