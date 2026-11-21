"""AccountService (§9.1 control class): sign-up, email verification, sign-in, password reset, sign-out,
session lookup, deletion (R-1.1, R-1.4)."""

import datetime as dt
import hashlib
import logging
import secrets

from roomly.db import Database, IntegrityError, Tx
from roomly.dto.account import (
    DeleteAccountRequest,
    EmailRequest,
    ResetPasswordRequest,
    SessionDTO,
    SignInRequest,
    SignUpRequest,
    SignUpResult,
    TokenRequest,
    UserDTO,
)
from roomly.entity import User
from roomly.mapper.account_mapper import AuthTokenMapper, SessionMapper, UserMapper
from roomly.mapper.comparison_mapper import ComparisonMapper
from roomly.mapper.group_mapper import GroupMapper, InvitationMapper, MembershipMapper
from roomly.mapper.listing_mapper import (
    DuplicateMapper,
    ReportMapper,
    SourceRecordMapper,
)
from roomly.mapper.notification_mapper import NotificationMapper
from roomly.mapper.room_mapper import PollMapper, ReactionMapper
from roomly.mapper.search_mapper import CommuteMapper, SavedSearchMapper
from roomly.service.errors import Conflict, Forbidden, Invalid, Unauthorized
from roomly.service.mailer import LogMailer, Mailer, MailError, Message

logger = logging.getLogger(__name__)

SESSION_LIFETIME = dt.timedelta(days=7)
VERIFY_LIFETIME = dt.timedelta(hours=24)
RESET_LIFETIME = dt.timedelta(minutes=30)
LIFETIME = {"verify_email": VERIFY_LIFETIME, "reset_password": RESET_LIFETIME}
# Per account and kind: one link a minute, three an hour. Counted from auth_token rows.
SEND_COOLDOWN = dt.timedelta(seconds=60)
SEND_WINDOW = dt.timedelta(hours=1)
SEND_LIMIT = 3


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
    def __init__(self, db: Database, mailer: Mailer | None = None) -> None:
        self.db = db
        self.mailer = mailer or LogMailer("http://localhost:3000")

    def sign_up(self, req: SignUpRequest) -> SignUpResult:
        """Create the account, unverified, and email the confirmation link. No session yet."""
        encoded = password_hash(req.password)
        try:
            with self.db.transaction() as tx:
                users = UserMapper(tx)
                if users.find_by_email(req.email):
                    raise Conflict("An account with this email already exists.")
                user = users.insert(req.email, encoded, req.display_name)
                message = self._issue(tx, user, "verify_email")
        except IntegrityError:
            # Confirm a concurrent sign-up after rollback; preserve unrelated DB failures.
            with self.db.transaction() as tx:
                duplicate = UserMapper(tx).find_by_email(req.email)
            if duplicate is not None:
                raise Conflict("An account with this email already exists.") from None
            raise
        logger.info("sign-up user=%s", user.id)
        return SignUpResult(email=req.email, verification_sent=message is not None and self.deliver(message))

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
            if current.email_verified_at is None:
                # Said only after the password matched, so it does not reveal who has an account.
                logger.info("sign-in blocked, email not verified user=%s", current.id)
                raise Forbidden("Confirm your email address before signing in. Check your inbox, "
                                "or ask for a new link.", "email_not_verified")
            return self._session(SessionMapper(tx), current)

    # --- emailed links ---------------------------------------------------------------

    def resend_verification(self, req: EmailRequest) -> Message | None:
        """A new confirmation link for an unverified account. ``None`` for anything else (the
        caller answers the same either way); the returned message is sent after the response."""
        with self.db.transaction() as tx:
            user = UserMapper(tx).find_by_email(req.email)
            if user is None or user.email_verified_at is not None:
                return None
            return self._issue(tx, user, "verify_email")

    def verify_email(self, req: TokenRequest) -> None:
        with self.db.transaction() as tx:
            token = AuthTokenMapper(tx).find_usable("verify_email", token_hash(req.token))
            if token is None or not AuthTokenMapper(tx).consume(token.id):
                raise Invalid("This confirmation link is invalid or has expired.", "invalid_token")
            UserMapper(tx).mark_verified(token.user_id)
        logger.info("email verified user=%s", token.user_id)

    def forgot_password(self, req: EmailRequest) -> Message | None:
        with self.db.transaction() as tx:
            user = UserMapper(tx).find_by_email(req.email)
            if user is None:
                return None
            return self._issue(tx, user, "reset_password")

    def reset_password(self, req: ResetPasswordRequest) -> None:
        """Set a new password, sign the account out everywhere and spend every other reset link.
        Receiving the link proves the mailbox, so an unverified account is verified too."""
        encoded = password_hash(req.password)
        with self.db.transaction() as tx:
            tokens = AuthTokenMapper(tx)
            token = tokens.find_usable("reset_password", token_hash(req.token))
            if token is None or not tokens.consume(token.id):
                raise Invalid("This reset link is invalid or has expired.", "invalid_token")
            users = UserMapper(tx)
            users.lock(token.user_id)
            users.set_password(token.user_id, encoded)
            users.mark_verified(token.user_id)
            revoked = SessionMapper(tx).delete_all_for_user(token.user_id)
            tokens.consume_all(token.user_id, "reset_password")
        logger.info("password reset user=%s sessions_revoked=%s", token.user_id, revoked)

    def deliver(self, message: Message) -> bool:
        """Send after the transaction committed. A failure never reaches the caller as an error:
        the link is discarded (it never arrived, so it must not eat the user's send limit) and the
        caller learns only that nothing was sent."""
        try:
            self.mailer.send(message)
            return True
        except MailError as exc:
            logger.warning("mail %s not sent: %s", message.template, exc)
        except Exception:
            logger.exception("mail %s failed unexpectedly", message.template)
        with self.db.transaction() as tx:
            AuthTokenMapper(tx).discard(token_hash(message.token))
        return False

    def _issue(self, tx: Tx, user: User, kind: str) -> Message | None:
        """Store a fresh single-use link for ``user`` unless they asked too recently. The user row
        is locked so two concurrent requests cannot both slip under the limit."""
        UserMapper(tx).lock(user.id)
        tokens = AuthTokenMapper(tx)
        now = dt.datetime.now(dt.UTC)
        if tokens.count_since(user.id, kind, now - SEND_COOLDOWN) or \
                tokens.count_since(user.id, kind, now - SEND_WINDOW) >= SEND_LIMIT:
            logger.info("%s link throttled user=%s", kind, user.id)
            return None
        token = secrets.token_urlsafe(32)
        tokens.insert(user.id, kind, token_hash(token), now + LIFETIME[kind])
        logger.info("%s link issued user=%s", kind, user.id)
        assert user.email is not None
        return Message(kind, user.email, token, user.display_name)

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
        if not password_matches(req.password, user.password_hash):
            raise Unauthorized("Invalid password.")
        with self.db.transaction() as tx:
            current = UserMapper(tx).lock(user.id)
            if current is None or current.deleted_at is not None:
                raise Unauthorized("This account no longer exists.")
            memberships = MembershipMapper(tx).current_for_user(user.id)
            owners = [m for m in memberships if m.is_owner]
            for membership in owners:
                if MembershipMapper(tx).count_current(membership.group_id) > 1:
                    raise Conflict("Transfer ownership of your groups before deleting the account.")
            for membership in owners:
                GroupMapper(tx).delete(membership.group_id)
            MembershipMapper(tx).end_all_for_user(user.id)

            # Personal rows: nothing left to read, nothing left to notify.
            SessionMapper(tx).delete_all_for_user(user.id)
            AuthTokenMapper(tx).delete_all_for_user(user.id)
            NotificationMapper(tx).delete_all_for_user(user.id)
            CommuteMapper(tx).delete_all_for_user(user.id)
            SavedSearchMapper(tx).delete_all_for_user(user.id)
            ComparisonMapper(tx).delete_personal_for_user(user.id)
            ReactionMapper(tx).delete_all_for_user(user.id)
            PollMapper(tx).delete_votes_for_user(user.id)

            # Shared content keeps the id (so it can say "Deleted user") but loses the link.
            SourceRecordMapper(tx).clear_submitter(user.id)
            ReportMapper(tx).clear_reporter(user.id)
            ReportMapper(tx).clear_resolver(user.id)
            InvitationMapper(tx).clear_inviter(user.id)
            if current.email is not None:
                InvitationMapper(tx).delete_for_email(current.email)
            ComparisonMapper(tx).clear_saved_by(user.id)
            PollMapper(tx).clear_creator(user.id)
            DuplicateMapper(tx).clear_reviewer(user.id)
            UserMapper(tx).scrub(user.id)
