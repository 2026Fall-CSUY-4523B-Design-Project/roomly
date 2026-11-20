"""The service layer through HTTP, on both database engines.

Each test signs up real accounts and exercises the endpoints the way a client does; the
database invariants are covered separately by test_schema.
"""

import pytest
from fastapi.testclient import TestClient

from roomly.config import Settings
from roomly.main import create_app
from roomly.mapper.account_mapper import UserMapper
from roomly.mapper.listing_mapper import ListingMapper

pytestmark = pytest.mark.integration
PASSWORD = "correct horse battery"


@pytest.fixture
def client(db):
    return TestClient(create_app(Settings.from_env({}), database=db))


def account(client, email):
    response = client.post("/auth/sign-up", json={"email": email, "password": PASSWORD, "display_name": email[:6]})
    assert response.status_code == 201, response.text
    session = response.json()
    return {"Authorization": f"Bearer {session['token']}"}, session["user"]


def listing(client, headers, **overrides):
    body = {
        "address_line": "1 Test Street", "unit": "1A", "borough": "brooklyn", "postal_code": "11201",
        "advertised_rent_cents": 300_000, "bedrooms": 2, "bathrooms": 1.0, "area_sqft": 600,
        "min_lease_days": 365, "amenities": ["laundry_in_building"], "move_in_date": "2027-01-01",
    } | overrides
    response = client.post("/listings", json=body, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def group(client, owner, name="Crew"):
    response = client.post("/groups", json={"name": name}, headers=owner)
    assert response.status_code == 201, response.text
    return response.json()


def join(client, crew, owner_headers, member_headers, email):
    invitation = client.post(f"/groups/{crew['id']}/invitations", json={"email": email}, headers=owner_headers)
    assert invitation.status_code == 201, invitation.text
    joined = client.post(f"/invitations/{invitation.json()['id']}/accept", headers=member_headers)
    assert joined.status_code == 201, joined.text
    return joined.json()


def group_with(client, owner, other_headers, email):
    created = client.post("/groups", json={"name": "Crew"}, headers=owner)
    assert created.status_code == 201
    detail = created.json()
    invitation = client.post(f"/groups/{detail['id']}/invitations", json={"email": email}, headers=owner)
    joined = client.post(f"/invitations/{invitation.json()['id']}/accept", headers=other_headers)
    assert joined.status_code == 201, joined.text
    return detail


# --- groups ---------------------------------------------------------------------------


def test_group_invitation_lifecycle_and_ownership(client):
    owner_headers, owner = account(client, "owner@example.com")
    member_headers, member = account(client, "member@example.com")
    outsider_headers, _ = account(client, "outsider@example.com")

    created = client.post("/groups", json={"name": "Bushwick crew"}, headers=owner_headers)
    assert created.status_code == 201
    crew = created.json()
    assert (crew["my_role"], len(crew["members"])) == ("owner", 1)
    assert client.get(f"/groups/{crew['id']}", headers=outsider_headers).status_code == 403
    assert len(client.get("/groups", headers=owner_headers).json()) == 1
    assert client.get("/groups", headers=outsider_headers).json() == []

    invitation = client.post(f"/groups/{crew['id']}/invitations", json={"email": "member@example.com"},
                             headers=owner_headers)
    assert invitation.status_code == 201
    pending = invitation.json()
    assert pending["state"] == "pending"
    assert client.post(f"/groups/{crew['id']}/invitations", json={"email": "member@example.com"},
                       headers=owner_headers).status_code == 409
    assert client.get("/invitations", headers=member_headers).json()[0]["group_name"] == "Bushwick crew"

    joined = client.post(f"/invitations/{pending['id']}/accept", headers=member_headers)
    assert joined.status_code == 201
    assert joined.json()["my_role"] == "member"
    assert {m["user"]["name"] for m in joined.json()["members"]} == {"owner@", "member"}
    # Accepting again is idempotent; the membership is not duplicated.
    assert client.post(f"/invitations/{pending['id']}/accept", headers=member_headers).status_code == 201
    assert len(client.get(f"/groups/{crew['id']}", headers=owner_headers).json()["members"]) == 2

    # An owner cannot leave while others remain, and only the owner removes people.
    assert client.post(f"/groups/{crew['id']}/leave", headers=owner_headers).status_code == 409
    assert client.delete(f"/groups/{crew['id']}/members/{owner['id']}",
                         headers=member_headers).status_code == 403
    assert client.post(f"/groups/{crew['id']}/transfer", json={"user_id": member["id"]},
                       headers=owner_headers).status_code == 200
    assert client.get(f"/groups/{crew['id']}", headers=member_headers).json()["my_role"] == "owner"
    assert client.post(f"/groups/{crew['id']}/leave", headers=owner_headers).status_code == 204
    assert client.get(f"/groups/{crew['id']}", headers=owner_headers).status_code == 403

    # A sole owner leaving dissolves the group.
    assert client.post(f"/groups/{crew['id']}/leave", headers=member_headers).status_code == 204
    assert client.get(f"/groups/{crew['id']}", headers=member_headers).status_code == 404


def test_invitations_are_addressed_and_removable(client):
    owner_headers, owner = account(client, "owner@example.com")
    member_headers, member = account(client, "member@example.com")
    eve_headers, _ = account(client, "eve@example.com")
    crew = group(client, owner_headers)

    invitation = client.post(f"/groups/{crew['id']}/invitations", json={"email": "someone@example.com"},
                             headers=owner_headers).json()
    assert client.post(f"/invitations/{invitation['id']}/accept", headers=eve_headers).status_code == 404
    assert client.post(f"/invitations/{invitation['id']}/decline", headers=eve_headers).status_code == 404

    declined = client.post(f"/groups/{crew['id']}/invitations", json={"email": "member@example.com"},
                           headers=owner_headers).json()
    assert client.post(f"/invitations/{declined['id']}/decline", headers=member_headers).status_code == 204
    assert client.post(f"/invitations/{declined['id']}/accept", headers=member_headers).status_code == 409
    sent = client.get(f"/groups/{crew['id']}/invitations", headers=owner_headers).json()
    assert {row["state"] for row in sent} == {"pending", "declined"}

    join(client, crew, owner_headers, member_headers, "member@example.com")
    assert client.delete(f"/groups/{crew['id']}/members/{member['id']}", headers=owner_headers).status_code == 204
    assert client.get(f"/groups/{crew['id']}", headers=member_headers).status_code == 403
    assert client.delete(f"/groups/{crew['id']}/members/{owner['id']}", headers=owner_headers).status_code == 409


# --- listing cards, search and saved inputs -------------------------------------------


def test_manual_listing_card_search_and_saved_searches(client):
    headers, _ = account(client, "person@example.com")
    card = listing(client, headers)
    assert card["status"] == "searchable"
    assert card["price_per_sqft_cents"] == {"value": 500, "formula": "advertised monthly rent ÷ area in sq ft"}
    assert [s["source_name"] for s in card["sources"]] == ["Manual entry"]
    assert card["price_history"][0]["rent_cents"] == 300_000
    assert "broker_fee_cents" in card["unknown"]
    assert card["unknown"].count("coordinates") == 1

    listing(client, headers, address_line="2 Other Street", unit=None, borough="queens",
            advertised_rent_cents=450_000, bedrooms=1)

    found = client.get("/search", params={"borough": "brooklyn", "max_rent_cents": 350_000}).json()
    assert (found["total"], len(found["items"])) == (1, 1)
    assert found["items"][0]["id"] == card["id"]
    assert client.get("/search", params={"min_rent_cents": 900_000}).json()["total"] == 0
    assert client.get("/search", params={"amenity": "laundry_in_building"}).json()["total"] == 2
    assert client.get("/search", params={"no_broker_fee": "true"}).json()["total"] == 0

    saved = client.post("/saved-searches", json={
        "name": "Brooklyn under 3.5k",
        "criteria": {"boroughs": ["brooklyn"], "max_rent_cents": 350_000, "min_bedrooms": 2},
    }, headers=headers)
    assert saved.status_code == 201
    search_id = saved.json()["id"]
    assert [s["name"] for s in client.get("/saved-searches", headers=headers).json()] == ["Brooklyn under 3.5k"]
    rerun = client.get(f"/saved-searches/{search_id}/results", headers=headers).json()
    assert rerun["total"] == 1
    assert client.delete(f"/saved-searches/{search_id}", headers=headers).status_code == 204
    assert client.get(f"/saved-searches/{search_id}/results", headers=headers).status_code == 404

    for index in range(3):
        destination = client.post("/me/commute-destinations", json={"label": f"Place {index}", "address": "NYC"},
                                  headers=headers)
        assert destination.status_code == 201
    assert client.post("/me/commute-destinations", json={"label": "Fourth", "address": "NYC"},
                       headers=headers).status_code == 409
    destinations = client.get("/me/commute-destinations", headers=headers).json()
    assert len(destinations) == 3
    assert client.delete(f"/me/commute-destinations/{destinations[0]['id']}", headers=headers).status_code == 204
    assert len(client.get("/me/commute-destinations", headers=headers).json()) == 2


def test_duplicate_submission_and_admin_review(client, db):
    headers, _user = account(client, "person@example.com")
    original = listing(client, headers)
    duplicate = listing(client, headers, advertised_rent_cents=310_000, bathrooms=1.5)
    assert duplicate["status"] == "under_review"
    # A listing outside the search scope is stored but not searchable.
    assert listing(client, headers, address_line="3 Far Away", borough=None)["status"] == "excluded"

    assert client.get("/admin/duplicates", headers=headers).status_code == 403
    with db.transaction() as tx:
        UserMapper(tx).set_role("person@example.com", "admin")

    queue = client.get("/admin/duplicates", headers=headers).json()
    assert (queue["total"], queue["items"][0]["status"]) == (1, "queued")
    candidate = queue["items"][0]
    assert (candidate["a"]["listing_status"], candidate["b"]["listing_status"]) == ("searchable", "under_review")

    merged = client.post(f"/admin/duplicates/{candidate['id']}/merge", headers=headers)
    assert merged.status_code == 200 and merged.json()["status"] == "merged"
    survivor = client.get(f"/listings/{original['id']}").json()
    assert survivor["advertised_rent_cents"] == 300_000          # the survivor keeps its own value
    assert "advertised_rent_cents" in survivor["conflicts"]      # and records the disagreement
    assert len(survivor["sources"]) == 2                         # both source records are visible
    assert client.get(f"/listings/{duplicate['id']}").json()["status"] == "merged"

    restored = client.post(f"/admin/duplicates/{candidate['id']}/split", headers=headers)
    assert restored.status_code == 200 and restored.json()["status"] == "separate"
    assert client.get(f"/listings/{duplicate['id']}").json()["status"] == "searchable"

    # A separate decision releases the held listing just like a split.
    third = listing(client, headers, advertised_rent_cents=305_000)
    held = client.get("/admin/duplicates", headers=headers).json()["items"]
    assert held and held[0]["status"] == "queued"
    kept = client.post(f"/admin/duplicates/{held[0]['id']}/keep-separate", headers=headers)
    assert kept.status_code == 200 and kept.json()["status"] == "separate"
    assert client.get(f"/listings/{third['id']}").json()["status"] == "searchable"


def test_admin_sources_reports_and_permissions(client, db):
    headers, _user = account(client, "person@example.com")
    reporter_headers, _ = account(client, "reporter@example.com")
    card = listing(client, headers)

    assert client.get("/admin/sources", headers=headers).status_code == 403
    with db.transaction() as tx:
        UserMapper(tx).set_role("person@example.com", "admin")

    sources = client.get("/admin/sources", headers=headers).json()
    assert [s["name"] for s in sources] == ["Manual entry"]
    created = client.post("/admin/sources", json={"name": "SampleFeed", "kind": "feed"}, headers=headers)
    assert created.status_code == 201 and created.json()["is_synthetic"] is True
    assert client.post("/admin/sources", json={"name": "SampleFeed"}, headers=headers).status_code == 409
    updated = client.patch(f"/admin/sources/{created.json()['id']}", json={"enabled": False}, headers=headers)
    assert updated.status_code == 200 and updated.json()["enabled"] is False

    report = client.post(f"/listings/{card['id']}/reports", json={"reason": "wrong_value", "details": "Rent is off"},
                         headers=reporter_headers)
    assert report.status_code == 201 and report.json()["status"] == "open"
    reports = client.get("/admin/reports", headers=headers).json()
    assert reports["total"] == 1
    resolved = client.post(f"/admin/reports/{report.json()['id']}/resolve", json={"status": "resolved"},
                           headers=headers)
    assert resolved.status_code == 200 and resolved.json()["status"] == "resolved"
    assert client.post(f"/admin/reports/{report.json()['id']}/resolve", json={"status": "dismissed"},
                       headers=headers).status_code == 409


# --- comparison -----------------------------------------------------------------------


def test_comparison_preview_save_share_and_change_tracking(client, db):
    headers, _ = account(client, "person@example.com")
    other_headers, _ = account(client, "other@example.com")
    first = listing(client, headers)
    second = listing(client, headers, address_line="2 Other Street", advertised_rent_cents=450_000, area_sqft=900)
    tied = listing(client, headers, address_line="3 Third Street", advertised_rent_cents=450_000, area_sqft=900)

    preview = client.post("/comparisons/preview", json={"listing_ids": [first["id"], second["id"]]})
    assert preview.status_code == 200, preview.text
    rows = {row["key"]: row for row in preview.json()["rows"]}
    assert [cell["best"] for cell in rows["advertised_rent_cents"]["cells"]] == [True, False]
    assert rows["advertised_rent_cents"]["direction"] == "lower"
    assert rows["price_per_sqft_cents"]["formula"]
    assert rows["commute"]["cells"][0]["known"] is False
    assert "Commute estimates are not available yet." in preview.json()["notes"]

    # A tie is never marked best, and one known value is not enough to rank.
    tie_rows = {row["key"]: row for row in client.post(
        "/comparisons/preview", json={"listing_ids": [second["id"], tied["id"]]}).json()["rows"]}
    assert not any(cell["best"] for cell in tie_rows["advertised_rent_cents"]["cells"])

    saved = client.post("/comparisons", json={"listing_ids": [first["id"], second["id"]], "title": "Top two"},
                        headers=headers)
    assert saved.status_code == 201
    comparison = saved.json()
    assert comparison["stale"] is False
    assert [change["state"] for change in comparison["changes"]] == ["unchanged", "unchanged"]
    assert [c["id"] for c in client.get("/comparisons", headers=headers).json()] == [comparison["id"]]
    assert client.get(f"/comparisons/{comparison['id']}", headers=other_headers).status_code == 403

    crew = group_with(client, headers, other_headers, "other@example.com")
    shared = client.post(f"/comparisons/{comparison['id']}/share", json={"group_id": crew["id"]}, headers=headers)
    assert shared.status_code == 200 and shared.json()["group_id"] == crew["id"]
    assert client.post(f"/comparisons/{comparison['id']}/share", json={"group_id": crew["id"]},
                       headers=headers).status_code == 409
    assert [c["id"] for c in client.get(f"/groups/{crew['id']}/comparisons", headers=other_headers).json()] == [
        comparison["id"]]

    with db.transaction() as tx:
        ListingMapper(tx).update(first["id"], {"advertised_rent_cents": 290_000})
    changed = client.get(f"/comparisons/{comparison['id']}", headers=headers).json()
    assert changed["stale"] is True
    assert changed["changes"][0]["state"] == "changed"
    assert set(changed["changes"][0]["changed_fields"]) == {"advertised_rent_cents", "price_per_sqft_cents"}


# --- rooms and notifications ----------------------------------------------------------


def test_room_messages_reactions_polls_and_notifications(db, client):
    owner_headers, _owner = account(client, "owner@example.com")
    member_headers, _member = account(client, "member@example.com")
    outsider_headers, _ = account(client, "outsider@example.com")
    crew = group_with(client, owner_headers, member_headers, "member@example.com")

    assert client.get(f"/groups/{crew['id']}/messages", headers=outsider_headers).status_code == 403
    message = client.post(f"/groups/{crew['id']}/messages", json={"body": "Tour on Saturday?"},
                          headers=owner_headers)
    assert message.status_code == 201, message.text
    message_id = message.json()["id"]

    inbox = client.get("/notifications", headers=member_headers).json()
    assert (inbox["total"], inbox["unread"]) == (1, 1)
    assert inbox["items"][0]["kind"] == "message"
    read = client.post(f"/notifications/{inbox['items'][0]['id']}/read", headers=member_headers)
    assert read.status_code == 200 and read.json()["read"] is True
    assert client.get("/notifications", headers=member_headers).json()["unread"] == 0
    assert client.get("/notifications", headers=outsider_headers).json()["total"] == 0
    client.post(f"/groups/{crew['id']}/messages", json={"body": "Second"}, headers=owner_headers)
    all_read = client.post("/notifications/read-all", headers=member_headers)
    assert all_read.status_code == 200 and all_read.json()["marked"] == 1

    reacted = client.put(f"/messages/{message_id}/reaction", json={"emoji": "🎉"}, headers=member_headers)
    assert reacted.status_code == 200 and reacted.json() == [{"emoji": "🎉", "count": 1, "mine": True}]
    seen = client.get(f"/groups/{crew['id']}/messages", headers=owner_headers).json()
    tour = next(item for item in seen if item["id"] == message_id)
    assert (tour["body"], tour["reactions"][0]["mine"]) == ("Tour on Saturday?", False)
    assert client.delete(f"/messages/{message_id}/reaction", headers=member_headers).json() == []

    poll = client.post(f"/groups/{crew['id']}/polls", json={
        "question": "Which one?", "options": ["Knickerbocker", "Steinway"],
    }, headers=owner_headers)
    assert poll.status_code == 201
    poll_id = poll.json()["id"]
    option_ids = [option["id"] for option in poll.json()["options"]]
    assert [p["id"] for p in client.get(f"/groups/{crew['id']}/polls", headers=member_headers).json()] == [poll_id]
    assert client.get(f"/polls/{poll_id}", headers=member_headers).json()["total_votes"] == 0
    voted = client.put(f"/polls/{poll_id}/vote", json={"option_id": option_ids[0]}, headers=member_headers)
    assert voted.status_code == 200 and voted.json()["total_votes"] == 1
    changed = client.put(f"/polls/{poll_id}/vote", json={"option_id": option_ids[1]}, headers=member_headers)
    assert [option["votes"] for option in changed.json()["options"]] == [0, 1]
    assert client.put(f"/polls/{poll_id}/vote", json={"option_id": option_ids[0]},
                      headers=outsider_headers).status_code == 403
    assert client.post(f"/polls/{poll_id}/close", headers=member_headers).status_code == 403
    assert client.post(f"/polls/{poll_id}/close", headers=owner_headers).json()["state"] == "closed"
    assert client.put(f"/polls/{poll_id}/vote", json={"option_id": option_ids[0]},
                      headers=member_headers).status_code == 409


def test_notification_settings_filter_delivery(client):
    owner_headers, _ = account(client, "owner@example.com")
    member_headers, _ = account(client, "member@example.com")
    crew = group_with(client, owner_headers, member_headers, "member@example.com")

    settings = client.get("/me/notification-settings", headers=member_headers).json()
    assert settings["kinds"] == ["new_match", "price_change", "removed", "message"]
    off = client.put("/me/notification-settings", json={
        "kinds": ["new_match"], "email": False, "digest": False,
    }, headers=member_headers)
    assert off.status_code == 200 and off.json()["kinds"] == ["new_match"]
    assert client.put("/me/notification-settings", json={"quiet_start": "22:00"},
                      headers=member_headers).status_code == 422

    client.post(f"/groups/{crew['id']}/messages", json={"body": "No alert for you"}, headers=owner_headers)
    assert client.get("/notifications", headers=member_headers).json()["total"] == 0


def test_a_group_never_exceeds_six_members(client):
    owner_headers, _ = account(client, "owner@example.com")
    crew = group(client, owner_headers)
    outsiders = [account(client, f"person{index}@example.com") for index in range(5)]
    emails = [f"person{index}@example.com" for index in range(5)]
    for (headers, _), email in zip(outsiders, emails, strict=True):
        join(client, crew, owner_headers, headers, email)
    assert len(client.get(f"/groups/{crew['id']}", headers=owner_headers).json()["members"]) == 6
    _extra_headers, _ = account(client, "extra@example.com")
    assert client.post(f"/groups/{crew['id']}/invitations", json={"email": "extra@example.com"},
                       headers=owner_headers).status_code == 409


# --- account deletion ----------------------------------------------------------------


def test_account_deletion_scrubs_personal_data_and_shared_content(client):
    owner_headers, _owner = account(client, "owner@example.com")
    member_headers, member = account(client, "member@example.com")
    crew = group_with(client, owner_headers, member_headers, "member@example.com")
    client.post(f"/groups/{crew['id']}/messages", json={"body": "Count me in"}, headers=member_headers)

    assert client.request("DELETE", "/me", json={"password": "wrong password"},
                          headers=member_headers).status_code == 401
    assert client.request("DELETE", "/me", json={"password": PASSWORD}, headers=owner_headers).status_code == 409

    assert client.request("DELETE", "/me", json={"password": PASSWORD}, headers=member_headers).status_code == 204
    assert client.get("/me", headers=member_headers).status_code == 401
    seen = client.get(f"/groups/{crew['id']}/messages", headers=owner_headers).json()
    assert seen[0]["author"] == {"id": str(member["id"]), "name": "Deleted user", "deleted": True}
    assert [m["role"] for m in client.get(f"/groups/{crew['id']}", headers=owner_headers).json()["members"]] == [
        "owner"]

    # The owner is now alone, so the group is dissolved with the account.
    assert client.request("DELETE", "/me", json={"password": PASSWORD}, headers=owner_headers).status_code == 204
    assert client.get(f"/groups/{crew['id']}", headers=owner_headers).status_code == 401
