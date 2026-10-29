"""AccountService (§9.1 control class): sign-up, sign-in, sign-out, session lookup, deletion (R-1.1, R-1.4)."""

import datetime as dt
import hashlib
import logging
import secrets

from fastapi_reborn.security import hash_password, verify_password

from roomly.db import Database
from roomly.dto.account import (
    DeleteAccountRequest,
    SessionDTO,
    SignInRequest,
    SignUpRequest,
    UserDTO,
)
from roomly.entity import User
from roomly.mapper import (
    CommuteMapper,
    ComparisonMapper,
    GroupMapper,
    InvitationMapper,
    MembershipMapper,
    NotificationMapper,
    SavedSearchMapper,
    SessionMapper,
    SourceRecordMapper,
    UserMapper,
)
from roomly.service.errors import Conflict, Forbidden, Unauthorized

logger = logging.getLogger(__name__)


def token_digest(token: str) -> bytes:
    """Sessions store only sha256(token): a leaked table does not leak usable tokens."""
    return hashlib.sha256(token.encode("utf-8")).digest()


class AccountService:
    def __init__(self, db: Database, *, session_ttl: dt.timedelta, password_iterations: int) -> None:
        self.db = db
        self.session_ttl = session_ttl
        self.password_iterations = password_iterations
        # verified against when the email is unknown, so both failures take the same time
        self._dummy_hash = hash_password(secrets.token_hex(8), iterations=password_iterations)

    def sign_up(self, req: SignUpRequest) -> SessionDTO:
        password_hash = hash_password(req.password, iterations=self.password_iterations)
        with self.db.transaction() as conn:
            users = UserMapper(conn)
            if users.find_by_email(req.email) is not None:
                raise Conflict("an account with this email already exists")
            user = users.insert(req.email, password_hash, req.display_name)
            session = self._open_session(SessionMapper(conn), user)
        logger.info("account created user=%s", user.id)
        return session

    def sign_in(self, req: SignInRequest) -> SessionDTO:
        with self.db.transaction() as conn:
            user = UserMapper(conn).find_by_email(req.email)
            ok = verify_password(req.password, user.password_hash if user and user.password_hash else self._dummy_hash)
            if user is None or not ok:
                logger.info("sign-in rejected")  # no email in logs
                raise Unauthorized("invalid email or password")
            session = self._open_session(SessionMapper(conn), user)
        logger.info("signed in user=%s", user.id)
        return session

    def sign_out(self, token: str) -> None:
        with self.db.transaction() as conn:
            SessionMapper(conn).revoke(token_digest(token))

    def authenticate(self, token: str) -> User:
        """The live user behind a bearer token, or 401."""
        with self.db.transaction() as conn:
            user = SessionMapper(conn).find_user_by_token(token_digest(token))
        if user is None:
            raise Unauthorized("session expired or invalid")
        return user

    def me(self, user: User) -> UserDTO:
        return UserDTO.from_entity(user)

    def delete_account(self, user: User, req: DeleteAccountRequest) -> None:
        """R-1.4 / §8.1.2.1 alt. flows 2-3: blocked while the user owns a group with other members."""
        with self.db.transaction() as conn:
            fresh = UserMapper(conn).lock(user.id)
            if fresh is None or fresh.password_hash is None or not verify_password(req.password, fresh.password_hash):
                raise Forbidden("password confirmation failed")
            memberships = MembershipMapper(conn)
            groups = GroupMapper(conn)
            blocking = []
            for m in memberships.current_for_user(user.id):
                if not m.is_owner:
                    continue
                if memberships.count_current(m.group_id) > 1:
                    blocking.append(str(m.group_id))
                else:
                    groups.delete(m.group_id)  # sole member: nobody else can see its content
            if blocking:
                raise Conflict("transfer ownership of your groups before deleting the account: " + ", ".join(blocking))
            memberships.end_all_for_user(user.id)
            SessionMapper(conn).delete_all_for_user(user.id)
            CommuteMapper(conn).delete_all_for_user(user.id)
            SavedSearchMapper(conn).delete_all_for_user(user.id)
            NotificationMapper(conn).delete_all_for_user(user.id)
            ComparisonMapper(conn).delete_personal_for_user(user.id)
            assert fresh.email is not None
            InvitationMapper(conn).delete_pending_for_email(fresh.email)
            SourceRecordMapper(conn).clear_submitter(user.id)
            UserMapper(conn).scrub(user.id)
        logger.info("account deleted user=%s", user.id)

    def _open_session(self, sessions: SessionMapper, user: User) -> SessionDTO:
        token = secrets.token_urlsafe(32)
        session = sessions.insert(user.id, token_digest(token), dt.datetime.now(dt.UTC) + self.session_ttl)
        return SessionDTO(token=token, expires_at=session.expires_at, user=UserDTO.from_entity(user))
