"""Roomly API entrypoint. Run: script/backend.sh [dev|prod]

Layers (SSDS §7, §9.1): controller (HTTP) -> service (use-case rules, transactions)
-> mapper (SQL) -> PostgreSQL. DTOs cross the HTTP boundary; entities cross the SQL one.
"""

import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi_reborn import FastAPI

from roomly.config import Settings
from roomly.controller import ROUTERS
from roomly.controller.errors import install_error_handlers
from roomly.db import Database, migrate
from roomly.service import Services

logger = logging.getLogger("roomly")

VERSION = "0.2.0"


def create_app(settings: Settings | None = None, database: Database | None = None) -> FastAPI:
    """Build the app. The pool opens in the lifespan (when serving); tests open it themselves."""
    settings = settings or Settings.from_env(os.environ)
    database = database or Database(settings.database_url)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        database.open()
        try:
            yield
        finally:
            database.close()

    app = FastAPI(
        title="Roomly API",
        version=VERSION,
        description="Group apartment search for NYC renters (SSDS-001).",
        lifespan=lifespan,
        security_schemes={"bearerAuth": {"type": "http", "scheme": "bearer"}},
    )
    app.state.settings = settings
    app.state.database = database
    app.state.services = Services.build(database, settings)
    install_error_handlers(app)
    for router in ROUTERS:
        app.include_router(router)

    @app.get("/health", tags=["ops"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()


def main() -> None:
    settings = Settings.from_env(os.environ)
    logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    migrate(settings.database_url, settings.migrations_dir)
    logger.info("starting env=%s on %s:%s", settings.env, settings.host, settings.port)
    app.run(host=settings.host, port=settings.port, log_level=settings.log_level)


if __name__ == "__main__":
    main()
