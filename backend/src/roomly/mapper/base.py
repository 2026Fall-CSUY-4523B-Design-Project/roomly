"""SQL mapper base: hand-written SQL in, entity dataclasses out (MyBatis-style, no ORM).

A mapper is bound to one transaction (``Tx``), so every call inside a service's
``with db.transaction() as tx`` block commits or rolls back together. SQL uses named
parameters (``%(name)s``) in the subset PostgreSQL and SQLite share; values are never
formatted into the SQL string. The only formatting is ``columns(Entity)`` (the entity's own
field names) and the dialect fragments ``tx.any_of`` / ``tx.contains_all``.
"""

from collections.abc import Callable
from dataclasses import fields
from typing import Any

from roomly.db import Json, Tx

Params = dict[str, Any] | None


def columns(entity: type, alias: str = "") -> str:
    """``columns(User, "u")`` -> ``u.id, u.email, ...`` in field order."""
    prefix = f"{alias}." if alias else ""
    return ", ".join(prefix + f.name for f in fields(entity))


def jsonb(value: Any) -> Json:
    """Mark a parameter for a JSON column."""
    return Json(value)


class Mapper:
    def __init__(self, tx: Tx) -> None:
        self.tx = tx

    def _one[T](self, entity: type[T], sql: str, params: Params = None) -> T | None:
        return self.tx.one(entity, sql, params)

    def _all[T](self, entity: type[T], sql: str, params: Params = None) -> list[T]:
        return self.tx.all(entity, sql, params)

    def _scalar(self, sql: str, params: Params = None, as_type: Callable[[Any], Any] | None = None) -> Any:
        return self.tx.scalar(sql, params, as_type)

    def _exec(self, sql: str, params: Params = None) -> int:
        """Run a write; returns the number of rows it touched."""
        return self.tx.exec(sql, params)
