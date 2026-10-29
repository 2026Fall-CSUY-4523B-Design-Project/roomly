"""Database backends: PostgreSQL (primary) and SQLite (fallback) behind one transaction API.

Mappers write each statement once, in the SQL both engines share, with psycopg-style named
parameters (``%(name)s``). The few constructs that differ come from the transaction itself:
``tx.any_of`` (value in a list parameter) and ``tx.contains_all`` (array containment).

``SqliteTx`` rewrites parameters to ``:name`` and drops ``FOR UPDATE`` (a SQLite write
transaction is already exclusive: it starts with BEGIN IMMEDIATE). It stores UUIDs, times
and dates as text, booleans as 0/1, and lists or JSON as JSON text, then converts rows back to
the annotated dataclass field types, so mappers and services see the same Python values
from both engines. Timestamps are UTC text in one fixed-width format, so comparing them as
text orders them correctly.
"""

import dataclasses
import datetime as dt
import decimal
import json
import re
import sqlite3
import types
import typing
import uuid
from abc import ABC, abstractmethod
from collections.abc import Callable, Iterator
from contextlib import closing, contextmanager
from functools import cache
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import class_row
from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool, PoolTimeout

Params = dict[str, Any] | None

# exceptions the controller layer maps to 409 / 503, whichever engine raised them
IntegrityError = (psycopg.errors.IntegrityError, sqlite3.IntegrityError)
UnavailableError = (psycopg.OperationalError, PoolTimeout, sqlite3.OperationalError)

SQLITE_TIMESTAMP = "%Y-%m-%dT%H:%M:%S.%f+00:00"


class Json:
    """A value for a JSON column: jsonb in Postgres, JSON text in SQLite."""

    __slots__ = ("value",)

    def __init__(self, value: Any) -> None:
        self.value = value


class Tx(ABC):
    """One open transaction. Mappers reach the database only through this interface."""

    dialect: str

    @abstractmethod
    def one[T](self, entity: type[T], sql: str, params: Params = None) -> T | None: ...

    @abstractmethod
    def all[T](self, entity: type[T], sql: str, params: Params = None) -> list[T]: ...

    @abstractmethod
    def scalar(self, sql: str, params: Params = None, as_type: Callable[[Any], Any] | None = None) -> Any: ...

    @abstractmethod
    def rows(self, sql: str, params: Params = None) -> list[tuple[Any, ...]]:
        """Raw tuples, unconverted (scripts and tests)."""

    @abstractmethod
    def exec(self, sql: str, params: Params = None) -> int:
        """Run a write; returns the number of rows it touched."""

    @abstractmethod
    def any_of(self, expr: str, param: str, element: str) -> str:
        """SQL for ``expr`` equal to one item of the list parameter ``param`` (items of SQL type ``element``)."""

    @abstractmethod
    def contains_all(self, column: str, param: str) -> str:
        """SQL for the text-array ``column`` containing every item of the list parameter ``param``."""


# --- PostgreSQL ------------------------------------------------------------------------


class PostgresTx(Tx):
    dialect = "postgres"

    def __init__(self, conn: psycopg.Connection) -> None:
        self.conn = conn

    @staticmethod
    def _params(params: Params) -> Params:
        if params is None:
            return None
        return {k: Jsonb(v.value) if isinstance(v, Json) else v for k, v in params.items()}

    def one[T](self, entity: type[T], sql: str, params: Params = None) -> T | None:
        with self.conn.cursor(row_factory=class_row(entity)) as cur:
            cur.execute(sql, self._params(params))
            return cur.fetchone()

    def all[T](self, entity: type[T], sql: str, params: Params = None) -> list[T]:
        with self.conn.cursor(row_factory=class_row(entity)) as cur:
            cur.execute(sql, self._params(params))
            return cur.fetchall()

    def scalar(self, sql: str, params: Params = None, as_type: Callable[[Any], Any] | None = None) -> Any:
        row = self.conn.execute(sql, self._params(params)).fetchone()
        return row[0] if row else None  # psycopg already returns the Python type

    def rows(self, sql: str, params: Params = None) -> list[tuple[Any, ...]]:
        return self.conn.execute(sql, self._params(params)).fetchall()

    def exec(self, sql: str, params: Params = None) -> int:
        return self.conn.execute(sql, self._params(params)).rowcount

    def any_of(self, expr: str, param: str, element: str) -> str:
        return f"{expr} = ANY(%({param})s::{element}[])"

    def contains_all(self, column: str, param: str) -> str:
        return f"{column} @> %({param})s::text[]"


class PostgresBackend:
    dialect = "postgres"

    def __init__(self, url: str, *, min_size: int, max_size: int) -> None:
        self.url = url
        self.pool = ConnectionPool(url, min_size=min_size, max_size=max_size, open=False, name="roomly")

    def open(self, timeout: float) -> None:
        self.pool.open(wait=True, timeout=timeout)

    def close(self) -> None:
        self.pool.close()

    @contextmanager
    def transaction(self) -> Iterator[Tx]:
        with self.pool.connection() as conn:   # commits on normal exit, rolls back on error
            yield PostgresTx(conn)

    def describe(self) -> str:
        info = psycopg.conninfo.conninfo_to_dict(self.url)   # never log the password
        return f"postgres {info.get('host', 'localhost')}:{info.get('port', 5432)}/{info.get('dbname', '')}"


# --- SQLite ----------------------------------------------------------------------------

_PARAM = re.compile(r"%\((\w+)\)s")
_FOR_UPDATE = re.compile(r"\s+FOR\s+UPDATE\b", re.IGNORECASE)


@cache
def _sqlite_sql(sql: str) -> str:
    return _FOR_UPDATE.sub("", _PARAM.sub(r":\1", sql))


def _to_sqlite(v: Any) -> Any:
    if v is None or isinstance(v, (str, int, float, bytes)):  # bool is an int: stored as 0/1
        return v
    if isinstance(v, Json):
        return json.dumps(v.value, default=str)
    if isinstance(v, uuid.UUID):
        return str(v)
    if isinstance(v, dt.datetime):
        aware = v if v.tzinfo is not None else v.replace(tzinfo=dt.UTC)
        return aware.astimezone(dt.UTC).strftime(SQLITE_TIMESTAMP)
    if isinstance(v, (dt.date, dt.time)):
        return v.isoformat()
    if isinstance(v, decimal.Decimal):
        return float(v)
    if isinstance(v, (list, tuple, dict)):
        return json.dumps(v, default=str)
    raise TypeError(f"cannot store {type(v).__name__} in SQLite")


def _identity(v: Any) -> Any:
    return v


def _converter(tp: Any) -> Callable[[Any], Any]:
    if typing.get_origin(tp) in (typing.Union, types.UnionType):
        tp = next(a for a in typing.get_args(tp) if a is not type(None))
    origin = typing.get_origin(tp) or tp
    simple: dict[Any, Callable[[Any], Any]] = {
        uuid.UUID: uuid.UUID, dt.datetime: dt.datetime.fromisoformat, dt.date: dt.date.fromisoformat,
        dt.time: dt.time.fromisoformat, bool: bool, int: int, float: float,
        decimal.Decimal: lambda v: decimal.Decimal(str(v)), list: json.loads, dict: json.loads,
    }
    return simple.get(origin, _identity)


@cache
def _converters(entity: type) -> dict[str, Callable[[Any], Any]]:
    hints = typing.get_type_hints(entity)
    return {f.name: _converter(hints[f.name]) for f in dataclasses.fields(entity)}


class SqliteTx(Tx):
    dialect = "sqlite"

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def _run(self, sql: str, params: Params) -> sqlite3.Cursor:
        values = {k: _to_sqlite(v) for k, v in (params or {}).items()}
        return self.conn.execute(_sqlite_sql(sql), values)

    def _build[T](self, entity: type[T], cur: sqlite3.Cursor, rows: list[tuple[Any, ...]]) -> list[T]:
        names = [d[0] for d in cur.description]
        conv = _converters(entity)
        return [entity(**{n: None if v is None else conv[n](v) for n, v in zip(names, row, strict=True)})
                for row in rows]

    def one[T](self, entity: type[T], sql: str, params: Params = None) -> T | None:
        cur = self._run(sql, params)
        rows = cur.fetchall()  # drain: an unfinished INSERT ... RETURNING would block COMMIT
        return self._build(entity, cur, rows[:1])[0] if rows else None

    def all[T](self, entity: type[T], sql: str, params: Params = None) -> list[T]:
        cur = self._run(sql, params)
        return self._build(entity, cur, cur.fetchall())

    def scalar(self, sql: str, params: Params = None, as_type: Callable[[Any], Any] | None = None) -> Any:
        rows = self._run(sql, params).fetchall()
        value = rows[0][0] if rows else None
        return value if value is None or as_type is None else as_type(value)

    def rows(self, sql: str, params: Params = None) -> list[tuple[Any, ...]]:
        return self._run(sql, params).fetchall()

    def exec(self, sql: str, params: Params = None) -> int:
        return self._run(sql, params).rowcount

    def any_of(self, expr: str, param: str, element: str) -> str:
        return f"{expr} IN (SELECT value FROM json_each(%({param})s))"

    def contains_all(self, column: str, param: str) -> str:
        return (f"NOT EXISTS (SELECT 1 FROM json_each(%({param})s) wanted "
                f"WHERE wanted.value NOT IN (SELECT value FROM json_each({column})))")


def _sqlite_now() -> str:
    return dt.datetime.now(dt.UTC).strftime(SQLITE_TIMESTAMP)


def _sqlite_regexp(pattern: str, value: str | None) -> bool | None:
    """``value REGEXP pattern`` with Postgres ``~`` semantics: a search, and NULL in, NULL out
    (so a CHECK on a NULL column passes, as in SQL)."""
    return None if value is None else re.search(pattern, value) is not None


class SqliteBackend:
    dialect = "sqlite"

    def __init__(self, path: Path) -> None:
        self.path = path

    def connect(self) -> sqlite3.Connection:
        """A connection in manual-transaction mode with Roomly's SQL functions registered."""
        conn = sqlite3.connect(self.path, isolation_level=None, timeout=10)
        conn.execute("PRAGMA foreign_keys = ON")
        conn.create_function("gen_random_uuid", 0, lambda: str(uuid.uuid4()))
        conn.create_function("now", 0, _sqlite_now)
        conn.create_function("regexp", 2, _sqlite_regexp, deterministic=True)
        return conn

    def open(self, timeout: float = 10.0) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self.connect()) as conn:
            conn.execute("PRAGMA journal_mode = WAL")   # readers do not block the writer

    def close(self) -> None:
        pass  # connections are per transaction

    @contextmanager
    def transaction(self) -> Iterator[Tx]:
        with closing(self.connect()) as conn:
            conn.execute("BEGIN IMMEDIATE")   # take the write lock now: no upgrade deadlocks later
            try:
                yield SqliteTx(conn)
            except BaseException:
                conn.execute("ROLLBACK")
                raise
            conn.execute("COMMIT")

    def describe(self) -> str:
        return f"sqlite {self.path}"


# --- errors ----------------------------------------------------------------------------

_SQLITE_CONSTRAINT = re.compile(r"^(?:CHECK|UNIQUE|NOT NULL|FOREIGN KEY) constraint failed(?:: (.+))?$")
_NAME = re.compile(r"^[a-z][a-z0-9_]*$")


def constraint_name(exc: BaseException) -> str | None:
    """The violated constraint. SQLite triggers raise ``"<constraint>: <message>"``."""
    if isinstance(exc, psycopg.Error):
        return exc.diag.constraint_name
    text = str(exc)
    m = _SQLITE_CONSTRAINT.match(text)
    if m:
        return m.group(1)
    head, sep, _ = text.partition(": ")
    return head if sep and _NAME.match(head) else None


def error_message(exc: BaseException) -> str:
    if isinstance(exc, psycopg.Error):
        return exc.diag.message_primary or str(exc)
    head, sep, rest = str(exc).partition(": ")
    return rest if sep and _NAME.match(head) else str(exc)
