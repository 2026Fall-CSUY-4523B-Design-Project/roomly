"""Login use case (§8.1.2.1): /auth and /me."""

from fastapi import APIRouter, BackgroundTasks, Response

from roomly.controller.base import CurrentUser, Svc, Token
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

router = APIRouter(tags=["account"])


@router.post("/auth/sign-up", status_code=201, summary="Create an account and email a confirmation link")
def sign_up(req: SignUpRequest, svc: Svc) -> SignUpResult:
    return svc.account.sign_up(req)


@router.post("/auth/verify-email", status_code=204, summary="Confirm an email address with the emailed token")
def verify_email(req: TokenRequest, svc: Svc) -> None:
    svc.account.verify_email(req)


@router.post("/auth/verify-email/resend", status_code=202, summary="Email a new confirmation link")
def resend_verification(req: EmailRequest, svc: Svc, tasks: BackgroundTasks) -> Response:
    """202 whether or not the address belongs to an unverified account."""
    message = svc.account.resend_verification(req)
    if message:
        tasks.add_task(svc.account.deliver, message)
    return Response(status_code=202)


@router.post("/auth/forgot-password", status_code=202, summary="Email a password reset link")
def forgot_password(req: EmailRequest, svc: Svc, tasks: BackgroundTasks) -> Response:
    """202 whether or not the address belongs to an account."""
    message = svc.account.forgot_password(req)
    if message:
        tasks.add_task(svc.account.deliver, message)
    return Response(status_code=202)


@router.post("/auth/reset-password", status_code=204,
             summary="Set a new password with the emailed token and sign out everywhere")
def reset_password(req: ResetPasswordRequest, svc: Svc) -> None:
    svc.account.reset_password(req)


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
