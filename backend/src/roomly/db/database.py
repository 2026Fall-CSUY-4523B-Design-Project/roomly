"""The app's database: PostgreSQL first, SQLite as the fallback.

``DATABASE_URL`` names the primary. When it is a ``postgresql://`` URL that cannot be
reached at startup and a fallback file is configured (``ROOMLY_SQLITE_FALLBACK``; on by
default in dev, off in prod), Roomly logs a warning and runs on that SQLite file instead.
``DATABASE_URL=sqlite:///path/to/file.sqlite3`` runs on SQLite only.

The fallback is a separate database: what is written there is not copied into Postgres later.
"""

import logging
from contextlib import AbstractContextManager
from pathlib import Path

import psycopg
from psycopg_pool import PoolTimeout

from roomly.db.backend import PostgresBackend, SqliteBackend, Tx
from roomly.db.migrate import migrate_backend

logger = logging.getLogger(__name__)

SQLITE_PREFIX = "sqlite:///"
Backend = PostgresBackend | SqliteBackend


def sqlite_path(url: str) -> Path:
    """``sqlite:///relative.db`` or ``sqlite:////absolute/path.db``."""
    path = url.removeprefix(SQLITE_PREFIX)
    if not path or path == ":memory:":
        raise ValueError("SQLite needs a file path (connections are per transaction, so :memory: cannot work)")
    return Path(path)


class Database:
    def __init__(self, url: str, *, fallback: Path | None = None, min_size: int = 1, max_size: int = 10) -> None:
        self.url = url
        self.fallback = fallback
        self.min_size = min_size
        self.max_size = max_size
        self._backend: Backend | None = None

    @property
    def dialect(self) -> str | None:
        """'postgres' or 'sqlite' once open; None before."""
        return self._backend.dialect if self._backend else None

    @property
    def backend(self) -> Backend:
        if self._backend is None:
            raise RuntimeError("database is not open")
        return self._backend

    def open(self, timeout: float = 10.0) -> None:
        if self._backend is not None:
            return
        if self.url.startswith(SQLITE_PREFIX):
            backend: Backend = SqliteBackend(sqlite_path(self.url))
            backend.open()
        else:
            backend = self._open_postgres(timeout)
        self._backend = backend
        logger.info("database open: %s", backend.describe())

    def _open_postgres(self, timeout: float) -> Backend:
        try:
            psycopg.connect(self.url, connect_timeout=3).close()   # fail fast before building a pool
            backend = PostgresBackend(self.url, min_size=self.min_size, max_size=self.max_size)
            backend.open(timeout)
            return backend
        except (psycopg.OperationalError, PoolTimeout) as exc:
            if self.fallback is None:
                raise
            reason = str(exc).strip().splitlines()[0] if str(exc).strip() else type(exc).__name__
            logger.warning("PostgreSQL unreachable (%s); falling back to SQLite at %s", reason, self.fallback)
            sqlite = SqliteBackend(self.fallback)
            sqlite.open()
            return sqlite

    def close(self) -> None:
        if self._backend is not None:
            self._backend.close()
            self._backend = None
            logger.info("database closed")

    def transaction(self) -> AbstractContextManager[Tx]:
        """Commit when the block exits normally, roll back when it raises."""
        return self.backend.transaction()

    def migrate(self, migrations_root: Path) -> list[str]:
        """Apply pending migrations from ``<migrations_root>/<dialect>/``."""
        return migrate_backend(self.backend, migrations_root)
