"""Use-case failures. Services raise these; the controller layer maps ``status`` to the HTTP response."""


class ServiceError(Exception):
    status = 400

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


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
