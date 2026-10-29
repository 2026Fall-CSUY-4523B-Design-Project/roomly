"""Group Discussion (§8.1.2.7, R-5) and the message alerts it triggers (R-6) through the HTTP API."""

import pytest

from conftest import Api

pytestmark = pytest.mark.integration


def test_messages_threads_and_alerts(api: Api) -> None:
    owner, _ = api.user("Olivia")
    member, _ = api.user("Max")
    group = api.group(owner, member, name="Bushwick hunt")
    listing = api.listing(owner)

    general = api.post(f"/groups/{group}/messages", {"body": "Saturday viewings?"}, owner)
    assert general.status == 201
    assert general.json["author"]["name"] == "Olivia"
    on_listing = api.post(f"/groups/{group}/messages", {"body": "Love the light", "listing_id": listing["id"]}, member)
    assert on_listing.status == 201

    room = api.get(f"/groups/{group}/messages", owner).json
    assert [m["body"] for m in room] == ["Love the light", "Saturday viewings?"]      # newest first
    thread = api.get(f"/groups/{group}/messages?listing_id={listing['id']}", owner).json
    assert [m["id"] for m in thread] == [on_listing.json["id"]]
    older = api.get(f"/groups/{group}/messages?before={on_listing.json['sent_at']}", owner).json
    assert [m["id"] for m in older] == [general.json["id"]]

    owner_inbox = api.get("/notifications", owner).json
    member_inbox = api.get("/notifications", member).json
    assert [n["title"] for n in owner_inbox["items"]] == ["New message in Bushwick hunt"]   # not the sender
    assert [n["title"] for n in member_inbox["items"]] == ["New message in Bushwick hunt"]
    assert "Love the light" not in str(owner_inbox)                                     # never the body


def test_comparison_threads_must_belong_to_the_group(api: Api) -> None:
    owner, _ = api.user()
    other_owner, _ = api.user()
    group = api.group(owner)
    other_group = api.group(other_owner)
    a, b = api.listing(owner), api.listing(owner)
    foreign = api.post("/comparisons", {"listing_ids": [a["id"], b["id"]], "group_id": other_group}, other_owner).json
    r = api.post(f"/groups/{group}/messages", {"body": "look", "comparison_id": foreign["id"]}, owner)
    assert r.status == 422
    mine = api.post("/comparisons", {"listing_ids": [a["id"], b["id"]], "group_id": group}, owner).json
    assert api.post(f"/groups/{group}/messages", {"body": "look", "comparison_id": mine["id"]}, owner).status == 201


def test_one_reaction_per_user(api: Api) -> None:
    owner, _ = api.user()
    member, _ = api.user()
    group = api.group(owner, member)
    message = api.post(f"/groups/{group}/messages", {"body": "This one?"}, owner).json

    api.put(f"/messages/{message['id']}/reaction", {"emoji": "👍"}, owner)
    api.put(f"/messages/{message['id']}/reaction", {"emoji": "👍"}, member)
    replaced = api.put(f"/messages/{message['id']}/reaction", {"emoji": "❤️"}, member).json
    assert sorted((r["emoji"], r["count"], r["mine"]) for r in replaced) == [("❤️", 1, True), ("👍", 1, False)]
    after = api.delete(f"/messages/{message['id']}/reaction", token=member).json
    assert [(r["emoji"], r["count"]) for r in after] == [("👍", 1)]
    listed = api.get(f"/groups/{group}/messages", owner).json[0]["reactions"]
    assert listed == [{"emoji": "👍", "count": 1, "mine": True}]


def test_former_members_cannot_post_or_react(api: Api) -> None:
    owner, _ = api.user()
    member, _ = api.user()
    group = api.group(owner, member)
    message = api.post(f"/groups/{group}/messages", {"body": "hi"}, owner).json
    api.post(f"/groups/{group}/leave", token=member)
    assert api.post(f"/groups/{group}/messages", {"body": "hello?"}, member).status == 403
    assert api.put(f"/messages/{message['id']}/reaction", {"emoji": "👀"}, member).status == 403


def test_poll_lifecycle(api: Api) -> None:
    owner, _ = api.user()
    member, _ = api.user()
    third, _ = api.user()
    group = api.group(owner, member, third)

    poll = api.post(f"/groups/{group}/polls", {"question": "Which apartment?", "options": ["Kent", "Grand"]}, member)
    assert poll.status == 201
    kent, grand = (o["id"] for o in poll.json["options"])

    api.put(f"/polls/{poll.json['id']}/vote", {"option_id": kent}, owner)
    api.put(f"/polls/{poll.json['id']}/vote", {"option_id": kent}, member)
    changed = api.put(f"/polls/{poll.json['id']}/vote", {"option_id": grand}, member).json   # one active vote
    assert [o["votes"] for o in changed["options"]] == [1, 1]
    assert changed["my_vote"] == grand

    third_vote = api.put(f"/polls/{poll.json['id']}/vote", {"option_id": grand}, third).json
    assert third_vote["total_votes"] == 3
    api.delete(f"/groups/{group}/members/{api.get('/me', third).json['id']}", token=owner)
    assert api.get(f"/polls/{poll.json['id']}", owner).json["total_votes"] == 2           # removed member's vote stops counting

    other_poll = api.post(f"/groups/{group}/polls", {"question": "?", "options": ["x", "y"]}, owner).json
    wrong_option = api.put(f"/polls/{poll.json['id']}/vote", {"option_id": other_poll["options"][0]["id"]}, owner)
    assert wrong_option.status == 422

    assert api.post(f"/polls/{poll.json['id']}/close", token=api.user()[0]).status == 403   # outsider
    closed = api.post(f"/polls/{poll.json['id']}/close", token=owner)                       # owner may close
    assert closed.json["state"] == "closed"
    late = api.put(f"/polls/{poll.json['id']}/vote", {"option_id": kent}, member)
    assert late.status == 409
    assert api.post(f"/polls/{poll.json['id']}/close", token=member).status == 409


def test_only_creator_or_owner_closes(api: Api) -> None:
    owner, _ = api.user()
    creator, _ = api.user()
    bystander, _ = api.user()
    group = api.group(owner, creator, bystander)
    poll = api.post(f"/groups/{group}/polls", {"question": "Budget?", "options": ["$2k", "$3k"]}, creator).json
    assert api.post(f"/polls/{poll['id']}/close", token=bystander).status == 403
    assert api.post(f"/polls/{poll['id']}/close", token=creator).status == 200
    assert [p["state"] for p in api.get(f"/groups/{group}/polls", bystander).json] == ["closed"]
