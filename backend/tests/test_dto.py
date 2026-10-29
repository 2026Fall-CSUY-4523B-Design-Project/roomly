"""DTO validation: the 422 contract every controller relies on (no database)."""

import datetime as dt
import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel, ValidationError

from roomly.config import Settings
from roomly.dto.account import SignUpRequest
from roomly.dto.comparison import SaveComparisonRequest
from roomly.dto.listing import ManualListingRequest
from roomly.dto.notification import NotificationSettingsDTO
from roomly.dto.room import CreatePollRequest, PostMessageRequest
from roomly.dto.search import CommuteDestinationRequest, SearchCriteria
from roomly.main import create_app

pytestmark = pytest.mark.unit


def errors(cls: type[BaseModel], data: object) -> list[dict[str, Any]]:
    with pytest.raises(ValidationError) as info:
        cls.model_validate(data)
    return info.value.errors(include_url=False)


def test_valid_body_is_normalized() -> None:
    req = SignUpRequest.model_validate({"email": "  Ann@Example.COM ", "password": "  spaced pw  "})
    assert req.email == "ann@example.com"
    assert req.password == "  spaced pw  "  # secrets are never stripped
    assert req.display_name is None


def test_every_problem_is_reported_at_once() -> None:
    errs = errors(SignUpRequest, {"email": "not-an-email", "password": "short", "display_name": 7})
    assert {e["loc"] for e in errs} == {("email",), ("password",), ("display_name",)}
    assert all({"type", "loc", "msg", "input"} <= e.keys() for e in errs)


def test_missing_and_wrong_shape() -> None:
    assert errors(SignUpRequest, {})[0]["type"] == "missing"
    assert errors(SignUpRequest, [])[0]["type"] == "model_type"


def test_numbers_and_booleans_are_strict() -> None:
    errs = errors(ManualListingRequest, {"address_line": "1 A St", "bedrooms": True, "area_sqft": "700",
                                         "bathrooms": "1.5"})
    assert {(e["loc"][0], e["type"]) for e in errs} == {
        ("bedrooms", "int_type"), ("area_sqft", "int_type"), ("bathrooms", "float_type")}
    assert errors(NotificationSettingsDTO, {"email": 1})[0]["type"] == "bool_type"
    whole = ManualListingRequest.model_validate({"address_line": "1 A St", "latitude": 40, "longitude": -74})
    assert whole.latitude == 40.0   # an integer is a valid float


def test_patterns_match_the_whole_value() -> None:
    listing = {"address_line": "1 A St"}
    assert errors(ManualListingRequest, {**listing, "postal_code": "x112371"})[0]["loc"] == ("postal_code",)
    assert errors(ManualListingRequest, {**listing, "original_url": "see https://x.com"})[0]["loc"] == ("original_url",)
    assert ManualListingRequest.model_validate({**listing, "postal_code": " 11237 "}).postal_code == "11237"


def test_list_rules_and_uuid_parsing() -> None:
    same = str(uuid.uuid4())
    errs = errors(SaveComparisonRequest, {"listing_ids": [same, same]})
    assert [e["type"] for e in errs] == ["unique_items"]
    assert [e["type"] for e in errors(SaveComparisonRequest, {"listing_ids": ["nope", same]})] == ["uuid_parsing"]
    errs = errors(SaveComparisonRequest, {"listing_ids": [str(uuid.uuid4()) for _ in range(5)]})
    assert [e["type"] for e in errs] == ["too_long"]


def test_dates_literals_and_cross_field_checks() -> None:
    c = SearchCriteria.model_validate({"move_in_from": "2026-11-01", "boroughs": ["queens"]})
    assert c.move_in_from == dt.date(2026, 11, 1)
    assert errors(SearchCriteria, {"boroughs": ["jersey_city"]})[0]["type"] == "literal_error"
    errs = errors(SearchCriteria, {"min_rent_cents": 500, "max_rent_cents": 100, "south": 40.0})
    assert {(e["type"], e["loc"][-1]) for e in errs} == {("value_error", "max_rent_cents"), ("value_error", "south")}
    assert errors(CommuteDestinationRequest, {"label": "Work"})[0]["loc"] == ("address",)


def test_message_belongs_to_one_thread_and_polls_need_2_to_4_options() -> None:
    both = {"body": "hi", "listing_id": str(uuid.uuid4()), "comparison_id": str(uuid.uuid4())}
    errs = errors(PostMessageRequest, both)
    assert errs[0]["loc"] == ("comparison_id",) and errs[0]["type"] == "value_error"
    assert errors(CreatePollRequest, {"question": "Which?", "options": ["A"]})[0]["type"] == "too_short"
    errs = errors(CreatePollRequest, {"question": "Which?", "options": ["A", "  "]})
    assert (errs[0]["type"], errs[0]["loc"]) == ("string_too_short", ("options", 1))


def test_schema_mirrors_the_dto() -> None:
    s = SignUpRequest.model_json_schema()
    assert s["required"] == ["email", "password"]
    assert s["properties"]["password"] == {"type": "string", "minLength": 8, "maxLength": 128, "title": "Password"}
    assert SaveComparisonRequest.model_json_schema()["properties"]["listing_ids"]["maxItems"] == 4


def test_http_422_locates_errors_in_body_path_and_query() -> None:
    client = TestClient(create_app(Settings.from_env({})))
    auth = {"authorization": "Bearer any-token"}
    detail = client.post("/listings", json={"address_line": "1 A St", "bedrooms": True}, headers=auth).json()["detail"]
    assert [(e["type"], e["loc"]) for e in detail] == [("int_type", ["body", "bedrooms"])]
    assert set(detail[0]) >= {"type", "loc", "msg", "input"}

    detail = client.get("/search", params={"min_rent_cents": 500, "max_rent_cents": 100}).json()["detail"]
    assert [(e["type"], e["loc"]) for e in detail] == [("value_error", ["query", "max_rent_cents"])]
    detail = client.get("/search", params={"limit": 0, "sort": "cheapest"}).json()["detail"]
    assert {e["loc"][-1] for e in detail} == {"limit", "sort"}

    resp = client.get("/groups/not-a-uuid", headers=auth)
    assert resp.status_code == 422 and resp.json()["detail"][0]["loc"] == ["path", "group_id"]


def test_openapi_documents_bodies_responses_and_bearer_auth() -> None:
    doc = TestClient(create_app(Settings.from_env({}))).get("/openapi.json").json()
    assert doc["components"]["securitySchemes"]["bearerAuth"] == {"type": "http", "scheme": "bearer"}
    create = doc["paths"]["/groups"]["post"]
    assert create["security"] == [{"bearerAuth": []}]
    schema = create["requestBody"]["content"]["application/json"]["schema"]
    assert schema == {"$ref": "#/components/schemas/CreateGroupRequest"}
    assert "201" in create["responses"] and "422" in create["responses"]
    assert "security" not in doc["paths"]["/search"]["get"]
