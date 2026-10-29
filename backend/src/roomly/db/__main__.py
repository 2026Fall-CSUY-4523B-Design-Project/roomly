"""``python -m roomly.db``: apply pending migrations to the configured database (or its fallback)."""

import logging
import os
import sys

from roomly.config import Settings
from roomly.db.backend import UnavailableError
from roomly.db.database import Database

logger = logging.getLogger("roomly.db")


def main() -> None:
    settings = Settings.from_env(os.environ)
    logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    db = Database(settings.database_url, fallback=settings.sqlite_fallback)
    try:
        db.open()
        db.migrate(settings.migrations_dir)
    except (*UnavailableError, OSError, ValueError) as exc:
        logger.error("migration failed: %s", exc)
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
