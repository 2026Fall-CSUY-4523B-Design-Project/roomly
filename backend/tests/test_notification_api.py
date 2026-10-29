"""Notifications (§8.1.2.8, R-6) through the HTTP API and the notifier itself."""

import pytest

from conftest import Api
from roomly.entity import Group, Message
from roomly.mapper import GroupMapper, MessageMapper
from roomly.service.notification_service import notify_group_message

pytestmark = pytest.mark.integration


def test_inbox_read_and_read_all(api: Api) -> None:
    owner, _ = api.user()
    member, _ = api.user()
    group = api.group(owner, member)
    for text in ("one", "two", "three"):
        api.post(f"/groups/{group}/messages", {"body": text}, owner)
    inbox = api.get("/notifications", member).json
    assert (inbox["total"], inbox["unread"]) == (3, 3)

    first = inbox["items"][0]["id"]
    read = api.post(f"/notifications/{first}/read", token=member)
    assert read.json["read"] is True
    assert api.post(f"/notifications/{first}/read", token=owner).status == 404   # not theirs
    assert api.get("/notifications?unread=true", member).json["total"] == 2
    assert api.post("/notifications/read-all", token=member).json == {"marked": 2}
    assert api.get("/notifications", member).json["unread"] == 0


def test_retried_event_creates_no_second_alert(api: Api) -> None:
    owner, _ = api.user()
    member, _ = api.user()
    group_id = api.group(owner, member)
    posted = api.post(f"/groups/{group_id}/messages", {"body": "hello"}, owner).json
    with api.db.transaction() as conn:
        group = GroupMapper(conn).find(group_id)
        message = MessageMapper(conn).find(posted["id"])
        assert isinstance(group, Group) and isinstance(message, Message)
        assert notify_group_message(conn, group, message) == 0
    assert api.get("/notifications", member).json["total"] == 1


def test_settings_choose_which_alerts_arrive(api: Api) -> None:
    owner, _ = api.user()
    member, _ = api.user()
    group = api.group(owner, member)
    defaults = api.get("/me/notification-settings", member).json
    assert defaults == {"kinds": ["new_match", "price_change", "removed", "message"], "email": True,
                        "digest": False, "quiet_start": None, "quiet_end": None}

    updated = api.put("/me/notification-settings", {"kinds": ["new_match"], "email": False, "digest": True,
                                                    "quiet_start": "22:00", "quiet_end": "07:30"}, member)
    assert updated.status == 200
    assert updated.json["quiet_end"] == "07:30:00"
    api.post(f"/groups/{group}/messages", {"body": "muted for you"}, owner)
    assert api.get("/notifications", member).json["total"] == 0

    bad_kind = api.put("/me/notification-settings", {"kinds": ["gossip"]}, member)
    assert [e["loc"] for e in bad_kind.json["detail"]] == [["body", "kinds", 0]]
    half_quiet = api.put("/me/notification-settings", {"quiet_start": "22:00"}, member)
    assert [e["loc"] for e in half_quiet.json["detail"]] == [["body", "quiet_end"]]


def test_email_is_queued_only_for_users_who_want_it(api: Api) -> None:
    owner, _ = api.user()
    wants, _ = api.user()
    declines, _ = api.user()
    group = api.group(owner, wants, declines)
    api.put("/me/notification-settings", {"email": False}, declines)
    api.post(f"/groups/{group}/messages", {"body": "hi"}, owner)
    with api.db.transaction() as conn:
        rows = conn.execute("SELECT u.notify_email, n.email_status FROM notification n "
                            "JOIN app_user u ON u.id = n.recipient_id ORDER BY 1").fetchall()
    assert rows == [(False, "none"), (True, "pending")]
