"""Login use case (§8.1.2.1): /auth and /me."""

from fastapi_reborn import APIRouter, Request

from roomly.controller.base import (
    BEARER,
    bearer_token,
    current_user,
    read,
    run,
    services,
)
from roomly.dto.account import (
    DeleteAccountRequest,
    SessionDTO,
    SignInRequest,
    SignUpRequest,
    UserDTO,
)
from roomly.dto.base import body, returns

router = APIRouter(tags=["account"])


@router.post("/auth/sign-up", status_code=201, summary="Create an account and sign in",
             request_body=body(SignUpRequest), responses=returns(SessionDTO, 201))
async def sign_up(request: Request) -> SessionDTO:
    req = await read(request, SignUpRequest)
    return await run(services(request).account.sign_up, req)


@router.post("/auth/sign-in", summary="Sign in with email and password",
             request_body=body(SignInRequest), responses=returns(SessionDTO))
async def sign_in(request: Request) -> SessionDTO:
    req = await read(request, SignInRequest)
    return await run(services(request).account.sign_in, req)


@router.post("/auth/sign-out", status_code=204, summary="Invalidate this session", security=BEARER)
async def sign_out(request: Request) -> None:
    await run(services(request).account.sign_out, bearer_token(request))


@router.get("/me", summary="The signed-in account", security=BEARER, responses=returns(UserDTO))
async def me(request: Request) -> UserDTO:
    user = await current_user(request)
    return services(request).account.me(user)


@router.delete("/me", status_code=204, summary="Delete the account (password confirms)",
               request_body=body(DeleteAccountRequest), security=BEARER)
async def delete_me(request: Request) -> None:
    user = await current_user(request)
    req = await read(request, DeleteAccountRequest)
    await run(services(request).account.delete_account, user, req)
