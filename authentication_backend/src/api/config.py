"""
Configuration management for the authentication backend.

Loads environment variables using python-dotenv. Do not hardcode secrets.
All configuration access should happen via the Settings class.

Environment variables must be set in the container's .env file.
"""

from functools import lru_cache
from typing import Optional

from pydantic import BaseModel, Field, ValidationError
from dotenv import load_dotenv
import os

# Load environment variables from .env if present
load_dotenv()


class Settings(BaseModel):
    """
    Settings for the authentication backend service.
    """

    APP_NAME: str = Field("Authentication Backend", description="Application name.")
    APP_ENV: str = Field("development", description="Application environment (development/staging/production).")
    APP_DEBUG: bool = Field(True, description="Enable debug mode.")
    LOG_LEVEL: Optional[str] = Field(default=None, description="Optional explicit log level (DEBUG, INFO, WARNING, ERROR).")

    # CORS
    CORS_ALLOW_ORIGINS: str = Field("*", description="Comma-separated list of allowed CORS origins.")
    # In production, FRONTEND_BASE_URL is preferred for single-frontend deployments.
    FRONTEND_BASE_URL: Optional[str] = Field(default=None, description="Frontend base URL used for strict CORS in production.")

    # Supabase admin credentials
    SUPABASE_URL: str = Field(..., description="Supabase project URL, e.g., https://xyzcompany.supabase.co")
    SUPABASE_SERVICE_ROLE_KEY: str = Field(..., description="Supabase Service Role key for admin operations. Keep it secret.")

    # SMTP for email sending (Gmail supported)
    SMTP_HOST: str = Field(..., description="SMTP server host, e.g., smtp.gmail.com")
    SMTP_PORT: int = Field(587, description="SMTP server port, typically 587 for TLS.")
    SMTP_USER: str = Field(..., description="SMTP username (full email for Gmail).")
    SMTP_PASSWORD: str = Field(..., description="SMTP password or app-specific password for Gmail.")
    SMTP_FROM_EMAIL: str = Field(..., description="From email address used in outgoing messages.")
    SMTP_FROM_NAME: Optional[str] = Field("Auth System", description="From display name for emails.")

    # Site URL for links (used by email templates, reset links, etc.)
    SITE_URL: str = Field(..., description="Public site URL used in emails (e.g., https://app.example.com)")

    # Security
    # Set default TTLs (can be overridden via .env). Requirement: 5 minutes for both.
    VERIFICATION_CODE_TTL_SECONDS: int = Field(5 * 60, description="Verification code time-to-live (seconds).")
    PASSWORD_RESET_TOKEN_TTL_SECONDS: int = Field(5 * 60, description="Password reset token TTL (seconds).")

    class Config:
        extra = "ignore"


# PUBLIC_INTERFACE
def get_raw_env(key: str, default: Optional[str] = None) -> Optional[str]:
    """Return a raw environment variable value."""
    return os.getenv(key, default)


# PUBLIC_INTERFACE
@lru_cache()
def get_settings() -> Settings:
    """Return cached Settings instance loaded from environment variables."""
    try:
        return Settings(
            APP_NAME=get_raw_env("APP_NAME", "Authentication Backend"),
            APP_ENV=get_raw_env("APP_ENV", "development"),
            APP_DEBUG=get_raw_env("APP_DEBUG", "true").lower() in ("1", "true", "yes"),
            LOG_LEVEL=get_raw_env("LOG_LEVEL"),

            CORS_ALLOW_ORIGINS=get_raw_env("CORS_ALLOW_ORIGINS", "*"),
            FRONTEND_BASE_URL=get_raw_env("FRONTEND_BASE_URL"),

            SUPABASE_URL=get_raw_env("SUPABASE_URL", "") or "",  # force validation error if missing
            SUPABASE_SERVICE_ROLE_KEY=get_raw_env("SUPABASE_SERVICE_ROLE_KEY", "") or "",

            SMTP_HOST=get_raw_env("SMTP_HOST", "") or "",
            SMTP_PORT=int(get_raw_env("SMTP_PORT", "587")),
            SMTP_USER=get_raw_env("SMTP_USER", "") or "",
            SMTP_PASSWORD=get_raw_env("SMTP_PASSWORD", "") or "",
            SMTP_FROM_EMAIL=get_raw_env("SMTP_FROM_EMAIL", "") or "",
            SMTP_FROM_NAME=get_raw_env("SMTP_FROM_NAME", "Auth System"),

            SITE_URL=get_raw_env("SITE_URL", "") or "",

            VERIFICATION_CODE_TTL_SECONDS=int(get_raw_env("VERIFICATION_CODE_TTL_SECONDS", str(5 * 60))),
            PASSWORD_RESET_TOKEN_TTL_SECONDS=int(get_raw_env("PASSWORD_RESET_TOKEN_TTL_SECONDS", str(5 * 60))),
        )
    except ValidationError as e:
        # Provide a clearer error for missing required envs
        missing = [err["loc"][0] for err in e.errors()]
        raise RuntimeError(f"Missing or invalid environment variables: {', '.join(missing)}") from e
