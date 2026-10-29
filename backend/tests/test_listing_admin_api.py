"""Listing Submission and Listing Administration (§8.1.2.3-4, R-2) through the HTTP API."""

import pytest

from conftest import Api

pytestmark = pytest.mark.integration


def test_manual_listing_card_has_provenance_and_unknowns(api: Api) -> None:
    token, user = api.user()
    card = api.listing(token, address_line="  77   Grand St ", area_sqft=..., bathrooms=..., amenities=["Laundry ", "laundry", "Elevator"],
                       original_url="https://example.com/77-grand")
    assert card["status"] == "searchable"
    assert card["address_line"] == "77 Grand St"
    assert card["amenities"] == ["elevator", "laundry"]
    assert {"area_sqft", "bathrooms", "broker_fee_cents"} <= set(card["unknown"])
    assert card["price_per_sqft_cents"] == {"value": None, "formula": "advertised monthly rent ÷ area in sq ft"}
    [source] = card["sources"]
    assert source["source_name"] == "Manual entry"
    assert source["original_url"] == "https://example.com/77-grand"
    assert source["collected_at"]
    assert [p["rent_cents"] for p in card["price_history"]] == [300_000]

    guest = api.get(f"/listings/{card['id']}")   # guests can view cards
    assert guest.status == 200
    assert guest.json["id"] == card["id"]
    assert user["id"] not in str(guest.json)       # the submitter is never exposed


def test_price_per_sqft_shows_its_formula(api: Api) -> None:
    token, _ = api.user()
    card = api.listing(token, advertised_rent_cents=350_000, area_sqft=700)
    assert card["price_per_sqft_cents"]["value"] == 500


def test_out_of_scope_listings_are_stored_but_not_searchable(api: Api) -> None:
    token, _ = api.user()
    short = api.listing(token, min_lease_days=14)
    nowhere = api.listing(token, borough=None)
    assert short["status"] == nowhere["status"] == "excluded"
    ids = {x["id"] for x in api.get("/search").json["items"]}
    assert short["id"] not in ids and nowhere["id"] not in ids


def test_manual_entry_needs_sign_in_and_valid_values(api: Api) -> None:
    assert api.post("/listings", {"address_line": "1 A St"}).status == 401
    token, _ = api.user()
    r = api.post("/listings", {"address_line": "1 A St", "area_sqft": 0, "latitude": 40.7}, token)
    assert r.status == 422
    assert {e["loc"][-1] for e in r.json["detail"]} == {"area_sqft"}
    r = api.post("/listings", {"address_line": "1 A St", "latitude": 40.7}, token)
    assert [e["loc"][-1] for e in r.json["detail"]] == ["longitude"]


def _possible_duplicate(api: Api) -> tuple[str, dict, dict, dict]:
    admin, _ = api.user(admin=True)
    token, _ = api.user()
    first = api.listing(token, address_line="10 Kent Ave", unit="4B")
    second = api.listing(token, address_line="10 kent ave", unit="4b", advertised_rent_cents=310_000)
    queue = api.get("/admin/duplicates", admin).json
    assert queue["total"] == 1
    return admin, first, second, queue["items"][0]


def test_same_unit_goes_to_review_instead_of_merging(api: Api) -> None:
    _, first, second, candidate = _possible_duplicate(api)
    assert second["status"] == "under_review"
    assert candidate["a"]["listing"]["id"] == first["id"]
    assert candidate["b"]["listing"]["id"] == second["id"]
    assert candidate["confidence"] == pytest.approx(0.8)
    ids = {x["id"] for x in api.get("/search").json["items"]}
    assert first["id"] in ids and second["id"] not in ids


def test_merge_then_split(api: Api) -> None:
    admin, first, second, candidate = _possible_duplicate(api)
    merged = api.post(f"/admin/duplicates/{candidate['id']}/merge", token=admin)
    assert merged.status == 200
    assert merged.json["b"]["listing_status"] == "merged"
    card = api.get(f"/listings/{first['id']}").json
    assert len(card["sources"]) == 2                      # the surviving card keeps both original links
    assert api.get(f"/listings/{second['id']}").json["merged_into_id"] == first["id"]
    assert api.post(f"/admin/duplicates/{candidate['id']}/merge", token=admin).status == 409

    split = api.post(f"/admin/duplicates/{candidate['id']}/split", token=admin)
    assert split.status == 200
    assert split.json["status"] == "separate"
    assert split.json["b"]["listing_status"] == "searchable"
    assert len(api.get(f"/listings/{first['id']}").json["sources"]) == 1


def test_keep_separate_releases_the_held_listing(api: Api) -> None:
    admin, _, second, candidate = _possible_duplicate(api)
    r = api.post(f"/admin/duplicates/{candidate['id']}/keep-separate", token=admin)
    assert r.json["status"] == "separate"
    assert api.get(f"/listings/{second['id']}").json["status"] == "searchable"
    assert api.get("/admin/duplicates", admin).json["total"] == 0


def test_admin_routes_are_admin_only(api: Api) -> None:
    token, _ = api.user()
    for path in ("/admin/sources", "/admin/duplicates", "/admin/reports"):
        assert api.get(path, token).status == 403
        assert api.get(path).status == 401


def test_sources_crud(api: Api) -> None:
    admin, _ = api.user(admin=True)
    created = api.post("/admin/sources", {"name": "SampleFeed", "config": {"fixture": "feeds/sample.json"}}, admin)
    assert created.status == 201
    assert created.json["kind"] == "feed" and created.json["is_synthetic"] is True
    assert api.post("/admin/sources", {"name": "SampleFeed"}, admin).status == 409
    off = api.patch(f"/admin/sources/{created.json['id']}", {"enabled": False}, admin)
    assert off.json["enabled"] is False
    assert off.json["config"] == {"fixture": "feeds/sample.json"}   # absent fields are untouched
    assert [s["name"] for s in api.get("/admin/sources", admin).json] == ["SampleFeed"]


def test_disabled_manual_channel_refuses_submissions(api: Api) -> None:
    admin, _ = api.user(admin=True)
    token, _ = api.user()
    api.listing(token)  # creates the manual source
    manual = next(s for s in api.get("/admin/sources", admin).json if s["kind"] == "manual")
    api.patch(f"/admin/sources/{manual['id']}", {"enabled": False}, admin)
    assert api.post("/listings", {"address_line": "1 A St"}, token).status == 403


def test_reports_flow(api: Api) -> None:
    admin, _ = api.user(admin=True)
    token, _ = api.user()
    listing = api.listing(token)
    report = api.post(f"/listings/{listing['id']}/reports", {"reason": "wrong_value", "details": "rent is $2,900"}, token)
    assert report.status == 201
    assert api.get("/admin/reports", admin).json["total"] == 1
    done = api.post(f"/admin/reports/{report.json['id']}/resolve", {"status": "resolved"}, admin)
    assert done.json["status"] == "resolved"
    assert api.post(f"/admin/reports/{report.json['id']}/resolve", {"status": "dismissed"}, admin).status == 404
    assert api.get("/admin/reports?status=resolved", admin).json["total"] == 1
    assert api.get("/admin/reports?status=bogus", admin).status == 422
