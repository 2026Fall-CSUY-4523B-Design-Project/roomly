"""Login use case (§8.1.2.1, R-1.1, R-1.4) through the HTTP API."""

import pytest

from conftest import PASSWORD, Api

pytestmark = pytest.mark.integration


def test_sign_up_sign_in_me_sign_out(api: Api) -> None:
    r = api.post("/auth/sign-up", {"email": "Ann@Example.com", "password": PASSWORD, "display_name": "Ann"})
    assert r.status == 201
    assert r.json["user"]["email"] == "ann@example.com"
    assert "password" not in str(r.json["user"])

    signed_in = api.post("/auth/sign-in", {"email": "ann@example.com", "password": PASSWORD})
    assert signed_in.status == 200
    token = signed_in.json["token"]
    assert api.get("/me", token).json["display_name"] == "Ann"

    assert api.post("/auth/sign-out", token=token).status == 204
    gone = api.get("/me", token)
    assert gone.status == 401
    assert gone.headers.get("WWW-Authenticate") == "Bearer"


def test_duplicate_email_and_bad_credentials(api: Api) -> None:
    api.user()
    first = api.post("/auth/sign-up", {"email": "dup@example.com", "password": PASSWORD})
    assert first.status == 201
    assert api.post("/auth/sign-up", {"email": "DUP@example.com", "password": PASSWORD}).status == 409
    wrong = api.post("/auth/sign-in", {"email": "dup@example.com", "password": "wrong password"})
    unknown = api.post("/auth/sign-in", {"email": "nobody@example.com", "password": PASSWORD})
    assert wrong.status == unknown.status == 401
    assert wrong.json == unknown.json  # no hint about which part was wrong


def test_requests_without_a_valid_token_are_401(api: Api) -> None:
    assert api.get("/me").status == 401
    assert api.get("/me", "not-a-real-token").status == 401
    assert api.post("/groups", {"name": "x"}).status == 401


def test_validation_errors_are_422(api: Api) -> None:
    r = api.post("/auth/sign-up", {"email": "x", "password": "123"})
    assert r.status == 422
    assert {tuple(e["loc"]) for e in r.json["detail"]} == {("body", "email"), ("body", "password")}
    assert api.call("POST", "/auth/sign-up", None).status == 400  # not JSON at all


def test_delete_account_needs_password_and_anonymizes_shared_content(api: Api) -> None:
    owner, _ = api.user("Owner")
    leaver, leaver_user = api.user("Leaver")
    group = api.group(owner, leaver)
    api.post(f"/groups/{group}/messages", {"body": "I like the first one"}, leaver)

    assert api.delete("/me", {"password": "nope"}, leaver).status == 403
    assert api.delete("/me", {"password": PASSWORD}, leaver).status == 204
    assert api.get("/me", leaver).status == 401
    assert api.post("/auth/sign-in", {"email": leaver_user["email"], "password": PASSWORD}).status == 401

    messages = api.get(f"/groups/{group}/messages", owner).json
    assert messages[0]["author"] == {"id": leaver_user["id"], "name": "Deleted user", "deleted": True}
    members = api.get(f"/groups/{group}", owner).json["members"]
    assert [m["user"]["name"] for m in members] == ["Owner"]


def test_owner_with_members_must_transfer_before_deleting(api: Api) -> None:
    owner, _ = api.user()
    member, _ = api.user()
    group = api.group(owner, member)
    r = api.delete("/me", {"password": PASSWORD}, owner)
    assert r.status == 409
    assert group in r.json["detail"]

    solo, _ = api.user()
    solo_group = api.group(solo)
    assert api.delete("/me", {"password": PASSWORD}, solo).status == 204
    assert api.get(f"/groups/{solo_group}", owner).status == 404  # dissolved with its only member
