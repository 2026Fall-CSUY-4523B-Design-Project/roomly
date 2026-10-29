"""DTOs for Login (§8.1.2.1, R-1.1, R-1.4)."""

import datetime as dt
from dataclasses import dataclass
from uuid import UUID

from roomly.dto.base import EMAIL_PATTERN, rule
from roomly.entity import User


@dataclass(frozen=True)
class SignUpRequest:
    email: str = rule(pattern=EMAIL_PATTERN, lower=True, max_len=254)
    password: str = rule(strip=False, min_len=8, max_len=128)
    display_name: str | None = rule(default=None, min_len=1, max_len=60)


@dataclass(frozen=True)
class SignInRequest:
    email: str = rule(lower=True, min_len=1, max_len=254)
    password: str = rule(strip=False, min_len=1, max_len=128)


@dataclass(frozen=True)
class DeleteAccountRequest:
    """Deletion is confirmed by re-entering the password."""

    password: str = rule(strip=False, min_len=1, max_len=128)


@dataclass(frozen=True)
class UserDTO:
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


@dataclass(frozen=True)
class SessionDTO:
    """Returned once at sign-up/sign-in. Send ``token`` as ``Authorization: Bearer <token>``."""

    token: str
    expires_at: dt.datetime
    user: UserDTO
