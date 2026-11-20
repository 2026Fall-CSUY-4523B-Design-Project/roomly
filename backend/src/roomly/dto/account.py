"""DTOs for Login (§8.1.2.1, R-1.1, R-1.4)."""

import datetime as dt
from typing import Annotated
from uuid import UUID

from pydantic import Field, StringConstraints

from roomly.dto.base import DTO, Email, Secret
from roomly.entity import User


class SignUpRequest(DTO):
    email: Email
    password: Secret = Field(min_length=8, max_length=128)
    display_name: str | None = Field(default=None, min_length=1, max_length=60)


class SignInRequest(DTO):
    email: Annotated[str, StringConstraints(to_lower=True)] = Field(min_length=1, max_length=254)
    password: Secret = Field(min_length=1, max_length=128)


class EmailRequest(DTO):
    """Resend a verification email or start a password reset; the answer never says whether the account exists."""

    email: Email


class TokenRequest(DTO):
    token: str = Field(min_length=16, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")


class ResetPasswordRequest(TokenRequest):
    password: Secret = Field(min_length=8, max_length=128)


class DeleteAccountRequest(DTO):
    """Deletion is confirmed by re-entering the password."""

    password: Secret = Field(min_length=1, max_length=128)


class UserDTO(DTO):
    id: UUID
    email: str
    display_name: str | None
    role: str
    created_at: dt.datetime

    @classmethod
    def from_entity(cls, user: User) -> UserDTO:
        assert user.email is not None, "deleted accounts are never serialized as users"
        return cls(id=user.id, email=user.email, display_name=user.display_name, role=user.role,
                   created_at=user.created_at)


class SignUpResult(DTO):
    """Sign-up creates the account but not a session: the person confirms their email first.

    ``verification_sent`` is false when the mail service did not accept the message; the account
    exists and ``POST /auth/verify-email/resend`` tries again.
    """

    email: str
    verification_sent: bool


class SessionDTO(DTO):
    """Returned once at sign-up/sign-in. Send ``token`` as ``Authorization: Bearer <token>``."""

    token: str
    expires_at: dt.datetime
    user: UserDTO
