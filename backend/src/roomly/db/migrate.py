"""Apply db/migrations/NNNN_*.sql in order, once each, recorded in schema_migration.

Each file runs in its own transaction under an advisory lock, so two backends starting at
the same time cannot apply the same migration twice. Run: ``script/backend.sh migrate``.
"""

import logging
import os
import re
import sys
from pathlib import Path

import psycopg

from roomly.config import Settings

logger = logging.getLogger(__name__)

_FILE = re.compile(r"^(\d{4})_[a-z0-9_]+\.sql$")
_LOCK_KEY = 4523_2026  # arbitrary, constant across processes


def pending_files(migrations_dir: Path) -> list[tuple[str, Path]]:
    files = []
    for path in sorted(migrations_dir.iterdir()):
        if path.suffix == ".sql":
            if not _FILE.match(path.name):
                raise ValueError(f"migration file name must look like 0001_name.sql: {path.name}")
            files.append((path.stem, path))
    return files


def migrate(database_url: str, migrations_dir: Path) -> list[str]:
    """Apply every migration not yet recorded. Returns the versions applied now."""
    if not migrations_dir.is_dir():
        raise FileNotFoundError(f"migrations directory not found: {migrations_dir} (set ROOMLY_MIGRATIONS_DIR)")
    applied_now: list[str] = []
    with psycopg.connect(database_url, autocommit=True) as conn:
        conn.execute("SELECT pg_advisory_lock(%s)", (_LOCK_KEY,))
        try:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS schema_migration ("
                " version text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())"
            )
            done = {row[0] for row in conn.execute("SELECT version FROM schema_migration")}
            for version, path in pending_files(migrations_dir):
                if version in done:
                    continue
                with conn.transaction():
                    conn.execute(path.read_text(encoding="utf-8"))  # no params: multi-statement is allowed
                    conn.execute("INSERT INTO schema_migration (version) VALUES (%s)", (version,))
                logger.info("applied migration %s", version)
                applied_now.append(version)
        finally:
            conn.execute("SELECT pg_advisory_unlock(%s)", (_LOCK_KEY,))
    if not applied_now:
        logger.info("schema up to date")
    return applied_now


def main() -> None:
    settings = Settings.from_env(os.environ)
    logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    try:
        migrate(settings.database_url, settings.migrations_dir)
    except (psycopg.Error, OSError, ValueError) as exc:
        logger.error("migration failed: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
