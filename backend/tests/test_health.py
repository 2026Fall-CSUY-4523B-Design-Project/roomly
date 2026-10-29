import asyncio
import json

from fastapi_reborn.http.requests import Request

from roomly.main import app


def test_health() -> None:
    resp = asyncio.run(app.handle(Request("GET", "/health")))
    assert resp.status_code == 200
    assert json.loads(resp.body)["status"] == "ok"
