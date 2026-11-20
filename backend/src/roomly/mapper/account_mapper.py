"""SQL for app_user and user_session."""

import datetime as dt
from uuid import UUID

from roomly.entity import AuthToken, Session, User
from roomly.mapper.base import Mapper, columns

_USER = columns(User)
_USER_U = columns(User, "u")
_SESSION = columns(Session)
_TOKEN = columns(AuthToken)
_TOKEN_T = columns(AuthToken, "t")


class UserMapper(Mapper):
    def insert(self, email: str, password_hash: str, display_name: str | None, *, verified: bool = False) -> User:
        """New accounts start unverified; the seed and tests pass ``verified=True``."""
        sql = f"""
            INSERT INTO app_user (email, password_hash, display_name, email_verified_at)
            VALUES (%(email)s, %(password_hash)s, %(display_name)s, %(verified_at)s)
            RETURNING {_USER}"""
        params = {"email": email, "password_hash": password_hash, "display_name": display_name,
                  "verified_at": dt.datetime.now(dt.UTC) if verified else None}
        user = self._one(User, sql, params)
        assert user is not None
        return user

    def find(self, user_id: UUID) -> User | None:
        return self._one(User, f"SELECT {_USER} FROM app_user WHERE id = %(id)s", {"id": user_id})

    def find_by_email(self, email: str) -> User | None:
        """Live accounts only: deleted accounts have no email."""
        return self._one(User, f"SELECT {_USER} FROM app_user WHERE email = %(email)s", {"email": email})

    def lock(self, user_id: UUID) -> User | None:
        return self._one(User, f"SELECT {_USER} FROM app_user WHERE id = %(id)s FOR UPDATE", {"id": user_id})

    def update_notification_settings(
        self,
        user_id: UUID,
        *,
        kinds: list[str],
        email: bool,
        digest: bool,
        quiet_start: dt.time | None,
        quiet_end: dt.time | None,
    ) -> User:
        sql = f"""
            UPDATE app_user
               SET notify_kinds = %(kinds)s, notify_email = %(email)s, notify_digest = %(digest)s,
                   quiet_start = %(quiet_start)s, quiet_end = %(quiet_end)s
             WHERE id = %(id)s
            RETURNING {_USER}"""
        params = {"id": user_id, "kinds": kinds, "email": email, "digest": digest,
                  "quiet_start": quiet_start, "quiet_end": quiet_end}
        user = self._one(User, sql, params)
        assert user is not None
        return user

    def mark_verified(self, user_id: UUID) -> int:
        """Idempotent: the first confirmation wins, later ones leave the timestamp alone."""
        return self._exec(
            "UPDATE app_user SET email_verified_at = now() WHERE id = %(id)s AND email_verified_at IS NULL",
            {"id": user_id},
        )

    def set_password(self, user_id: UUID, password_hash: str) -> int:
        return self._exec(
            "UPDATE app_user SET password_hash = %(hash)s WHERE id = %(id)s AND deleted_at IS NULL",
            {"id": user_id, "hash": password_hash},
        )

    def set_role(self, email: str, role: str) -> User | None:
        sql = f"UPDATE app_user SET role = %(role)s WHERE email = %(email)s RETURNING {_USER}"
        return self._one(User, sql, {"email": email, "role": role})

    def scrub(self, user_id: UUID) -> int:
        """R-1.4: keep the id (for "Deleted user" attribution), drop every personal field."""
        return self._exec(
            """
            UPDATE app_user
               SET email = NULL, password_hash = NULL, display_name = NULL, email_verified_at = NULL, preferences = '{}',
                   quiet_start = NULL, quiet_end = NULL, notify_email = false, deleted_at = now()
             WHERE id = %(id)s AND deleted_at IS NULL""",
            {"id": user_id},
        )


class SessionMapper(Mapper):
    def insert(self, user_id: UUID, token_hash: bytes, expires_at: dt.datetime) -> Session:
        sql = f"""
            INSERT INTO user_session (user_id, token_hash, expires_at)
            VALUES (%(user_id)s, %(token_hash)s, %(expires_at)s)
            RETURNING {_SESSION}"""
        session = self._one(Session, sql, {"user_id": user_id, "token_hash": token_hash, "expires_at": expires_at})
        assert session is not None
        return session

    def find_user_by_token(self, token_hash: bytes) -> User | None:
        """The live account behind an unexpired, unrevoked session token."""
        sql = f"""
            SELECT {_USER_U}
              FROM user_session s JOIN app_user u ON u.id = s.user_id
             WHERE s.token_hash = %(token_hash)s AND s.revoked_at IS NULL
               AND s.expires_at > now() AND u.deleted_at IS NULL"""
        return self._one(User, sql, {"token_hash": token_hash})

    def revoke(self, token_hash: bytes) -> int:
        return self._exec(
            "UPDATE user_session SET revoked_at = now() WHERE token_hash = %(h)s AND revoked_at IS NULL",
            {"h": token_hash},
        )

    def delete_all_for_user(self, user_id: UUID) -> int:
        return self._exec("DELETE FROM user_session WHERE user_id = %(id)s", {"id": user_id})


class AuthTokenMapper(Mapper):
    def insert(self, user_id: UUID, kind: str, token_hash: bytes, expires_at: dt.datetime) -> AuthToken:
        sql = f"""
            INSERT INTO auth_token (user_id, kind, token_hash, expires_at)
            VALUES (%(user_id)s, %(kind)s, %(token_hash)s, %(expires_at)s)
            RETURNING {_TOKEN}"""
        token = self._one(AuthToken, sql, {"user_id": user_id, "kind": kind, "token_hash": token_hash,
                                           "expires_at": expires_at})
        assert token is not None
        return token

    def find_usable(self, kind: str, token_hash: bytes) -> AuthToken | None:
        """An unexpired, unconsumed link of this kind whose account is still live."""
        sql = f"""
            SELECT {_TOKEN_T}
              FROM auth_token t JOIN app_user u ON u.id = t.user_id
             WHERE t.token_hash = %(h)s AND t.kind = %(kind)s AND t.consumed_at IS NULL
               AND t.expires_at > now() AND u.deleted_at IS NULL"""
        return self._one(AuthToken, sql, {"h": token_hash, "kind": kind})

    def consume(self, token_id: UUID) -> int:
        """1 for the caller that spent the link, 0 for a concurrent caller that got there first."""
        return self._exec(
            "UPDATE auth_token SET consumed_at = now() WHERE id = %(id)s AND consumed_at IS NULL",
            {"id": token_id},
        )

    def consume_all(self, user_id: UUID, kind: str) -> int:
        return self._exec(
            "UPDATE auth_token SET consumed_at = now()"
            " WHERE user_id = %(id)s AND kind = %(kind)s AND consumed_at IS NULL",
            {"id": user_id, "kind": kind},
        )

    def discard(self, token_hash: bytes) -> int:
        """Drop a link that never reached the user, so it does not count against their send limit."""
        return self._exec("DELETE FROM auth_token WHERE token_hash = %(h)s", {"h": token_hash})

    def count_since(self, user_id: UUID, kind: str, since: dt.datetime) -> int:
        return self._scalar(
            "SELECT count(*) FROM auth_token WHERE user_id = %(id)s AND kind = %(kind)s AND created_at > %(since)s",
            {"id": user_id, "kind": kind, "since": since}, int)

    def delete_all_for_user(self, user_id: UUID) -> int:
        return self._exec("DELETE FROM auth_token WHERE user_id = %(id)s", {"id": user_id})
