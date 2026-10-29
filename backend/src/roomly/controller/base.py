"""Controller helpers: the HTTP boundary between FastAPI and the services.

Controllers stay thin: FastAPI validates path, query and body into typed values and DTOs (422),
the dependencies below resolve the services and the caller (401), and the endpoint calls one
service method and returns its DTO. Endpoints and dependencies that reach the database are
plain ``def``: FastAPI runs them in its thread pool, because the database drivers block.
"""

from typing import Annotated, Any

from fastapi import Depends, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ValidationError

from roomly import fixtures
from roomly.entity import User
from roomly.service import Services

MAX_PAGE = 100

_bearer = HTTPBearer(scheme_name="bearerAuth")   # 401 + WWW-Authenticate: Bearer without a token


def services(request: Request) -> Services:
    return request.app.state.services


def bearer_token(credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)]) -> str:
    return credentials.credentials


def current_user(request: Request, token: Annotated[str, Depends(bearer_token)]) -> User:
    """The signed-in user, or 401. While ``authenticate`` is a stub and fixtures are on, any
    bearer token is the sample user, so the route still validates its request."""
    try:
        return services(request).account.authenticate(token)
    except NotImplementedError:
        if not request.app.state.settings.fixtures:
            raise
        return fixtures.USER


Svc = Annotated[Services, Depends(services)]
Token = Annotated[str, Depends(bearer_token)]
CurrentUser = Annotated[User, Depends(current_user)]
Limit = Annotated[int, Query(ge=1, le=MAX_PAGE)]
Offset = Annotated[int, Query(ge=0)]


def from_query[T: BaseModel](cls: type[T], values: dict[str, Any]) -> T:
    """Query parameters validated into a DTO; its errors are 422s located in the query."""
    try:
        return cls.model_validate(values)
    except ValidationError as exc:
        raise RequestValidationError(
            [{**e, "loc": ("query", *e["loc"])} for e in exc.errors(include_url=False)]) from None
