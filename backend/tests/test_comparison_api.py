"""Comparison use case (§8.1.2.6, R-4) through the HTTP API."""

import pytest

from conftest import Api

pytestmark = pytest.mark.integration


def row(table: dict, key: str) -> dict:
    return next(r for r in table["rows"] if r["key"] == key)


def test_preview_aligns_and_highlights_only_known_values(api: Api) -> None:
    token, _ = api.user()
    a = api.listing(token, advertised_rent_cents=300_000, area_sqft=600)
    b = api.listing(token, advertised_rent_cents=280_000, area_sqft=...)
    c = api.listing(token, advertised_rent_cents=320_000, area_sqft=800)
    r = api.post("/comparisons/preview", {"listing_ids": [a["id"], b["id"], c["id"]]})  # guests may compare
    assert r.status == 200
    table = r.json
    assert [x["id"] for x in table["listings"]] == [a["id"], b["id"], c["id"]]

    rent = row(table, "advertised_rent_cents")
    assert rent["direction"] == "lower"
    assert [cell["best"] for cell in rent["cells"]] == [False, True, False]

    ppsf = row(table, "price_per_sqft_cents")
    assert ppsf["formula"] == "advertised monthly rent ÷ area in sq ft"
    assert [cell["value"] for cell in ppsf["cells"]] == [500, None, 400]
    assert [cell["best"] for cell in ppsf["cells"]] == [False, False, True]   # Unknown never best
    assert ppsf["cells"][1]["known"] is False

    commute = row(table, "commute")
    assert all(not cell["known"] for cell in commute["cells"])
    assert table["notes"]


def test_no_highlight_without_two_known_values_or_on_ties(api: Api) -> None:
    token, _ = api.user()
    a = api.listing(token, broker_fee_cents=..., monthly_fees_cents=5_000)
    b = api.listing(token, broker_fee_cents=0, monthly_fees_cents=5_000)
    table = api.post("/comparisons/preview", {"listing_ids": [a["id"], b["id"]]}).json
    assert not any(c["best"] for c in row(table, "broker_fee_cents")["cells"])     # only one known
    assert not any(c["best"] for c in row(table, "monthly_fees_cents")["cells"])   # tie


def test_invalid_selections_are_explained(api: Api) -> None:
    token, _ = api.user()
    a = api.listing(token)
    excluded = api.listing(token, min_lease_days=7)
    one = api.post("/comparisons/preview", {"listing_ids": [a["id"]]})
    assert one.status == 422
    twice = api.post("/comparisons/preview", {"listing_ids": [a["id"], a["id"]]})
    assert twice.json["detail"][0]["type"] == "unique_items"
    ghost = api.post("/comparisons/preview", {"listing_ids": [a["id"], "00000000-0000-0000-0000-000000000000"]})
    assert ghost.status == 422 and "not found" in ghost.json["detail"]
    out = api.post("/comparisons/preview", {"listing_ids": [a["id"], excluded["id"]]})
    assert out.status == 422 and "excluded" in out.json["detail"]


def test_save_share_and_visibility(api: Api) -> None:
    owner, _ = api.user()
    member, _ = api.user()
    outsider, _ = api.user()
    group = api.group(owner, member)
    a, b = api.listing(owner), api.listing(owner)

    assert api.post("/comparisons", {"listing_ids": [a["id"], b["id"]]}).status == 401   # guests sign in to save
    personal = api.post("/comparisons", {"listing_ids": [a["id"], b["id"]], "title": "Shortlist"}, owner)
    assert personal.status == 201
    assert personal.json["group_id"] is None and personal.json["stale"] is False
    assert [c["title"] for c in api.get("/comparisons", owner).json] == ["Shortlist"]
    assert api.get(f"/comparisons/{personal.json['id']}", member).status == 404

    assert api.post(f"/comparisons/{personal.json['id']}/share", {"group_id": group}, member).status == 404
    shared = api.post(f"/comparisons/{personal.json['id']}/share", {"group_id": group}, owner)
    assert shared.status == 200 and shared.json["shared_at"]
    assert api.get(f"/comparisons/{personal.json['id']}", member).status == 200
    assert [c["id"] for c in api.get(f"/groups/{group}/comparisons", member).json] == [personal.json["id"]]
    assert api.get(f"/comparisons/{personal.json['id']}", outsider).status == 403
    assert api.post("/comparisons", {"listing_ids": [a["id"], b["id"]], "group_id": group}, outsider).status == 403


def test_saved_comparison_flags_changes_instead_of_replacing(api: Api) -> None:
    token, _ = api.user()
    a, b = api.listing(token), api.listing(token)
    saved = api.post("/comparisons", {"listing_ids": [a["id"], b["id"]]}, token).json
    with api.db.transaction() as tx:
        tx.exec("UPDATE listing SET advertised_rent_cents = 299000 WHERE id = %(id)s", {"id": a["id"]})
        tx.exec("UPDATE listing SET status = 'removed' WHERE id = %(id)s", {"id": b["id"]})
    got = api.get(f"/comparisons/{saved['id']}", token).json
    assert got["stale"] is True
    changes = {c["listing_id"]: c for c in got["changes"]}
    assert changes[a["id"]]["state"] == "changed"
    assert changes[a["id"]]["changed_fields"] == ["advertised_rent_cents"]
    assert changes[b["id"]]["state"] == "removed"
    assert got["listing_ids"] == [a["id"], b["id"]]   # never swapped for other listings
