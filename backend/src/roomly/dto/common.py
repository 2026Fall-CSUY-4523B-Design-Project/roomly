"""Response pieces shared by several domains."""

from uuid import UUID

from roomly.dto.base import DTO

DELETED_USER = "Deleted user"   # R-1.4: shared content of a deleted account
UNNAMED_MEMBER = "Member"


class PersonRef(DTO):
    """Who wrote, saved or owns something. A deleted account keeps its id but shows no name."""

    id: UUID | None
    name: str
    deleted: bool

    @classmethod
    def of(cls, user_id: UUID | None, display_name: str | None, deleted: bool) -> PersonRef:
        if user_id is None or deleted:
            return cls(id=user_id, name=DELETED_USER, deleted=True)
        return cls(id=user_id, name=display_name or UNNAMED_MEMBER, deleted=False)


class Page[T](DTO):
    """One page of results plus the total count, for list endpoints."""

    items: list[T]
    total: int
    limit: int
    offset: int
