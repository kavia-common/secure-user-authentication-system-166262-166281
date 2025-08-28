"""
Global exception handlers for the FastAPI app.

Handlers:
- HTTPException: return structured payload with status_code and detail.
- RequestValidationError: normalize validation errors into a JSON response.
- Generic Exception: return 500 with sanitized message, and log exception with stack trace.
"""

from typing import Any, Dict

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from .logging_config import get_logger

logger = get_logger(__name__)


def _problem_response(status_code: int, detail: Any, *, extra: Dict[str, Any] | None = None) -> JSONResponse:
    """
    Create a JSONResponse following a simple problem style schema.
    """
    payload: Dict[str, Any] = {
        "status_code": status_code,
        "detail": detail,
    }
    if extra:
        payload.update(extra)
    return JSONResponse(status_code=status_code, content=payload)


# PUBLIC_INTERFACE
async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """
    Handle Starlette/FastAPI HTTPException.
    Returns a structured JSON response with status_code and detail.
    """
    logger.warning(
        "HTTPException",
        extra={
            "path": request.url.path,
            "method": request.method,
            "status_code": exc.status_code,
        },
    )
    # Avoid leaking internal details if any
    detail = exc.detail if exc.detail else "HTTP error"
    return _problem_response(exc.status_code, detail)


# PUBLIC_INTERFACE
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """
    Handle Pydantic validation errors raised by FastAPI.

    Provides an array of errors in 'detail'.
    """
    logger.info(
        "RequestValidationError",
        extra={
            "path": request.url.path,
            "method": request.method,
            "status_code": 422,
        },
    )
    return _problem_response(422, exc.errors())


# PUBLIC_INTERFACE
async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Handle unexpected server errors.

    Logs stack trace server-side, returns generic message to the client.
    """
    # Log full stack trace
    logger.exception("Unhandled server error", extra={"path": request.url.path, "method": request.method})
    safe_message = "Internal server error"
    return _problem_response(500, safe_message)
