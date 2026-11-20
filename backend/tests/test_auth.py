"""Real HTTP authentication, on both database engines."""

import datetime as dt
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from roomly.config import Settings
from roomly.main import create_app
from roomly.mapper.account_mapper import SessionMapper, UserMapper
from roomly.service.account_service import token_hash

pytestmark = pytest.mark.integration
PASSWORD = "  correct horse battery  "


@pytest.fixture
def client(db):
    return TestClient(create_app(Settings.from_env({}), database=db))


def signup(client, email="person@example.com"):
    response = client.post("/auth/sign-up", json={"email": email, "password": PASSWORD, "display_name": "Person"})
    assert response.status_code == 201, response.text
    assert "x-roomly-fixture" not in response.headers
    return response.json()


def auth(session):
    return {"Authorization": f"Bearer {session['token']}"}


def test_account_lifecycle_and_persistence(client, db):
    session = signup(client, "PERSON@EXAMPLE.COM")
    assert session["user"]["email"] == "person@example.com"
    assert client.get("/me", headers=auth(session)).json() == session["user"]
    # A fresh application uses the same persisted account and session.
    restarted = TestClient(create_app(Settings.from_env({}), database=db))
    assert restarted.get("/me", headers=auth(session)).status_code == 200
    with db.transaction() as tx:
        user = UserMapper(tx).find_by_email("person@example.com")
        assert user.password_hash != PASSWORD
        assert user.password_hash.startswith("scrypt$")
        assert SessionMapper(tx).find_user_by_token(token_hash(session["token"])).id == user.id
        assert tx.scalar("SELECT token_hash FROM user_session") == token_hash(session["token"])
    second = client.post("/auth/sign-in", json={"email": "PERSON@example.com", "password": PASSWORD})
    assert second.status_code == 200
    assert second.json()["token"] != session["token"]
    assert client.post("/auth/sign-out", headers=auth(session)).status_code == 204
    assert client.get("/me", headers=auth(session)).status_code == 401
    assert client.get("/me", headers=auth(second.json())).status_code == 200
    assert client.post("/auth/sign-out", headers=auth(session)).status_code == 204


def test_invalid_credentials_duplicate_and_isolation(client, db):
    first = signup(client)
    other = signup(client, "other@example.com")
    assert first["user"]["id"] != other["user"]["id"]
    assert client.get("/me", headers=auth(other)).json()["email"] == "other@example.com"
    duplicate = client.post("/auth/sign-up", json={"email": "PERSON@example.com", "password": PASSWORD})
    assert duplicate.status_code == 409
    failures = []
    for email, password in [("person@example.com", "wrong"), ("missing@example.com", PASSWORD),
                            ("person@example.com", PASSWORD.strip())]:
        response = client.post("/auth/sign-in", json={"email": email, "password": password})
        assert response.status_code == 401
        assert response.headers["www-authenticate"] == "Bearer"
        failures.append(response.json())
    assert failures[0] == failures[1] == failures[2]
    with db.transaction() as tx:
        assert tx.scalar("SELECT count(*) FROM user_session") == 2
        assert tx.scalar("SELECT count(*) FROM app_user") == 2
    for headers in [{}, {"Authorization": "Bearer any-token"}]:
        assert client.get("/me", headers=headers).status_code == 401


def test_expired_and_deleted_tokens(client, db):
    session = signup(client)
    with db.transaction() as tx:
        tx.exec("UPDATE user_session SET created_at = %(created)s, expires_at = %(expired)s",
                {"created": dt.datetime.now(dt.UTC) - dt.timedelta(days=2),
                 "expired": dt.datetime.now(dt.UTC) - dt.timedelta(days=1)})
    assert client.get("/me", headers=auth(session)).status_code == 401
    session = client.post("/auth/sign-in", json={"email": "person@example.com", "password": PASSWORD}).json()
    with db.transaction() as tx:
        user = UserMapper(tx).find_by_email("person@example.com")
        UserMapper(tx).scrub(user.id)
    assert client.get("/me", headers=auth(session)).status_code == 401
    assert client.post("/auth/sign-in", json={"email": "person@example.com", "password": PASSWORD}).status_code == 401
    restarted = TestClient(create_app(Settings.from_env({}), database=db))
    assert restarted.get("/groups", headers={"Authorization": "Bearer any-token"}).status_code == 401
    real = signup(restarted, "real@example.com")
    assert restarted.get("/me", headers=auth(real)).json()["email"] == "real@example.com"


def test_concurrent_duplicate_signup(client, db):
    def create(_):
        return client.post("/auth/sign-up", json={"email": "race@example.com", "password": PASSWORD}).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(create, range(2))) == [201, 409]
    with db.transaction() as tx:
        assert tx.scalar("SELECT count(*) FROM app_user") == 1
        assert tx.scalar("SELECT count(*) FROM user_session") == 1
