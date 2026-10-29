"""Controller helpers: the HTTP boundary between fastapi-reborn and the services.

Controllers stay thin: read and validate the request into a DTO, resolve the caller, call
one service method in a worker thread (services use blocking psycopg), return its DTO.
"""

import asyncio
from collections.abc import Callable
from typing import Any
from uuid import UUID

from fastapi_reborn import Request
from fastapi_reborn.params import RequestValidationError
from fastapi_reborn.security import HTTPBearer

from roomly.dto.base import parse
from roomly.entity import User
from roomly.service import Services

BEARER: list[dict[str, list[str]]] = [{"bearerAuth": []}]   # OpenAPI security requirement
MAX_PAGE = 100

_bearer = HTTPBearer()


def services(request: Request) -> Services:
    return request.app.state.services


async def run[T](fn: Callable[..., T], /, *args: Any, **kwargs: Any) -> T:
    """Run a blocking service call off the event loop."""
    return await asyncio.to_thread(fn, *args, **kwargs)


async def read[T](request: Request, cls: type[T]) -> T:
    """The JSON body validated into a request DTO (400 if not JSON, 422 if invalid)."""
    return parse(cls, await request.json())


def bearer_token(request: Request) -> str:
    return _bearer(request).credentials  # type: ignore[union-attr]  # auto_error: never None


async def current_user(request: Request) -> User:
    """The signed-in user, or 401."""
    return await run(services(request).account.authenticate, bearer_token(request))


def _invalid(where: str, name: str, kind: str, msg: str, value: Any) -> RequestValidationError:
    return RequestValidationError([{"type": kind, "loc": [where, name], "msg": msg, "input": value}])


def path_uuid(value: str, name: str) -> UUID:
    try:
        return UUID(value)
    except ValueError:
        raise _invalid("path", name, "uuid_parsing", "Input should be a valid UUID", value) from None


def query_uuid(value: str | None, name: str) -> UUID | None:
    if value is None:
        return None
    try:
        return UUID(value)
    except ValueError:
        raise _invalid("query", name, "uuid_parsing", "Input should be a valid UUID", value) from None


def paging(limit: int, offset: int, max_limit: int = MAX_PAGE) -> tuple[int, int]:
    if not 1 <= limit <= max_limit:
        raise _invalid("query", "limit", "less_than_equal", f"limit must be between 1 and {max_limit}", limit)
    if offset < 0:
        raise _invalid("query", "offset", "greater_than_equal", "offset must not be negative", offset)
    return limit, offset


def choice(value: str, name: str, allowed: tuple[str, ...]) -> str:
    if value not in allowed:
        raise _invalid("query", name, "literal_error", "Input should be " + " or ".join(map(repr, allowed)), value)
    return value
