"""Fixture mode: stub service methods answer with roomly.fixtures samples instead of 501."""

import asyncio
import dataclasses
import json
import typing
from typing import Any

import pytest
from fastapi_reborn import FastAPI
from fastapi_reborn.http.requests import Request
from fastapi_reborn.routing import Route

from roomly import fixtures
from roomly.config import Settings
from roomly.dto.common import Page
from roomly.main import create_app

pytestmark = pytest.mark.unit

NOT_STUBBED = {"/openapi.json", "/docs", "/health"}


def call(app: FastAPI, method: str, path: str, body: Any = None, token: str | None = "any-token",
         query: str = "") -> tuple[int, Any, dict[str, str]]:
    headers = [("host", "test")]
    raw = b""
    if body is not None:
        raw = json.dumps(body).encode()
        headers += [("content-type", "application/json"), ("content-length", str(len(raw)))]
    if token:
        headers.append(("authorization", f"Bearer {token}"))
    r = asyncio.run(app.handle(Request(method, path, query_string=query, headers=headers, body=raw)))
    return r.status_code, json.loads(r.body) if r.body else None, {k.lower(): v for k, v in r.headers.items()}


def routes(app: FastAPI) -> list[Route]:
    found: list[Route] = []

    def walk(router: Any) -> None:
        for r in getattr(router, "routes", []):
            if isinstance(r, Route):
                found.append(r)
            else:
                walk(r)

    walk(app.router)
    return [r for r in found if r.path not in NOT_STUBBED]


def matches(value: Any, tp: Any) -> bool:
    """Shallow check of a sample against an endpoint's return annotation."""
    origin, args = typing.get_origin(tp), typing.get_args(tp)
    if origin is list:
        return isinstance(value, list) and all(matches(v, args[0]) for v in value)
    if origin is dict:
        return isinstance(value, dict)
    if origin is not None and dataclasses.is_dataclass(origin):   # Page[ListingSummaryDTO]
        return isinstance(value, origin) and all(matches(v, args[0]) for v in value.items)
    return isinstance(value, tp)


@pytest.fixture(scope="module")
def app() -> FastAPI:
    return create_app(Settings.from_env({}))   # dev: fixtures on


def test_every_route_with_a_body_has_a_sample_of_its_declared_type(app: FastAPI) -> None:
    for route in routes(app):
        for method in route.methods:
            key = f"{method} {route.path}"
            ret = typing.get_type_hints(route.endpoint)["return"]
            if route.status_code == 204:
                assert key not in fixtures.FIXTURES, key
                continue
            assert key in fixtures.FIXTURES, f"no sample for {key}"
            assert matches(fixtures.FIXTURES[key], ret), f"{key}: sample is not a {ret}"


def test_samples_are_served_with_the_route_status_and_marked(app: FastAPI) -> None:
    status, groups, headers = call(app, "GET", "/groups")
    assert status == 200 and headers["x-roomly-fixture"] == "1"
    status, group, _ = call(app, "GET", f"/groups/{groups[0]['id']}")
    assert status == 200 and group["id"] == groups[0]["id"]

    status, session, _ = call(app, "POST", "/auth/sign-up", {"email": "new@example.com", "password": "longenough"},
                              token=None)
    assert status == 201 and session["token"] and session["user"]["email"] == "maya@example.com"

    status, body, headers = call(app, "POST", f"/groups/{fixtures.CREW}/leave")
    assert status == 204 and body is None and headers["x-roomly-fixture"] == "1"

    status, page, _ = call(app, "GET", "/search", token=None, query="borough=brooklyn&borough=queens")
    assert status == 200 and page["total"] == len(page["items"]) == 3
    assert page["items"][1]["unknown"] == ["bathrooms", "area_sqft", "move_in_date"]


def test_requests_are_still_validated_and_authenticated(app: FastAPI) -> None:
    assert call(app, "POST", "/groups", {})[0] == 422
    assert call(app, "POST", "/auth/sign-up", {"email": "bad", "password": "x"}, token=None)[0] == 422
    assert call(app, "GET", "/search", token=None, query="sort=cheapest")[0] == 422
    assert call(app, "GET", "/groups/not-a-uuid")[0] == 422
    assert call(app, "GET", "/groups", token=None)[0] == 401


def test_with_fixtures_off_stubs_answer_501() -> None:
    app = create_app(Settings.from_env({"ROOMLY_FIXTURES": "off"}))
    assert call(app, "GET", "/groups")[:2] == (501, {"detail": "not implemented yet"})
    assert call(app, "POST", f"/groups/{fixtures.CREW}/leave")[0] == 501


def test_fixtures_default_on_in_dev_off_in_prod() -> None:
    assert Settings.from_env({}).fixtures is True
    assert Settings.from_env({"ROOMLY_ENV": "prod", "DATABASE_URL": "postgresql://db/x"}).fixtures is False
    assert Settings.from_env({"ROOMLY_FIXTURES": "on", "ROOMLY_ENV": "prod", "DATABASE_URL": "x"}).fixtures is True
    with pytest.raises(ValueError):
        Settings.from_env({"ROOMLY_FIXTURES": "maybe"})


def test_samples_reference_each_other_consistently() -> None:
    listing_ids = {x.id for x in fixtures.LISTINGS}
    assert set(fixtures.COMPARISON.listing_ids) == listing_ids
    assert {c.listing_id for row in fixtures.TABLE.rows for c in row.cells} == listing_ids
    assert {m.listing_id for m in fixtures.MESSAGES} - {None} <= listing_ids
    assert all(m.group_id == fixtures.CREW for m in fixtures.MESSAGES)
    assert fixtures.CARD.id in listing_ids
    assert {g.id for g in fixtures.GROUPS} == {fixtures.GROUP.id}
    assert fixtures.GROUPS[0].member_count == len(fixtures.GROUP.members)
    assert isinstance(fixtures.FIXTURES["GET /search"], Page)
