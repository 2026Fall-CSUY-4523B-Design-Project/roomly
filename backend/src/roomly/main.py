"""Roomly API entrypoint. Run: script/backend.sh [dev|prod]"""

import logging
import os

from fastapi_reborn import FastAPI

from roomly.config import Settings

app = FastAPI(title="Roomly API", version="0.1.0")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


def main() -> None:
    settings = Settings.from_env(os.environ)
    logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("roomly").info("starting env=%s on %s:%s", settings.env, settings.host, settings.port)
    app.run(host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()
