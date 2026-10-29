"""Apply db/migrations/<dialect>/NNNN_*.sql in order, once each, recorded in schema_migration.

postgres/ and sqlite/ hold the same schema in each engine's dialect and keep the same
version numbers. Each file runs in its own transaction; on Postgres under an advisory lock,
on SQLite under BEGIN IMMEDIATE, so two backends starting together cannot apply one twice.
Run: ``script/backend.sh migrate``.
"""

import logging
import re
from contextlib import closing
from pathlib import Path

import psycopg

from roomly.db.backend import PostgresBackend, SqliteBackend

logger = logging.getLogger(__name__)

_FILE = re.compile(r"^(\d{4})_[a-z0-9_]+\.sql$")
_LOCK_KEY = 4523_2026  # arbitrary, constant across processes


def migration_files(directory: Path) -> list[tuple[str, Path]]:
    if not directory.is_dir():
        raise FileNotFoundError(f"migrations directory not found: {directory} (set ROOMLY_MIGRATIONS_DIR)")
    files = []
    for path in sorted(directory.iterdir()):
        if path.suffix == ".sql":
            if not _FILE.match(path.name):
                raise ValueError(f"migration file name must look like 0001_name.sql: {path.name}")
            files.append((path.stem, path))
    return files


def migrate_backend(backend: PostgresBackend | SqliteBackend, migrations_root: Path) -> list[str]:
    """Apply every migration not yet recorded. Returns the versions applied now."""
    files = migration_files(migrations_root / backend.dialect)
    if isinstance(backend, PostgresBackend):
        applied = _migrate_postgres(backend.url, files)
    else:
        applied = _migrate_sqlite(backend, files)
    for version in applied:
        logger.info("applied migration %s (%s)", version, backend.dialect)
    if not applied:
        logger.info("schema up to date (%s)", backend.dialect)
    return applied


def _migrate_postgres(url: str, files: list[tuple[str, Path]]) -> list[str]:
    applied: list[str] = []
    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute("SELECT pg_advisory_lock(%s)", (_LOCK_KEY,))
        try:
            conn.execute("CREATE TABLE IF NOT EXISTS schema_migration ("
                         " version text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())")
            done = {row[0] for row in conn.execute("SELECT version FROM schema_migration")}
            for version, path in files:
                if version in done:
                    continue
                with conn.transaction():
                    conn.execute(path.read_text(encoding="utf-8"))  # no params: multi-statement is allowed
                    conn.execute("INSERT INTO schema_migration (version) VALUES (%s)", (version,))
                applied.append(version)
        finally:
            conn.execute("SELECT pg_advisory_unlock(%s)", (_LOCK_KEY,))
    return applied


def _migrate_sqlite(backend: SqliteBackend, files: list[tuple[str, Path]]) -> list[str]:
    applied: list[str] = []
    with closing(backend.connect()) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS schema_migration ("
                     " version TEXT PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT (now()))")
        for version, path in files:
            if conn.execute("SELECT 1 FROM schema_migration WHERE version = ?", (version,)).fetchone():
                continue
            # version matched _FILE (digits, a-z, _), so it is safe to inline into the script
            script = (f"BEGIN IMMEDIATE;\n{path.read_text(encoding='utf-8')}\n"
                      f"INSERT INTO schema_migration (version) VALUES ('{version}');\nCOMMIT;")
            try:
                conn.executescript(script)
            except Exception:
                if conn.in_transaction:
                    conn.execute("ROLLBACK")
                raise
            applied.append(version)
    return applied
