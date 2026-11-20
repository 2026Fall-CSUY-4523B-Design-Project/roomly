"""Use-case failures. Services raise these; the controller layer maps ``status`` to the HTTP response."""


class ServiceError(Exception):
    """``code`` is a stable machine-readable reason a client may branch on; the response then
    carries ``detail: {"code", "message"}`` instead of the plain message."""

    status = 400

    def __init__(self, detail: str, code: str | None = None) -> None:
        super().__init__(detail)
        self.detail = detail
        self.code = code


class Unauthorized(ServiceError):
    status = 401


class Forbidden(ServiceError):
    status = 403


class NotFound(ServiceError):
    status = 404


class Conflict(ServiceError):
    status = 409


class Invalid(ServiceError):
    status = 422
