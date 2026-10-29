"""Connection pool and transaction scope. Services open one transaction per use-case step."""

import logging
from collections.abc import Iterator
from contextlib import contextmanager

import psycopg
from psycopg_pool import ConnectionPool

logger = logging.getLogger(__name__)


class Database:
    def __init__(self, url: str, *, min_size: int = 1, max_size: int = 10) -> None:
        self.pool = ConnectionPool(url, min_size=min_size, max_size=max_size, open=False, name="roomly")

    def open(self, timeout: float = 10.0) -> None:
        self.pool.open(wait=True, timeout=timeout)
        logger.info("database pool open (max %d connections)", self.pool.max_size)

    def close(self) -> None:
        self.pool.close()
        logger.info("database pool closed")

    @contextmanager
    def transaction(self) -> Iterator[psycopg.Connection]:
        """Commit when the block exits normally, roll back when it raises."""
        with self.pool.connection() as conn:
            yield conn
