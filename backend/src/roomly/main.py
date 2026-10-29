"""Roomly API entrypoint. Run: script/backend.sh [dev|prod]

Layers (SSDS §7, §9.1): controller (HTTP) -> service (use-case rules, transactions)
-> mapper (SQL) -> PostgreSQL, or the SQLite fallback. DTOs cross the HTTP boundary; entities
cross the SQL one.
"""

import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from importlib.metadata import version

import uvicorn
from fastapi import FastAPI

from roomly.config import Settings
from roomly.controller import ROUTERS
from roomly.controller.errors import install_error_handlers
from roomly.db import Database
from roomly.service import Services

logger = logging.getLogger("roomly")

VERSION = version("roomly")   # backend/pyproject.toml, one number with the release tag


def create_app(settings: Settings | None = None, database: Database | None = None) -> FastAPI:
    """Build the app. The database opens (and migrates) in the lifespan when serving;
    tests open it themselves."""
    settings = settings or Settings.from_env(os.environ)
    database = database or Database(settings.database_url, fallback=settings.sqlite_fallback)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        database.open()   # Postgres, or the SQLite fallback if Postgres is unreachable
        database.migrate(settings.migrations_dir)
        try:
            yield
        finally:
            database.close()

    app = FastAPI(
        title="Roomly API",
        version=VERSION,
        description="Group apartment search for NYC renters (SSDS-001).",
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.database = database
    app.state.services = Services.build(database)
    install_error_handlers(app)
    for router in ROUTERS:
        app.include_router(router)

    @app.get("/health", tags=["ops"])
    async def health() -> dict[str, str | None]:
        """``database`` is "postgres", "sqlite" (fallback active) or null (not open)."""
        return {"status": "ok", "database": database.dialect}

    return app


app = create_app()


def main() -> None:
    settings = Settings.from_env(os.environ)
    logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logger.info("starting env=%s on %s:%s", settings.env, settings.host, settings.port)
    uvicorn.run(app, host=settings.host, port=settings.port, log_level=settings.log_level.lower())


if __name__ == "__main__":
    main()
