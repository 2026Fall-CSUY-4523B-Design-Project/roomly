"""Exception -> HTTP response mapping for the whole API."""

import logging

from fastapi import FastAPI, Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute

from roomly.db import IntegrityError, UnavailableError, constraint_name, error_message
from roomly.fixtures import FIXTURES
from roomly.service.errors import ServiceError

logger = logging.getLogger(__name__)


def _service_error(request: Request, exc: Exception) -> Response:
    assert isinstance(exc, ServiceError)
    headers = {"WWW-Authenticate": "Bearer"} if exc.status == 401 else None
    return JSONResponse({"detail": exc.detail}, status_code=exc.status, headers=headers)


def _integrity_error(request: Request, exc: Exception) -> Response:
    """A database invariant caught what the service did not (a race, or a missing check)."""
    constraint = constraint_name(exc)
    logger.warning("integrity error on %s %s constraint=%s", request.method, request.url.path, constraint)
    return JSONResponse({"detail": error_message(exc), "constraint": constraint}, status_code=409)


def _database_unavailable(request: Request, exc: Exception) -> Response:
    logger.error("database unavailable on %s %s: %s", request.method, request.url.path, type(exc).__name__)
    return JSONResponse({"detail": "the database is unavailable, try again shortly"}, status_code=503)


def _not_implemented(request: Request, exc: Exception) -> Response:
    """A service method that is still a stub: its roomly.fixtures sample when fixtures are on, else 501."""
    route = request.scope.get("route")
    if request.app.state.settings.fixtures and isinstance(route, APIRoute):
        key = f"{request.method} {route.path}"
        status = route.status_code or 200
        if status == 204:
            response = Response(status_code=204)
        elif key in FIXTURES:
            response = JSONResponse(jsonable_encoder(FIXTURES[key]), status_code=status)
        else:
            response = None
        if response is not None:
            logger.debug("fixture response for %s", key)
            response.headers["X-Roomly-Fixture"] = "1"
            return response
    logger.info("not implemented: %s %s", request.method, request.url.path)
    return JSONResponse({"detail": "not implemented yet"}, status_code=501)


def install_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ServiceError, _service_error)
    app.add_exception_handler(NotImplementedError, _not_implemented)
    for cls in IntegrityError:
        app.add_exception_handler(cls, _integrity_error)
    for cls in UnavailableError:
        app.add_exception_handler(cls, _database_unavailable)
