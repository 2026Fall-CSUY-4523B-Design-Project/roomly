"""Server-side access checks shared by every service that touches private group content (§6.2)."""

from uuid import UUID

import psycopg

from roomly.entity import Group, Membership, User
from roomly.mapper import GroupMapper, MembershipMapper
from roomly.service.errors import Forbidden, NotFound


def require_member(conn: psycopg.Connection, user: User, group_id: UUID, *, lock: bool = False) -> tuple[Group, Membership]:
    """The group and the caller's current membership. Administrators get no access by role."""
    groups = GroupMapper(conn)
    group = groups.lock(group_id) if lock else groups.find(group_id)
    if group is None:
        raise NotFound("group not found")
    membership = MembershipMapper(conn).find_current(group_id, user.id)
    if membership is None:
        raise Forbidden("only current members can access this group")
    return group, membership


def require_owner(conn: psycopg.Connection, user: User, group_id: UUID, *, lock: bool = False) -> tuple[Group, Membership]:
    group, membership = require_member(conn, user, group_id, lock=lock)
    if not membership.is_owner:
        raise Forbidden("only the group owner can do this")
    return group, membership


def require_admin(user: User) -> None:
    if not user.is_admin:
        raise Forbidden("administrators only")
