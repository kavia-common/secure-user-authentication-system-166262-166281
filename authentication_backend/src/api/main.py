"""
FastAPI application entrypoint for the Authentication Backend.

Exposes:
- GET /           Health check
- /auth/*         Authentication endpoints (signup, send-code, verify, signin, forgot/reset)

Includes:
- CORS configuration
- Global error handlers
- OpenAPI tags and metadata
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.status import HTTP_404_NOT_FOUND

from .config import get_settings, get_raw_env
from .models import HealthResponse
from .routers.auth import router as auth_router
from .logging_config import configure_logging, get_logger
from .error_handlers import (
    http_exception_handler,
    validation_exception_handler,
    generic_exception_handler,
)

# Initialize settings and logging early
settings = get_settings()
configure_logging()
logger = get_logger(__name__)

openapi_tags = [
    {
        "name": "Health",
        "description": "Service health and diagnostics.",
    },
    {
        "name": "Authentication",
        "description": "Sign up, verification, sign in, and password reset endpoints.",
    },
]

app = FastAPI(
    title=settings.APP_NAME,
    description="Authentication backend powered by FastAPI and Supabase.",
    version="0.1.0",
    openapi_tags=openapi_tags,
)

# CORS configuration:
# - In development (APP_ENV != production): allow all origins for local dev.
# - In production: restrict to FRONTEND_BASE_URL if present, else use CORS_ALLOW_ORIGINS list.
app_env = (settings.APP_ENV or "development").lower()
frontend_base = get_raw_env("FRONTEND_BASE_URL", "").strip()
if app_env == "production":
    if frontend_base:
        allow_origins = [frontend_base]
    else:
        configured = [o.strip() for o in (settings.CORS_ALLOW_ORIGINS or "").split(",") if o.strip()]
        allow_origins = configured if configured else []
else:
    allow_origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins if allow_origins else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register global exception handlers
# Catch-all for HTTPException to ensure JSON (not HTML) responses
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
# Explicit handler for 404 to avoid Starlette default HTML page if any middleware bypasses FastAPI routing
app.add_exception_handler(HTTP_404_NOT_FOUND, http_exception_handler)  # type: ignore[arg-type]
# Validation errors returned as JSON with details
app.add_exception_handler(RequestValidationError, validation_exception_handler)
# Final safety net for unexpected exceptions
app.add_exception_handler(Exception, generic_exception_handler)


# PUBLIC_INTERFACE
@app.get(
    "/",
    response_model=HealthResponse,
    tags=["Health"],
    summary="Health Check",
    description="Returns a simple health message for uptime monitoring.",
)
def health_check() -> HealthResponse:
    """
    Service health check endpoint.

    Returns:
        HealthResponse: A simple 'Healthy' message indicating service readiness.
    """
    logger.debug("Health check invoked")
    return HealthResponse(message="Healthy")


# Register routers
app.include_router(auth_router)
