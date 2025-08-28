from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .config import get_settings
from .models import HealthResponse
from .routers.auth import router as auth_router

settings = get_settings()

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

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.CORS_ALLOW_ORIGINS.split(",")] if settings.CORS_ALLOW_ORIGINS else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# PUBLIC_INTERFACE
@app.get(
    "/",
    response_model=HealthResponse,
    tags=["Health"],
    summary="Health Check",
    description="Returns a simple health message for uptime monitoring.",
)
def health_check() -> HealthResponse:
    """Service health check endpoint."""
    return HealthResponse(message="Healthy")


# Register routers
app.include_router(auth_router)
