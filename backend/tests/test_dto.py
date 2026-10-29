"""DTO validation: the 422 contract every controller relies on (no database)."""

import datetime as dt
import uuid

import pytest
from fastapi_reborn.params import RequestValidationError

from roomly.dto.account import SignUpRequest
from roomly.dto.base import parse, schema_of
from roomly.dto.comparison import SaveComparisonRequest
from roomly.dto.listing import ManualListingRequest
from roomly.dto.room import CreatePollRequest, PostMessageRequest
from roomly.dto.search import SearchCriteria

pytestmark = pytest.mark.unit


def errors(cls: type, data: object) -> list[dict]:
    with pytest.raises(RequestValidationError) as info:
        parse(cls, data)
    return info.value.errors


def test_valid_body_is_normalized() -> None:
    req = parse(SignUpRequest, {"email": "  Ann@Example.COM ", "password": "  spaced pw  "})
    assert req.email == "ann@example.com"
    assert req.password == "  spaced pw  "  # secrets are never stripped
    assert req.display_name is None


def test_every_problem_is_reported_at_once() -> None:
    errs = errors(SignUpRequest, {"email": "not-an-email", "password": "short", "display_name": 7})
    assert {tuple(e["loc"]) for e in errs} == {("body", "email"), ("body", "password"), ("body", "display_name")}
    assert all({"type", "loc", "msg", "input"} <= e.keys() for e in errs)


def test_missing_and_wrong_shape() -> None:
    assert errors(SignUpRequest, {})[0]["type"] == "missing"
    assert errors(SignUpRequest, [])[0]["type"] == "dict_type"


def test_booleans_are_not_integers() -> None:
    errs = errors(ManualListingRequest, {"address_line": "1 A St", "bedrooms": True})
    assert errs[0]["loc"] == ["body", "bedrooms"]


def test_list_rules_and_uuid_parsing() -> None:
    same = str(uuid.uuid4())
    errs = errors(SaveComparisonRequest, {"listing_ids": [same, same]})
    assert [e["type"] for e in errs] == ["unique_items"]
    errs = errors(SaveComparisonRequest, {"listing_ids": ["nope", str(uuid.uuid4()), str(uuid.uuid4()),
                                                          str(uuid.uuid4()), str(uuid.uuid4())]})
    assert {e["type"] for e in errs} == {"uuid_parsing", "too_long"}


def test_dates_literals_and_cross_field_checks() -> None:
    c = parse(SearchCriteria, {"move_in_from": "2026-11-01", "boroughs": ["queens"]})
    assert c.move_in_from == dt.date(2026, 11, 1)
    assert errors(SearchCriteria, {"boroughs": ["jersey_city"]})[0]["type"] == "literal_error"
    errs = errors(SearchCriteria, {"min_rent_cents": 500, "max_rent_cents": 100, "south": 40.0})
    assert {(e["type"], e["loc"][-1]) for e in errs} == {("value_error", "max_rent_cents"), ("value_error", "south")}


def test_message_belongs_to_one_thread_and_polls_need_2_to_4_options() -> None:
    errs = errors(PostMessageRequest, {"body": "hi", "listing_id": str(uuid.uuid4()), "comparison_id": str(uuid.uuid4())})
    assert errs[0]["loc"] == ["body", "comparison_id"]
    assert errors(CreatePollRequest, {"question": "Which?", "options": ["A"]})[0]["type"] == "too_short"
    assert errors(CreatePollRequest, {"question": "Which?", "options": ["A", "  "]})[0]["type"] == "value_error"


def test_schema_mirrors_the_dto() -> None:
    s = schema_of(SignUpRequest)
    assert s["required"] == ["email", "password"]
    assert s["properties"]["password"] == {"type": "string", "minLength": 8, "maxLength": 128}
    assert schema_of(SaveComparisonRequest)["properties"]["listing_ids"]["maxItems"] == 4
