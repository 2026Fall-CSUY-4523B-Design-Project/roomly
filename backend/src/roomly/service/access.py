"""Current-membership checks shared by the group, comparison and room services.

Every group action re-reads the membership inside the transaction that performs it, so a
member who left or was removed cannot act on a stale page. Membership is a soft flag
(``left_at``), so these helpers always look at current rows only.
"""

from uuid import UUID

from roomly.db import Tx
from roomly.entity import Group, Membership, User
from roomly.mapper.group_mapper import GroupMapper, MembershipMapper
from roomly.service.errors import Forbidden, NotFound


def require_member(tx: Tx, group_id: UUID, user: User) -> tuple[Group, Membership]:
    """The group and the caller's current membership, or 404 / 403."""
    group = GroupMapper(tx).find(group_id)
    if group is None:
        raise NotFound("Group not found.")
    membership = MembershipMapper(tx).find_current(group_id, user.id)
    if membership is None:
        raise Forbidden("You are not a member of this group.")
    return group, membership


def require_owner(tx: Tx, group_id: UUID, user: User) -> tuple[Group, Membership]:
    """Like ``require_member`` but only the current owner passes."""
    group, membership = require_member(tx, group_id, user)
    if not membership.is_owner:
        raise Forbidden("Only the group owner can do this.")
    return group, membership
