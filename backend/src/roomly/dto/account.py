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


class SessionDTO(DTO):
    """Returned once at sign-up/sign-in. Send ``token`` as ``Authorization: Bearer <token>``."""

    token: str
    expires_at: dt.datetime
    user: UserDTO
