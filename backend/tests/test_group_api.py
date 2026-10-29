"""Group Management use case (§8.1.2.2, R-1.2, R-1.3) through the HTTP API."""

import pytest

from conftest import Api

pytestmark = pytest.mark.integration


def test_create_invite_accept(api: Api) -> None:
    owner, _ = api.user("Olivia")
    invitee, invitee_user = api.user("Ivan")
    created = api.post("/groups", {"name": "  Fall search  "}, owner)
    assert created.status == 201
    group = created.json["id"]
    assert created.json["name"] == "Fall search"
    assert created.json["my_role"] == "owner"

    inv = api.post(f"/groups/{group}/invitations", {"email": invitee_user["email"]}, owner)
    assert inv.status == 201
    assert inv.json["state"] == "pending"
    incoming = api.get("/invitations", invitee).json
    assert [(i["group_name"], i["invited_by"]) for i in incoming] == [("Fall search", "Olivia")]

    joined = api.post(f"/invitations/{inv.json['id']}/accept", token=invitee)
    assert joined.status == 201
    assert [m["user"]["name"] for m in joined.json["members"]] == ["Olivia", "Ivan"]
    assert api.get("/groups", invitee).json[0]["member_count"] == 2
    assert api.get(f"/groups/{group}/invitations", owner).json[0]["state"] == "accepted"


def test_accepted_invitation_cannot_be_reused(api: Api) -> None:
    owner, _ = api.user()
    invitee, user = api.user()
    group = api.group(owner)
    inv = api.post(f"/groups/{group}/invitations", {"email": user["email"]}, owner).json
    assert api.post(f"/invitations/{inv['id']}/accept", token=invitee).status == 201
    again = api.post(f"/invitations/{inv['id']}/accept", token=invitee)
    assert again.status == 409
    assert len(api.get(f"/groups/{group}", owner).json["members"]) == 2


def test_expired_invitation_is_rejected(api: Api) -> None:
    owner, _ = api.user()
    invitee, user = api.user()
    group = api.group(owner)
    inv = api.post(f"/groups/{group}/invitations", {"email": user["email"]}, owner).json
    with api.db.transaction() as conn:
        conn.execute("UPDATE group_invitation SET created_at = now() - interval '9 days', "
                     "expires_at = now() - interval '1 day' WHERE id = %s", (inv["id"],))
    r = api.post(f"/invitations/{inv['id']}/accept", token=invitee)
    assert r.status == 409
    assert "expired" in r.json["detail"]
    assert api.get(f"/groups/{group}/invitations", owner).json[0]["state"] == "expired"


def test_invitations_are_only_for_their_addressee(api: Api) -> None:
    owner, _ = api.user()
    _, target = api.user()
    stranger, _ = api.user()
    group = api.group(owner)
    inv = api.post(f"/groups/{group}/invitations", {"email": target["email"]}, owner).json
    assert api.post(f"/invitations/{inv['id']}/accept", token=stranger).status == 404


def test_group_is_capped_at_six(api: Api) -> None:
    owner, _ = api.user()
    members = [api.user()[0] for _ in range(5)]
    group = api.group(owner, *members)
    _, seventh = api.user()
    r = api.post(f"/groups/{group}/invitations", {"email": seventh["email"]}, owner)
    assert r.status == 409
    assert "6" in r.json["detail"]


def test_only_the_owner_invites_and_duplicates_are_refused(api: Api) -> None:
    owner, _ = api.user()
    member, member_user = api.user()
    _, other = api.user()
    group = api.group(owner, member)
    assert api.post(f"/groups/{group}/invitations", {"email": other["email"]}, member).status == 403
    assert api.post(f"/groups/{group}/invitations", {"email": member_user["email"]}, owner).status == 409
    assert api.post(f"/groups/{group}/invitations", {"email": other["email"]}, owner).status == 201
    assert api.post(f"/groups/{group}/invitations", {"email": other["email"]}, owner).status == 409


def test_private_content_is_for_current_members_only(api: Api) -> None:
    owner, _ = api.user()
    member, _ = api.user()
    outsider, _ = api.user()
    group = api.group(owner, member)
    assert api.get(f"/groups/{group}", outsider).status == 403
    assert api.get(f"/groups/{group}/messages", outsider).status == 403

    assert api.post(f"/groups/{group}/leave", token=member).status == 204
    assert api.get(f"/groups/{group}", member).status == 403   # access stops at once
    assert api.post(f"/groups/{group}/messages", {"body": "still here?"}, member).status == 403


def test_administrators_cannot_join_or_open_rooms(api: Api) -> None:
    owner, _ = api.user()
    admin, admin_user = api.user(admin=True)
    group = api.group(owner)
    assert api.post("/groups", {"name": "admins"}, admin).status == 403
    inv = api.post(f"/groups/{group}/invitations", {"email": admin_user["email"]}, owner).json
    assert api.post(f"/invitations/{inv['id']}/accept", token=admin).status == 403
    assert api.get(f"/groups/{group}/messages", admin).status == 403


def test_owner_transfers_before_leaving(api: Api) -> None:
    owner, _ = api.user("Olivia")
    member, member_user = api.user("Max")
    group = api.group(owner, member)
    assert api.post(f"/groups/{group}/leave", token=owner).status == 409
    assert api.post(f"/groups/{group}/transfer", {"user_id": member_user["id"]}, member).status == 403
    moved = api.post(f"/groups/{group}/transfer", {"user_id": member_user["id"]}, owner)
    assert moved.status == 200
    assert {m["user"]["name"]: m["role"] for m in moved.json["members"]} == {"Max": "owner", "Olivia": "member"}
    assert api.post(f"/groups/{group}/leave", token=owner).status == 204
    assert api.get(f"/groups/{group}", member).json["my_role"] == "owner"


def test_owner_removes_a_member_and_declines_work(api: Api) -> None:
    owner, _ = api.user()
    member, member_user = api.user()
    invitee, invitee_user = api.user()
    group = api.group(owner, member)
    assert api.delete(f"/groups/{group}/members/{member_user['id']}", token=member).status == 403
    assert api.delete(f"/groups/{group}/members/{member_user['id']}", token=owner).status == 204
    assert api.get(f"/groups/{group}", member).status == 403

    inv = api.post(f"/groups/{group}/invitations", {"email": invitee_user["email"]}, owner).json
    assert api.post(f"/invitations/{inv['id']}/decline", token=invitee).status == 204
    assert api.post(f"/invitations/{inv['id']}/accept", token=invitee).status == 409


def test_bad_ids_are_422_and_unknown_groups_404(api: Api) -> None:
    owner, _ = api.user()
    assert api.get("/groups/not-a-uuid", owner).status == 422
    assert api.get("/groups/00000000-0000-0000-0000-000000000000", owner).status == 404
