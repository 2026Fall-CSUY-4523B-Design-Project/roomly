"""SQL for comparison and comparison_listing."""

from typing import Any
from uuid import UUID

from roomly.entity import Comparison, ComparisonListing
from roomly.mapper.base import Mapper, columns, jsonb

_COMPARISON = columns(Comparison)
_ITEM = columns(ComparisonListing)


class ComparisonMapper(Mapper):
    def insert(self, saved_by: UUID, group_id: UUID | None, title: str | None) -> Comparison:
        """Saved with a group = shared with it at once."""
        sql = f"""
            INSERT INTO comparison (saved_by, group_id, title, shared_at)
            VALUES (%(saved_by)s, %(group_id)s, %(title)s, CASE WHEN %(shared)s THEN now() END)
            RETURNING {_COMPARISON}"""
        params = {"saved_by": saved_by, "group_id": group_id, "title": title, "shared": group_id is not None}
        comparison = self._one(Comparison, sql, params)
        assert comparison is not None
        return comparison

    def add_listing(self, comparison_id: UUID, position: int, listing_id: UUID, snapshot: dict[str, Any]) -> None:
        self._exec(
            """INSERT INTO comparison_listing (comparison_id, position, listing_id, snapshot)
               VALUES (%(comparison_id)s, %(position)s, %(listing_id)s, %(snapshot)s)""",
            {"comparison_id": comparison_id, "position": position, "listing_id": listing_id, "snapshot": jsonb(snapshot)},
        )

    def find(self, comparison_id: UUID) -> Comparison | None:
        return self._one(Comparison, f"SELECT {_COMPARISON} FROM comparison WHERE id = %(id)s", {"id": comparison_id})

    def items(self, comparison_id: UUID) -> list[ComparisonListing]:
        sql = f"SELECT {_ITEM} FROM comparison_listing WHERE comparison_id = %(id)s ORDER BY position"
        return self._all(ComparisonListing, sql, {"id": comparison_id})

    def list_for_group(self, group_id: UUID) -> list[Comparison]:
        sql = f"SELECT {_COMPARISON} FROM comparison WHERE group_id = %(id)s ORDER BY shared_at DESC"
        return self._all(Comparison, sql, {"id": group_id})

    def list_personal(self, user_id: UUID) -> list[Comparison]:
        sql = f"SELECT {_COMPARISON} FROM comparison WHERE saved_by = %(id)s AND group_id IS NULL ORDER BY saved_at DESC"
        return self._all(Comparison, sql, {"id": user_id})

    def share(self, comparison_id: UUID, group_id: UUID) -> Comparison | None:
        sql = f"""
            UPDATE comparison SET group_id = %(group_id)s, shared_at = now()
             WHERE id = %(id)s AND group_id IS NULL
            RETURNING {_COMPARISON}"""
        return self._one(Comparison, sql, {"id": comparison_id, "group_id": group_id})

    def delete_personal_for_user(self, user_id: UUID) -> int:
        return self._exec("DELETE FROM comparison WHERE saved_by = %(id)s AND group_id IS NULL", {"id": user_id})
