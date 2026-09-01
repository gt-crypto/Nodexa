"""Centralized FastAPI exception handlers returning consistent error payloads."""
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend.errors.exceptions import SentinelError
from backend.logging import get_current_request_id, logger


def format_error_response(
    error_code: str,
    message: str,
    status_code: int,
    details: dict = None,
) -> JSONResponse:
    """Generates standard JSON error response with correlation ID."""
    req_id = get_current_request_id()
    content = {
        "error": error_code,
        "message": message,
        "detail": message,  # Backward-compatible alias for FastAPI clients/tests
        "request_id": req_id,
        "details": details or {},
    }
    return JSONResponse(
        status_code=status_code,
        content=content,
        headers={"X-Request-ID": req_id},
    )


async def sentinel_error_handler(request: Request, exc: SentinelError) -> JSONResponse:
    """Handles all Sentinel domain exceptions."""
    logger.warning(
        operation="DOMAIN_ERROR",
        message=f"{exc.error_code}: {exc.message}",
        details={"status_code": exc.status_code, "details": exc.details},
    )
    return format_error_response(
        error_code=exc.error_code,
        message=exc.message,
        status_code=exc.status_code,
        details=exc.details,
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Handles FastAPI Pydantic request validation errors."""
    clean_errors = []
    for err in exc.errors():
        clean_errors.append({
            "field": " -> ".join(str(loc) for loc in err.get("loc", [])),
            "issue": err.get("msg", "Invalid value"),
            "type": err.get("type", "value_error"),
        })

    logger.warning(
        operation="REQUEST_VALIDATION_ERROR",
        message="Request payload failed structural validation",
        details={"validation_errors": clean_errors},
    )
    return format_error_response(
        error_code="VALIDATION_ERROR",
        message="Invalid request payload structure or parameters.",
        status_code=status.HTTP_400_BAD_REQUEST,
        details={"validation_errors": clean_errors},
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Handles Starlette HTTP exceptions."""
    code_map = {
        400: "VALIDATION_ERROR",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        409: "CONFLICT",
        422: "UNPROCESSABLE_ENTITY",
        429: "RATE_LIMIT_EXCEEDED",
        500: "INTERNAL_ERROR",
        503: "SERVICE_UNAVAILABLE",
    }
    error_code = code_map.get(exc.status_code, "HTTP_ERROR")
    message = exc.detail if isinstance(exc.detail, str) else str(exc.detail)

    return format_error_response(
        error_code=error_code,
        message=message,
        status_code=exc.status_code,
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catches unexpected server errors safely without leaking internal stack traces."""
    logger.error(
        operation="UNHANDLED_EXCEPTION",
        message=f"Unhandled internal server error: {str(exc)}",
        error=str(exc),
    )
    return format_error_response(
        error_code="INTERNAL_ERROR",
        message="An unexpected internal server error occurred. Please contact system support.",
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )


def register_error_handlers(app: FastAPI) -> None:
    """Registers all custom exception handlers on the FastAPI application."""
    app.add_exception_handler(SentinelError, sentinel_error_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
