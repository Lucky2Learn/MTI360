"""Application errors and the API error envelope (T01-01; ARCHITECTURE.md §36).

Every error response has the same shape::

    {"error": {"code": "NOT_FOUND", "message": "…", "details": [], "request_id": "…"}}

Messages are written for end users. Responses never contain stack traces,
SQL, input values, infrastructure details or credentials (CLAUDE.md §37);
diagnostics go to the structured log together with the request ID.

Services raise the :class:`AppError` subclasses below. FastAPI validation
errors, unknown routes, optimistic-locking conflicts and unexpected exceptions
are converted to the same envelope by :func:`install_exception_handlers`.
"""

import logging
import uuid
from collections.abc import Sequence
from typing import Any, ClassVar

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm.exc import StaleDataError
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("app.errors")

REQUEST_ID_HEADER = "X-Request-ID"


class ErrorDetail(BaseModel):
    """One problem, usually with a field. Never contains the submitted value."""

    model_config = ConfigDict(frozen=True)

    field: str | None = None
    code: str
    message: str


class ErrorBody(BaseModel):
    code: str
    message: str
    details: list[ErrorDetail] = []
    request_id: str | None = None


class ErrorEnvelope(BaseModel):
    """Response model of every error (documented in OpenAPI)."""

    error: ErrorBody


class AppError(Exception):
    """Base class of expected, user-facing errors."""

    status_code: ClassVar[int] = 500
    code: ClassVar[str] = "INTERNAL_ERROR"
    default_message: ClassVar[str] = "Something went wrong. Please try again."

    def __init__(
        self,
        message: str | None = None,
        details: Sequence[ErrorDetail] = (),
        *,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.message = message or self.default_message
        self.details = tuple(details)
        # Response headers (for example Retry-After). Never user input or secrets.
        self.headers = dict(headers or {})
        super().__init__(self.message)


class ValidationFailedError(AppError):
    status_code = 422
    code = "VALIDATION_ERROR"
    default_message = "Some of the information provided is not valid."


class AuthenticationRequiredError(AppError):
    status_code = 401
    code = "AUTHENTICATION_REQUIRED"
    default_message = "Sign in to continue."


class PermissionDeniedError(AppError):
    status_code = 403
    code = "PERMISSION_DENIED"
    default_message = "You do not have permission to do this."


class NotFoundError(AppError):
    """Also used for other tenants' resources, so their existence is never revealed."""

    status_code = 404
    code = "NOT_FOUND"
    default_message = "The requested resource was not found."


class ConflictError(AppError):
    status_code = 409
    code = "CONFLICT"
    default_message = "The resource was changed by someone else. Reload it and try again."


class SessionRefreshRequiredError(AppError):
    """A browser-security check failed: missing or invalid CSRF token, or a
    cross-site request to an anonymous authentication route (T01-04, D14).
    The client recovers by reloading (UI contract §10, OQ-5)."""

    status_code = 403
    code = "SESSION_REFRESH_REQUIRED"
    default_message = "Your session needs to be refreshed. Reload the page and try again."


class RateLimitedError(AppError):
    status_code = 429
    code = "RATE_LIMITED"
    default_message = "Too many requests. Please wait and try again."

    def __init__(self, *, retry_after: int | None = None) -> None:
        headers = {"Retry-After": str(max(1, retry_after))} if retry_after is not None else None
        super().__init__(headers=headers)


class ServiceUnavailableError(AppError):
    """A dependency that protects the operation is unavailable (fail closed)."""

    status_code = 503
    code = "SERVICE_UNAVAILABLE"
    default_message = "This service is temporarily unavailable. Please try again shortly."


def _request_id(request: Request) -> str | None:
    value: uuid.UUID | None = getattr(request.state, "request_id", None)
    return str(value) if value else None


def error_response(
    request: Request,
    *,
    status_code: int,
    code: str,
    message: str,
    details: Sequence[ErrorDetail] = (),
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    request_id = _request_id(request)
    body = ErrorEnvelope(
        error=ErrorBody(code=code, message=message, details=list(details), request_id=request_id)
    )
    response_headers = dict(headers or {})
    if request_id:
        response_headers[REQUEST_ID_HEADER] = request_id
    return JSONResponse(
        body.model_dump(mode="json"), status_code=status_code, headers=response_headers
    )


def _field_path(location: Sequence[int | str]) -> str | None:
    # ("body", "address", "city") -> "address.city"; ("query", "limit") -> "limit"
    parts = [str(part) for part in location[1:]] if len(location) > 1 else []
    return ".".join(parts) or None


def validation_details(errors: Sequence[Any]) -> list[ErrorDetail]:
    """Pydantic errors → details. The submitted input is never echoed."""
    return [
        ErrorDetail(
            field=_field_path(error.get("loc", ())),
            code=str(error.get("type", "invalid")),
            message=str(error.get("msg", "Invalid value.")),
        )
        for error in errors
    ]


_HTTP_ERRORS: dict[int, tuple[str, str]] = {
    404: ("NOT_FOUND", NotFoundError.default_message),
    405: ("METHOD_NOT_ALLOWED", "This operation is not supported for this resource."),
}


async def _handle_app_error(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, AppError)  # noqa: S101 - registered for AppError only
    return error_response(
        request,
        status_code=exc.status_code,
        code=exc.code,
        message=exc.message,
        details=exc.details,
        headers=exc.headers,
    )


async def _handle_validation_error(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)  # noqa: S101
    return error_response(
        request,
        status_code=ValidationFailedError.status_code,
        code=ValidationFailedError.code,
        message=ValidationFailedError.default_message,
        details=validation_details(exc.errors()),
    )


async def _handle_http_error(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)  # noqa: S101
    code, message = _HTTP_ERRORS.get(exc.status_code, ("HTTP_ERROR", "The request failed."))
    return error_response(
        request,
        status_code=exc.status_code,
        code=code,
        message=message,
        headers=dict(exc.headers or {}),
    )


async def _handle_stale_data(request: Request, exc: Exception) -> JSONResponse:
    return await _handle_app_error(request, ConflictError())


async def _handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
    logger.error(
        "request.unhandled_exception",
        exc_info=exc,
        extra={"request_id": _request_id(request), "path": request.url.path},
    )
    return error_response(
        request,
        status_code=500,
        code=AppError.code,
        message=AppError.default_message,
    )


def install_exception_handlers(app: FastAPI) -> None:
    """Map every error to the envelope."""
    app.add_exception_handler(AppError, _handle_app_error)
    app.add_exception_handler(RequestValidationError, _handle_validation_error)
    app.add_exception_handler(StarletteHTTPException, _handle_http_error)
    app.add_exception_handler(StaleDataError, _handle_stale_data)
    app.add_exception_handler(Exception, _handle_unexpected)
