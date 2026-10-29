"""script/backend.sh admin: granting the administrator role keeps access isolation intact."""

import pytest

from roomly.admin_cli import set_admin

from conftest import Api

pytestmark = pytest.mark.integration


def test_promote_and_revoke(api: Api, database_url: str) -> None:
    token, user = api.user()
    assert api.get("/admin/sources", token).status == 403
    assert set_admin(database_url, f"  {user['email'].upper()} ", revoke=False) == user["id"]
    assert api.get("/admin/sources", token).status == 200
    set_admin(database_url, user["email"], revoke=True)
    assert api.get("/admin/sources", token).status == 403


def test_group_members_cannot_become_admins(api: Api, database_url: str) -> None:
    token, user = api.user()
    api.group(token)
    with pytest.raises(PermissionError):
        set_admin(database_url, user["email"], revoke=False)
    with pytest.raises(LookupError):
        set_admin(database_url, "nobody@example.com", revoke=False)
