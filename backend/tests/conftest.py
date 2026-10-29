"""Shared fixtures.

Every database test runs twice: on PostgreSQL (the primary) and on SQLite (the fallback).
Postgres uses a throwaway database (default ``roomly_test`` on the dev server from
``script/database.sh``; override with ROOMLY_TEST_DATABASE_URL), rebuilt from
db/migrations/postgres once per session; without a reachable server those runs are skipped
locally and fail in CI. SQLite uses a temporary file. Every table is emptied before each test.
"""

import os
from collections.abc import Iterator
from contextlib import closing

import psycopg
import pytest
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo

from roomly.config import Settings
from roomly.db import Database
from roomly.db.backend import SqliteBackend

TEST_DATABASE_URL = os.environ.get("ROOMLY_TEST_DATABASE_URL", "postgresql://roomly@127.0.0.1:5433/roomly_test")
MIGRATIONS = Settings.from_env({}).migrations_dir


def _fresh_postgres() -> str:
    dbname = conninfo_to_dict(TEST_DATABASE_URL)["dbname"]
    try:
        with psycopg.connect(make_conninfo(TEST_DATABASE_URL, dbname="postgres"), autocommit=True) as admin:
            if admin.execute("SELECT 1 FROM pg_database WHERE datname = %s", (dbname,)).fetchone() is None:
                admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(dbname)))
    except psycopg.OperationalError as exc:
        if os.environ.get("CI"):
            raise
        pytest.skip(f"Postgres not reachable for {TEST_DATABASE_URL} (start script/database.sh): {exc}")
    with psycopg.connect(TEST_DATABASE_URL, autocommit=True) as conn:
        conn.execute("DROP SCHEMA public CASCADE")
        conn.execute("CREATE SCHEMA public")
    return TEST_DATABASE_URL


@pytest.fixture(scope="session", params=["postgres", "sqlite"])
def database(request: pytest.FixtureRequest, tmp_path_factory: pytest.TempPathFactory) -> Iterator[Database]:
    if request.param == "postgres":
        db = Database(_fresh_postgres(), max_size=4)   # no fallback: a Postgres run must use Postgres
    else:
        db = Database(f"sqlite:///{tmp_path_factory.mktemp('sqlite') / 'roomly.sqlite3'}")
    db.open()
    assert db.dialect == request.param
    db.migrate(MIGRATIONS)
    yield db
    db.close()


@pytest.fixture
def db(database: Database) -> Database:
    """The database, with every table emptied first."""
    backend = database.backend
    if isinstance(backend, SqliteBackend):
        with closing(backend.connect()) as conn:
            conn.execute("PRAGMA foreign_keys = OFF")
            tables = [r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' "
                "AND name <> 'schema_migration'")]
            for table in tables:
                conn.execute(f'DELETE FROM "{table}"')
    else:
        with psycopg.connect(backend.url, autocommit=True) as conn:
            tables = [r[0] for r in conn.execute(
                "SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND tablename <> 'schema_migration'")]
            conn.execute(sql.SQL("TRUNCATE {} RESTART IDENTITY CASCADE").format(
                sql.SQL(", ").join(map(sql.Identifier, tables))))
    return database

