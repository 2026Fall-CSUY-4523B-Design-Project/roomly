"""Roomly API entrypoint. Run: uv run python -m roomly.main"""

import logging
import os

from fastapi_reborn import FastAPI

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("roomly")

app = FastAPI(title="Roomly API", version="0.1.0")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


if __name__ == "__main__":
    host = os.environ.get("ROOMLY_HOST", "127.0.0.1")
    port = int(os.environ.get("ROOMLY_PORT", "8000"))
    log.info("starting on %s:%s", host, port)
    app.run(host=host, port=port)
