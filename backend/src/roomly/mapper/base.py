"""SQL mapper base: hand-written SQL in, entity dataclasses out (MyBatis-style, no ORM).

A mapper is bound to one connection, so every call inside a service's
``with db.transaction() as conn`` block shares that transaction. SQL uses psycopg named
parameters (``%(name)s``); values are never formatted into the SQL string. The only
formatting is ``columns(Entity)``, which expands to the entity's own field names.
"""

from dataclasses import fields
from typing import Any

import psycopg
from psycopg.rows import class_row
from psycopg.types.json import Jsonb

Params = dict[str, Any] | None


def columns(entity: type, alias: str = "") -> str:
    """``columns(User, "u")`` -> ``u.id, u.email, ...`` in field order."""
    prefix = f"{alias}." if alias else ""
    return ", ".join(prefix + f.name for f in fields(entity))


def jsonb(value: Any) -> Jsonb:
    return Jsonb(value)


class Mapper:
    def __init__(self, conn: psycopg.Connection) -> None:
        self.conn = conn

    def _one[T](self, entity: type[T], sql: str, params: Params = None) -> T | None:
        with self.conn.cursor(row_factory=class_row(entity)) as cur:
            cur.execute(sql, params)
            return cur.fetchone()

    def _all[T](self, entity: type[T], sql: str, params: Params = None) -> list[T]:
        with self.conn.cursor(row_factory=class_row(entity)) as cur:
            cur.execute(sql, params)
            return cur.fetchall()

    def _scalar(self, sql: str, params: Params = None) -> Any:
        row = self.conn.execute(sql, params).fetchone()
        return row[0] if row else None

    def _rows(self, sql: str, params: Params = None) -> list[tuple[Any, ...]]:
        return self.conn.execute(sql, params).fetchall()

    def _exec(self, sql: str, params: Params = None) -> int:
        """Run a write; returns the number of rows it touched."""
        return self.conn.execute(sql, params).rowcount
