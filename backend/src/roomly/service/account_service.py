"""AccountService (§9.1 control class): sign-up, sign-in, sign-out, session lookup, deletion (R-1.1, R-1.4)."""

import datetime as dt
import hashlib
import secrets

from roomly.db import Database, IntegrityError
from roomly.dto.account import (
    DeleteAccountRequest,
    SessionDTO,
    SignInRequest,
    SignUpRequest,
    UserDTO,
)
from roomly.entity import User
from roomly.mapper.account_mapper import SessionMapper, UserMapper
from roomly.service.errors import Conflict, Unauthorized

SESSION_LIFETIME = dt.timedelta(days=7)


def password_hash(password: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=32768, r=8, p=3,
                            maxmem=64 * 1024 * 1024).hex()
    return f"scrypt${salt}${digest}"


def password_matches(password: str, encoded: str | None) -> bool:
    if not encoded:
        return False
    algorithm, salt, _ = encoded.split("$")
    return algorithm == "scrypt" and secrets.compare_digest(password_hash(password, salt), encoded)


# Equal-cost verification for unknown accounts.
_DUMMY_HASH = password_hash(secrets.token_urlsafe(32))


def token_hash(token: str) -> bytes:
    return hashlib.sha256(token.encode()).digest()


class AccountService:
    def __init__(self, db: Database) -> None:
        self.db = db

    def sign_up(self, req: SignUpRequest) -> SessionDTO:
        encoded = password_hash(req.password)
        try:
            with self.db.transaction() as tx:
                users = UserMapper(tx)
                if users.find_by_email(req.email):
                    raise Conflict("An account with this email already exists.")
                user = users.insert(req.email, encoded, req.display_name)
                return self._session(SessionMapper(tx), user)
        except IntegrityError:
            # Confirm a concurrent sign-up after rollback; preserve unrelated DB failures.
            with self.db.transaction() as tx:
                duplicate = UserMapper(tx).find_by_email(req.email)
            if duplicate is not None:
                raise Conflict("An account with this email already exists.") from None
            raise

    def sign_in(self, req: SignInRequest) -> SessionDTO:
        with self.db.transaction() as tx:
            user = UserMapper(tx).find_by_email(req.email)
        valid = password_matches(req.password, user.password_hash if user else _DUMMY_HASH)
        if not valid or user is None:
            raise Unauthorized("Invalid email or password.")
        with self.db.transaction() as tx:
            current = UserMapper(tx).lock(user.id)
            if current is None or current.deleted_at is not None or current.password_hash != user.password_hash:
                raise Unauthorized("Invalid email or password.")
            return self._session(SessionMapper(tx), current)

    def sign_out(self, token: str) -> None:
        with self.db.transaction() as tx:
            SessionMapper(tx).revoke(token_hash(token))

    def authenticate(self, token: str) -> User:
        """The live user behind a bearer token, or 401."""
        with self.db.transaction() as tx:
            user = SessionMapper(tx).find_user_by_token(token_hash(token))
        if user is None:
            raise Unauthorized("Your session has expired or is invalid. Please sign in again.")
        return user

    def me(self, user: User) -> UserDTO:
        return UserDTO.from_entity(user)

    @staticmethod
    def _session(mapper: SessionMapper, user: User) -> SessionDTO:
        token = secrets.token_urlsafe(32)
        expires_at = dt.datetime.now(dt.UTC) + SESSION_LIFETIME
        mapper.insert(user.id, token_hash(token), expires_at)
        return SessionDTO(token=token, expires_at=expires_at, user=UserDTO.from_entity(user))

    def delete_account(self, user: User, req: DeleteAccountRequest) -> None:
        """R-1.4 / §8.1.2.1 alt. flows 2-3: blocked while the user owns a group with other members."""
        raise NotImplementedError
