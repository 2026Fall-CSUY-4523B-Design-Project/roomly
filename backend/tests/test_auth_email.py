"""Email verification and password reset, on both database engines."""

import datetime as dt
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import ClassVar
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient

from roomly.config import Settings
from roomly.entity import AuthToken
from roomly.main import create_app
from roomly.mapper.account_mapper import UserMapper
from roomly.mapper.base import columns
from roomly.service.account_service import (
    RESET_LIFETIME,
    SEND_LIMIT,
    VERIFY_LIFETIME,
    token_hash,
)
from roomly.service.mailer import (
    HttpMailer,
    LogMailer,
    MailError,
    Message,
    build_mailer,
)

from conftest import link

pytestmark = pytest.mark.integration
PASSWORD = "correct horse battery"
EMAIL = "person@example.com"


@pytest.fixture
def client(db, mailer):
    return TestClient(create_app(Settings.from_env({}), database=db, mailer=mailer))


def sign_up(client, email=EMAIL, password=PASSWORD):
    response = client.post("/auth/sign-up", json={"email": email, "password": password, "display_name": "Pat"})
    assert response.status_code == 201, response.text
    return response.json()


def sign_in(client, password=PASSWORD, email=EMAIL):
    return client.post("/auth/sign-in", json={"email": email, "password": password})


def verified(client, mailer, email=EMAIL, password=PASSWORD):
    sign_up(client, email, password)
    assert client.post("/auth/verify-email", json={"token": mailer.last("verify_email", email).token}).status_code == 204


def age_tokens(db, seconds, kind=None):
    """Make every token (of one kind) look ``seconds`` older, as if time had passed."""
    delta = dt.timedelta(seconds=seconds)
    with db.transaction() as tx:
        rows = tx.all(AuthToken, f"SELECT {columns(AuthToken)} FROM auth_token" +
                      (" WHERE kind = %(k)s" if kind else ""), {"k": kind} if kind else None)
        for row in rows:
            tx.exec("UPDATE auth_token SET created_at = %(c)s, expires_at = %(e)s WHERE id = %(id)s",
                    {"c": row.created_at - delta, "e": row.expires_at - delta, "id": row.id})


# --- sign-up and verification -----------------------------------------------------------------

def test_sign_up_creates_an_unverified_account_without_a_session(client, db, mailer):
    assert sign_up(client) == {"email": EMAIL, "verification_sent": True}
    assert len(mailer.sent) == 1
    message = mailer.last("verify_email")
    assert (message.to, message.display_name) == (EMAIL, "Pat")
    with db.transaction() as tx:
        user = UserMapper(tx).find_by_email(EMAIL)
        assert user.email_verified_at is None
        assert tx.scalar("SELECT count(*) FROM user_session") == 0
        # Only the hash of the emailed token is stored.
        assert tx.scalar("SELECT token_hash FROM auth_token") == token_hash(message.token)
        assert tx.scalar("SELECT kind FROM auth_token") == "verify_email"


def test_unverified_sign_in_is_refused_only_with_the_right_password(client, mailer):
    sign_up(client)
    blocked = sign_in(client)
    assert blocked.status_code == 403
    assert blocked.json()["detail"]["code"] == "email_not_verified"
    assert "www-authenticate" not in blocked.headers
    # A wrong password or unknown address stays a plain 401, so the 403 cannot be used to find accounts.
    assert sign_in(client, "wrong").status_code == 401
    assert sign_in(client, email="nobody@example.com").status_code == 401


def test_verification_link_works_once_and_unlocks_sign_in(client, mailer):
    sign_up(client)
    token = mailer.last("verify_email").token
    assert client.post("/auth/verify-email", json={"token": token}).status_code == 204
    assert sign_in(client).status_code == 200
    again = client.post("/auth/verify-email", json={"token": token})
    assert again.status_code == 422
    assert again.json()["detail"]["code"] == "invalid_token"


def test_verification_link_expires(client, db, mailer):
    sign_up(client)
    token = mailer.last("verify_email").token
    age_tokens(db, VERIFY_LIFETIME.total_seconds() + 60)
    assert client.post("/auth/verify-email", json={"token": token}).status_code == 422
    assert sign_in(client).status_code == 403


def test_unknown_and_malformed_tokens_are_rejected(client):
    assert client.post("/auth/verify-email", json={"token": "A" * 43}).status_code == 422
    assert client.post("/auth/verify-email", json={"token": "short"}).status_code == 422
    assert client.post("/auth/verify-email", json={"token": "not valid! " * 4}).status_code == 422
    assert client.post("/auth/reset-password", json={"token": "A" * 43, "password": PASSWORD}).status_code == 422


def test_a_reset_token_cannot_verify_an_email_and_vice_versa(client, mailer):
    sign_up(client)
    client.post("/auth/forgot-password", json={"email": EMAIL})
    reset = mailer.last("reset_password").token
    assert client.post("/auth/verify-email", json={"token": reset}).status_code == 422
    verify = mailer.last("verify_email").token
    assert client.post("/auth/reset-password", json={"token": verify, "password": "another password"}).status_code == 422


def test_concurrent_confirmations_spend_the_link_once(client, mailer):
    sign_up(client)
    token = mailer.last("verify_email").token

    def confirm(_):
        return client.post("/auth/verify-email", json={"token": token}).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(confirm, range(2))) == [204, 422]


# --- resend ------------------------------------------------------------------------------------

def test_resend_answers_the_same_for_every_address(client, db, mailer):
    verified(client, mailer, "done@example.com")
    sign_up(client, "pending@example.com")
    mailer.sent.clear()
    answers = {email: client.post("/auth/verify-email/resend", json={"email": email})
               for email in ("pending@example.com", "done@example.com", "nobody@example.com")}
    assert {r.status_code for r in answers.values()} == {202}
    assert {r.text for r in answers.values()} == {""}
    # Throttled by the sign-up mail a moment ago: nothing new went out to anyone.
    assert mailer.sent == []
    age_tokens(db, 120)
    client.post("/auth/verify-email/resend", json={"email": "pending@example.com"})
    client.post("/auth/verify-email/resend", json={"email": "done@example.com"})
    client.post("/auth/verify-email/resend", json={"email": "nobody@example.com"})
    assert [m.to for m in mailer.sent] == ["pending@example.com"]


def test_resend_is_throttled_by_cooldown_and_hourly_limit(client, db, mailer):
    sign_up(client)
    resend = lambda: client.post("/auth/verify-email/resend", json={"email": EMAIL}).status_code
    assert resend() == 202 and len(mailer.sent) == 1          # 60 s cooldown after the sign-up mail
    for expected in range(2, SEND_LIMIT + 1):
        age_tokens(db, 120)
        assert resend() == 202 and len(mailer.sent) == expected
    age_tokens(db, 120)                                         # cooldown over, hourly limit reached
    assert resend() == 202 and len(mailer.sent) == SEND_LIMIT
    age_tokens(db, 3600)
    assert resend() == 202 and len(mailer.sent) == SEND_LIMIT + 1


def test_only_the_newest_link_does_not_matter_every_unexpired_link_works(client, db, mailer):
    sign_up(client)
    first = mailer.last("verify_email").token
    age_tokens(db, 120)
    client.post("/auth/verify-email/resend", json={"email": EMAIL})
    second = mailer.last("verify_email").token
    assert first != second
    assert client.post("/auth/verify-email", json={"token": first}).status_code == 204
    assert sign_in(client).status_code == 200


# --- mail failures -----------------------------------------------------------------------------

def test_sign_up_survives_a_dead_mail_service_and_resend_recovers(client, db, mailer):
    mailer.fail = True
    assert sign_up(client) == {"email": EMAIL, "verification_sent": False}
    with db.transaction() as tx:
        assert tx.scalar("SELECT count(*) FROM app_user") == 1
        assert tx.scalar("SELECT count(*) FROM auth_token") == 0   # the link never arrived: not counted
    mailer.fail = False
    # Nothing was delivered, so nothing counts against the send limit and no cooldown applies.
    assert client.post("/auth/verify-email/resend", json={"email": EMAIL}).status_code == 202
    assert mailer.last("verify_email").to == EMAIL


def test_forgot_password_survives_a_dead_mail_service(client, mailer):
    verified(client, mailer)
    mailer.fail = True
    assert client.post("/auth/forgot-password", json={"email": EMAIL}).status_code == 202


def test_an_unexpected_mailer_bug_is_not_a_server_error(client, mailer):
    def boom(message):
        raise RuntimeError("bug")
    mailer.send = boom
    assert sign_up(client)["verification_sent"] is False


# --- password reset ----------------------------------------------------------------------------

def test_forgot_password_answers_the_same_for_known_and_unknown_addresses(client, mailer):
    verified(client, mailer)
    mailer.sent.clear()
    known = client.post("/auth/forgot-password", json={"email": EMAIL})
    unknown = client.post("/auth/forgot-password", json={"email": "nobody@example.com"})
    assert (known.status_code, known.text) == (unknown.status_code, unknown.text) == (202, "")
    assert [(m.template, m.to) for m in mailer.sent] == [("reset_password", EMAIL)]
    assert client.post("/auth/forgot-password", json={"email": "not-an-email"}).status_code == 422


def test_reset_sets_the_password_and_signs_out_everywhere(client, db, mailer):
    verified(client, mailer)
    old = sign_in(client).json()
    other = sign_in(client).json()
    client.post("/auth/forgot-password", json={"email": EMAIL})
    token = mailer.last("reset_password").token
    changed = client.post("/auth/reset-password", json={"token": token, "password": "a brand new password"})
    assert changed.status_code == 204
    for session in (old, other):
        assert client.get("/me", headers={"Authorization": f"Bearer {session['token']}"}).status_code == 401
    assert sign_in(client).status_code == 401
    assert sign_in(client, "a brand new password").status_code == 200
    with db.transaction() as tx:
        assert tx.scalar("SELECT count(*) FROM user_session") == 1   # only the sign-in just made
    assert client.post("/auth/reset-password", json={"token": token, "password": "yet another one"}).status_code == 422


def test_a_new_reset_link_retires_the_old_ones_on_use(client, db, mailer):
    verified(client, mailer)
    client.post("/auth/forgot-password", json={"email": EMAIL})
    first = mailer.last("reset_password").token
    age_tokens(db, 120)
    client.post("/auth/forgot-password", json={"email": EMAIL})
    second = mailer.last("reset_password").token
    assert client.post("/auth/reset-password", json={"token": second, "password": "the second password"}).status_code == 204
    # Using one link spends every other outstanding reset link for the account.
    assert client.post("/auth/reset-password", json={"token": first, "password": "the first password"}).status_code == 422
    assert sign_in(client, "the second password").status_code == 200


def test_reset_link_expires_after_thirty_minutes(client, db, mailer):
    verified(client, mailer)
    client.post("/auth/forgot-password", json={"email": EMAIL})
    token = mailer.last("reset_password").token
    age_tokens(db, RESET_LIFETIME.total_seconds() + 60, "reset_password")
    assert client.post("/auth/reset-password", json={"token": token, "password": "too late indeed"}).status_code == 422
    assert sign_in(client).status_code == 200   # the old password still works


def test_reset_validates_the_new_password(client, mailer):
    verified(client, mailer)
    client.post("/auth/forgot-password", json={"email": EMAIL})
    token = mailer.last("reset_password").token
    assert client.post("/auth/reset-password", json={"token": token, "password": "short"}).status_code == 422
    # A rejected password does not spend the link.
    assert client.post("/auth/reset-password", json={"token": token, "password": "long enough now"}).status_code == 204


def test_resetting_through_the_mailbox_also_verifies_an_unverified_account(client, db, mailer):
    sign_up(client)
    client.post("/auth/forgot-password", json={"email": EMAIL})
    token = mailer.last("reset_password").token
    assert client.post("/auth/reset-password", json={"token": token, "password": "reset before verify"}).status_code == 204
    assert sign_in(client, "reset before verify").status_code == 200


def test_reset_is_throttled_per_account(client, db, mailer):
    verified(client, mailer)
    mailer.sent.clear()
    for _ in range(SEND_LIMIT + 2):
        assert client.post("/auth/forgot-password", json={"email": EMAIL}).status_code == 202
        age_tokens(db, 120)
    assert len([m for m in mailer.sent if m.template == "reset_password"]) == SEND_LIMIT


def test_deleting_an_account_removes_its_links(client, db, mailer):
    verified(client, mailer)
    client.post("/auth/forgot-password", json={"email": EMAIL})
    token = mailer.last("reset_password").token
    session = sign_in(client).json()
    deleted = client.request("DELETE", "/me", json={"password": PASSWORD},
                             headers={"Authorization": f"Bearer {session['token']}"})
    assert deleted.status_code == 204
    with db.transaction() as tx:
        assert tx.scalar("SELECT count(*) FROM auth_token") == 0
        assert tx.scalar("SELECT email_verified_at FROM app_user") is None
    assert client.post("/auth/reset-password", json={"token": token, "password": "ghost password"}).status_code == 422


# --- existing accounts --------------------------------------------------------------------------

def test_migration_backfills_existing_accounts_as_verified(tmp_path):
    """Accounts created before 0002 must still sign in after the release (both engines' files
    carry the same UPDATE; SQLite is exercised here because it needs no server)."""
    import shutil

    from roomly.config import Settings as S
    from roomly.db import Database

    root = S.from_env({}).migrations_dir
    old = tmp_path / "migrations" / "sqlite"
    old.mkdir(parents=True)
    shutil.copy(root / "sqlite" / "0001_init.sql", old)
    database = Database(f"sqlite:///{tmp_path / 'old.sqlite3'}")
    database.open()
    database.migrate(tmp_path / "migrations")
    with database.transaction() as tx:
        tx.exec("INSERT INTO app_user (email, password_hash) VALUES ('old@example.com', 'x')")
        tx.exec("INSERT INTO app_user (email, password_hash, deleted_at) VALUES (NULL, NULL, now())")
    database.migrate(root)                      # the release's migrations
    with database.transaction() as tx:
        created = tx.scalar("SELECT created_at FROM app_user WHERE email IS NOT NULL")
        verified_at = tx.scalar("SELECT email_verified_at FROM app_user WHERE email IS NOT NULL")
        gone = tx.scalar("SELECT email_verified_at FROM app_user WHERE email IS NULL")
    database.close()
    assert verified_at is not None and verified_at == created
    assert gone is None


# --- the mailer ---------------------------------------------------------------------------------

class _Worker(BaseHTTPRequestHandler):
    seen: ClassVar[list[dict]] = []
    status: ClassVar[int] = 202

    def do_POST(self):
        body = self.rfile.read(int(self.headers["Content-Length"]))
        _Worker.seen.append({"path": self.path, "headers": dict(self.headers), "body": body})
        self.send_response(_Worker.status)
        self.end_headers()

    def log_message(self, *args):
        pass


@pytest.fixture
def worker():
    server = HTTPServer(("127.0.0.1", 0), _Worker)
    _Worker.seen, _Worker.status = [], 202
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}", _Worker
    server.shutdown()
    server.server_close()


def test_http_mailer_signs_the_way_the_worker_verifies(worker):
    import hashlib
    import hmac

    url, state = worker
    HttpMailer(url + "/", "shared-secret").send(Message("verify_email", EMAIL, "T" * 43, "Pat"))
    request = state.seen[0]
    assert request["path"] == "/v1/send"
    assert json.loads(request["body"]) == {"template": "verify_email", "to": EMAIL,
                                           "data": {"token": "T" * 43, "display_name": "Pat"}}
    timestamp = request["headers"]["X-Roomly-Timestamp"]
    assert abs(int(timestamp) - dt.datetime.now(dt.UTC).timestamp()) < 5
    expected = hmac.new(b"shared-secret", timestamp.encode() + b"." + request["body"], hashlib.sha256).hexdigest()
    assert request["headers"]["X-Roomly-Signature"] == f"v1={expected}"


def test_http_mailer_omits_a_missing_display_name(worker):
    url, state = worker
    HttpMailer(url, "s").send(Message("reset_password", EMAIL, "T" * 43))
    assert json.loads(state.seen[0]["body"])["data"] == {"token": "T" * 43}


def test_http_mailer_raises_on_rejection_and_on_an_unreachable_host(worker):
    url, state = worker
    state.status = 502
    with pytest.raises(MailError, match="HTTP 502"):
        HttpMailer(url, "s").send(Message("verify_email", EMAIL, "T" * 43))
    with pytest.raises(MailError, match="unreachable"):
        HttpMailer("http://127.0.0.1:9", "s", timeout=1).send(Message("verify_email", EMAIL, "T" * 43))


def test_log_mailer_writes_the_link_where_a_developer_can_click_it(caplog):
    caplog.set_level("INFO", logger="roomly.service.mailer")
    LogMailer("http://localhost:3000/").send(Message("reset_password", EMAIL, "abc-DEF_123"))
    url = next(r.getMessage() for r in caplog.records).split(": ", 1)[1]
    assert urlsplit(url).path == "/reset-password"
    assert parse_qs(urlsplit(url).query) == {"token": ["abc-DEF_123"]}
    assert link(Message("reset_password", EMAIL, "abc-DEF_123")) == "/reset-password?token=abc-DEF_123"


def test_build_mailer_picks_by_mode():
    assert isinstance(build_mailer("log", "http://x", None, None), LogMailer)
    assert isinstance(build_mailer("http", "http://x", "https://m", "s"), HttpMailer)
    with pytest.raises(ValueError):
        build_mailer("smtp", "http://x", None, None)
