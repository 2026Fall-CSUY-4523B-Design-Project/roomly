"""AccountService (§9.1 control class): sign-up, sign-in, sign-out, session lookup, deletion (R-1.1, R-1.4)."""

from roomly.db import Database
from roomly.dto.account import (
    DeleteAccountRequest,
    SessionDTO,
    SignInRequest,
    SignUpRequest,
    UserDTO,
)
from roomly.entity import User


class AccountService:
    def __init__(self, db: Database) -> None:
        self.db = db

    def sign_up(self, req: SignUpRequest) -> SessionDTO:
        raise NotImplementedError

    def sign_in(self, req: SignInRequest) -> SessionDTO:
        raise NotImplementedError

    def sign_out(self, token: str) -> None:
        raise NotImplementedError

    def authenticate(self, token: str) -> User:
        """The live user behind a bearer token, or 401."""
        raise NotImplementedError

    def me(self, user: User) -> UserDTO:
        raise NotImplementedError

    def delete_account(self, user: User, req: DeleteAccountRequest) -> None:
        """R-1.4 / §8.1.2.1 alt. flows 2-3: blocked while the user owns a group with other members."""
        raise NotImplementedError
