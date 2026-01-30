"""Error handling and exception handlers for GTM Advisor Gateway.

Provides consistent error response formatting and logging across all endpoints.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from jose import JWTError
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from packages.core.src.config import Environment, get_config

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _is_production() -> bool:
    """Check if running in production environment (cached)."""
    return get_config().environment == Environment.PRODUCTION


class GTMError(Exception):
    """Base exception for GTM Advisor application errors."""

    def __init__(
        self,
        message: str,
        error_code: str = "GTM_ERROR",
        status_code: int = 500,
        details: dict[str, Any] | None = None,
    ):
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)


class ResourceNotFoundError(GTMError):
    """Resource not found error."""

    def __init__(self, resource_type: str, resource_id: str):
        super().__init__(
            message=f"{resource_type} not found",
            error_code="RESOURCE_NOT_FOUND",
            status_code=404,
            details={"resource_type": resource_type, "resource_id": resource_id},
        )


class AuthenticationError(GTMError):
    """Authentication error."""

    def __init__(self, message: str = "Authentication failed"):
        super().__init__(
            message=message,
            error_code="AUTHENTICATION_ERROR",
            status_code=401,
        )


class AuthorizationError(GTMError):
    """Authorization error."""

    def __init__(self, message: str = "Access denied"):
        super().__init__(
            message=message,
            error_code="AUTHORIZATION_ERROR",
            status_code=403,
        )


class RateLimitError(GTMError):
    """Rate limit exceeded error."""

    def __init__(self, retry_after: int | None = None):
        details = {}
        if retry_after:
            details["retry_after_seconds"] = retry_after
        super().__init__(
            message="Rate limit exceeded. Please try again later.",
            error_code="RATE_LIMIT_EXCEEDED",
            status_code=429,
            details=details,
        )


class GTMValidationError(GTMError):
    """Validation error."""

    def __init__(self, message: str, field_errors: list[dict[str, Any]] | None = None):
        super().__init__(
            message=message,
            error_code="VALIDATION_ERROR",
            status_code=422,
            details={"field_errors": field_errors or []},
        )


class DatabaseError(GTMError):
    """Database error."""

    def __init__(self, message: str = "Database operation failed"):
        super().__init__(
            message=message,
            error_code="DATABASE_ERROR",
            status_code=500,
        )


def _format_error_response(
    error_code: str,
    message: str,
    status_code: int,
    details: dict[str, Any] | None = None,
    path: str | None = None,
) -> dict[str, Any]:
    """Format a consistent error response."""
    response = {
        "error": error_code,
        "message": message,
        "status_code": status_code,
    }

    if details and not _is_production():
        # Only include details in non-production for security
        response["details"] = details

    if path:
        response["path"] = path

    return response


async def gtm_error_handler(request: Request, exc: GTMError) -> JSONResponse:
    """Handle GTM application errors."""
    logger.warning(
        "gtm_error: code=%s path=%s message=%s",
        exc.error_code,
        request.url.path,
        exc.message,
    )

    return JSONResponse(
        status_code=exc.status_code,
        content=_format_error_response(
            error_code=exc.error_code,
            message=exc.message,
            status_code=exc.status_code,
            details=exc.details,
            path=request.url.path,
        ),
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Handle FastAPI HTTPExceptions with consistent formatting."""
    logger.warning(
        "http_exception: status=%d path=%s detail=%s",
        exc.status_code,
        request.url.path,
        exc.detail,
    )

    # Map status codes to error codes
    error_code_map = {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        405: "METHOD_NOT_ALLOWED",
        409: "CONFLICT",
        422: "UNPROCESSABLE_ENTITY",
        429: "TOO_MANY_REQUESTS",
        500: "INTERNAL_SERVER_ERROR",
        502: "BAD_GATEWAY",
        503: "SERVICE_UNAVAILABLE",
    }

    error_code = error_code_map.get(exc.status_code, "HTTP_ERROR")

    return JSONResponse(
        status_code=exc.status_code,
        content=_format_error_response(
            error_code=error_code,
            message=str(exc.detail) if exc.detail else "An error occurred",
            status_code=exc.status_code,
            path=request.url.path,
        ),
        headers=getattr(exc, "headers", None),
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Handle Pydantic validation errors with user-friendly messages."""
    errors = exc.errors()

    # Format errors for user
    field_errors = []
    for error in errors:
        loc = " -> ".join(str(part) for part in error["loc"] if part != "body")
        field_errors.append(
            {
                "field": loc,
                "message": error["msg"],
                "type": error["type"],
            }
        )

    logger.warning("validation_error: path=%s errors=%s", request.url.path, field_errors)

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=_format_error_response(
            error_code="VALIDATION_ERROR",
            message="Request validation failed",
            status_code=422,
            details={"errors": field_errors},
            path=request.url.path,
        ),
    )


async def pydantic_validation_handler(request: Request, exc: ValidationError) -> JSONResponse:
    """Handle Pydantic ValidationError (from model construction)."""
    errors = exc.errors()

    field_errors = []
    for error in errors:
        loc = " -> ".join(str(part) for part in error["loc"])
        field_errors.append(
            {
                "field": loc,
                "message": error["msg"],
                "type": error["type"],
            }
        )

    logger.warning("pydantic_validation_error: path=%s errors=%s", request.url.path, field_errors)

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=_format_error_response(
            error_code="VALIDATION_ERROR",
            message="Data validation failed",
            status_code=422,
            details={"errors": field_errors},
            path=request.url.path,
        ),
    )


async def jwt_error_handler(request: Request, exc: JWTError) -> JSONResponse:
    """Handle JWT errors."""
    logger.warning("jwt_error: path=%s error=%s", request.url.path, str(exc))

    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content=_format_error_response(
            error_code="INVALID_TOKEN",
            message="Invalid or expired token",
            status_code=401,
            path=request.url.path,
        ),
        headers={"WWW-Authenticate": "Bearer"},
    )


async def integrity_error_handler(request: Request, exc: IntegrityError) -> JSONResponse:
    """Handle database integrity errors (e.g., unique constraint violations)."""
    logger.warning(
        "integrity_error: path=%s error=%s",
        request.url.path,
        str(exc.orig) if exc.orig else str(exc),
    )

    # Check for common constraint violations
    error_str = str(exc.orig) if exc.orig else str(exc)

    if "unique" in error_str.lower() or "duplicate" in error_str.lower():
        message = "A record with this value already exists"
        error_code = "DUPLICATE_ENTRY"
    elif "foreign" in error_str.lower():
        message = "Referenced record does not exist"
        error_code = "INVALID_REFERENCE"
    else:
        message = "Data constraint violation"
        error_code = "INTEGRITY_ERROR"

    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content=_format_error_response(
            error_code=error_code,
            message=message,
            status_code=409,
            path=request.url.path,
        ),
    )


async def sqlalchemy_error_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
    """Handle general SQLAlchemy errors."""
    logger.error("database_error: path=%s error=%s", request.url.path, str(exc), exc_info=True)

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=_format_error_response(
            error_code="DATABASE_ERROR",
            message="A database error occurred" if _is_production() else str(exc),
            status_code=500,
            path=request.url.path,
        ),
    )


async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle all unhandled exceptions."""
    logger.error(
        "unhandled_exception: path=%s method=%s error_type=%s error=%s",
        request.url.path,
        request.method,
        type(exc).__name__,
        str(exc),
        exc_info=True,
    )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=_format_error_response(
            error_code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred" if _is_production() else str(exc),
            status_code=500,
            path=request.url.path,
        ),
    )


def register_error_handlers(app: FastAPI) -> None:
    """Register all error handlers with the FastAPI app.

    Call this during app initialization to set up consistent error handling.

    Args:
        app: The FastAPI application instance
    """
    # Custom application errors
    app.add_exception_handler(GTMError, gtm_error_handler)

    # HTTP exceptions
    app.add_exception_handler(HTTPException, http_exception_handler)

    # Validation errors
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(ValidationError, pydantic_validation_handler)

    # JWT errors
    app.add_exception_handler(JWTError, jwt_error_handler)

    # Database errors
    app.add_exception_handler(IntegrityError, integrity_error_handler)
    app.add_exception_handler(SQLAlchemyError, sqlalchemy_error_handler)

    # Catch-all for unhandled exceptions
    app.add_exception_handler(Exception, global_exception_handler)

    logger.info("Error handlers registered")
