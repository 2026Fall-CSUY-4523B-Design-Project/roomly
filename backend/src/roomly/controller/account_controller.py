"""Login use case (§8.1.2.1): /auth and /me."""

from fastapi import APIRouter

from roomly.controller.base import CurrentUser, Svc, Token
from roomly.dto.account import (
    DeleteAccountRequest,
    SessionDTO,
    SignInRequest,
    SignUpRequest,
    UserDTO,
)

router = APIRouter(tags=["account"])


@router.post("/auth/sign-up", status_code=201, summary="Create an account and sign in")
def sign_up(req: SignUpRequest, svc: Svc) -> SessionDTO:
    return svc.account.sign_up(req)


@router.post("/auth/sign-in", summary="Sign in with email and password")
def sign_in(req: SignInRequest, svc: Svc) -> SessionDTO:
    return svc.account.sign_in(req)


@router.post("/auth/sign-out", status_code=204, summary="Invalidate this session")
def sign_out(token: Token, svc: Svc) -> None:
    svc.account.sign_out(token)


@router.get("/me", summary="The signed-in account")
def me(user: CurrentUser, svc: Svc) -> UserDTO:
    return svc.account.me(user)


@router.delete("/me", status_code=204, summary="Delete the account (password confirms)")
def delete_me(req: DeleteAccountRequest, user: CurrentUser, svc: Svc) -> None:
    svc.account.delete_account(user, req)
