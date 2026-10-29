"""Search (§8.1.2.5, R-3.1, R-3.2), saved searches and commute destinations through the HTTP API."""

import pytest

from conftest import Api

pytestmark = pytest.mark.integration


def ids(r) -> set[str]:  # type: ignore[no-untyped-def]
    return {x["id"] for x in r.json["items"]}


def test_hard_constraints_and_unknown_values(api: Api) -> None:
    token, _ = api.user()
    cheap = api.listing(token, advertised_rent_cents=250_000, bedrooms=1)
    pricey = api.listing(token, advertised_rent_cents=420_000, bedrooms=3, borough="manhattan")
    unknown_rent = api.listing(token, advertised_rent_cents=..., bedrooms=...)

    assert ids(api.get("/search")) == {cheap["id"], pricey["id"], unknown_rent["id"]}
    assert ids(api.get("/search?max_rent_cents=300000")) == {cheap["id"]}           # Unknown rent fails
    assert ids(api.get("/search?min_bedrooms=2")) == {pricey["id"]}                  # Unknown bedrooms fail
    assert ids(api.get("/search?borough=manhattan&borough=queens")) == {pricey["id"]}
    assert api.get("/search?borough=hoboken").status == 422


def test_amenities_dates_fees_and_viewport(api: Api) -> None:
    token, _ = api.user()
    a = api.listing(token, amenities=["Laundry", "Elevator"], move_in_date="2026-11-15", broker_fee_cents=0)
    b = api.listing(token, amenities=["laundry"], move_in_date="2027-01-10", broker_fee_cents=...,
                    latitude=..., longitude=...)
    assert ids(api.get("/search?amenity=elevator&amenity=LAUNDRY")) == {a["id"]}
    assert ids(api.get("/search?move_in_to=2026-12-31")) == {a["id"]}
    assert ids(api.get("/search?no_broker_fee=true")) == {a["id"]}                    # Unknown fee fails
    box = "south=40.6&west=-74.1&north=40.8&east=-73.8"
    assert ids(api.get(f"/search?{box}")) == {a["id"]}                                # no coordinates: list only
    assert api.get("/search?south=40.6").status == 422
    assert api.get("/search?move_in_from=next-week").status == 422


def test_sorting_and_paging(api: Api) -> None:
    token, _ = api.user()
    rents = [330_000, 210_000, 450_000]
    for rent in rents:
        api.listing(token, advertised_rent_cents=rent)
    asc = api.get("/search?sort=rent_asc&limit=2").json
    assert [x["advertised_rent_cents"] for x in asc["items"]] == [210_000, 330_000]
    assert asc["total"] == 3
    page2 = api.get("/search?sort=rent_asc&limit=2&offset=2").json
    assert [x["advertised_rent_cents"] for x in page2["items"]] == [450_000]
    assert api.get("/search?sort=best").status == 422
    assert api.get("/search?limit=1000").status == 422


def test_saved_search_round_trip(api: Api) -> None:
    token, _ = api.user()
    other, _ = api.user()
    match = api.listing(token, advertised_rent_cents=200_000, move_in_date="2026-11-20")
    api.listing(token, advertised_rent_cents=500_000)
    saved = api.post("/saved-searches", {"name": "Under 2.5k", "criteria": {"max_rent_cents": 250_000,
                                         "move_in_to": "2026-12-01"}, "weights": {"rent": 0.7}}, token)
    assert saved.status == 201
    assert saved.json["criteria"]["move_in_to"] == "2026-12-01"
    assert [s["name"] for s in api.get("/saved-searches", token).json] == ["Under 2.5k"]
    results = api.get(f"/saved-searches/{saved.json['id']}/results", token)
    assert ids(results) == {match["id"]}
    assert api.get(f"/saved-searches/{saved.json['id']}/results", other).status == 404
    assert api.delete(f"/saved-searches/{saved.json['id']}", token=other).status == 404
    assert api.delete(f"/saved-searches/{saved.json['id']}", token=token).status == 204


def test_at_most_three_commute_destinations(api: Api) -> None:
    token, _ = api.user()
    for label in ("NYU Tandon", "Work", "Gym"):
        assert api.post("/me/commute-destinations", {"label": label, "address": "x", "mode": "transit"}, token).status == 201
    fourth = api.post("/me/commute-destinations", {"label": "Fourth", "latitude": 40.7, "longitude": -74.0}, token)
    assert fourth.status == 409
    listed = api.get("/me/commute-destinations", token).json
    assert [d["label"] for d in listed] == ["NYU Tandon", "Work", "Gym"]
    assert api.delete(f"/me/commute-destinations/{listed[0]['id']}", token=token).status == 204
    assert api.post("/me/commute-destinations", {"label": "Only coords"}, token).status == 422
