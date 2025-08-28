"""
Dependency injection utilities for FastAPI routes.
Provides instances of Settings, Supabase client, and EmailService.
"""

from functools import lru_cache

from .config import get_settings, Settings
from .services.supabase_client import SupabaseAdminClient
from .services.email_service import EmailService, SmtpEmailService


# PUBLIC_INTERFACE
def provide_settings() -> Settings:
    """Provide application settings (cached)."""
    return get_settings()


@lru_cache()
def _get_supabase_client() -> SupabaseAdminClient:
    settings = get_settings()
    return SupabaseAdminClient(
        url=settings.SUPABASE_URL,
        service_role_key=settings.SUPABASE_SERVICE_ROLE_KEY,
    )


# PUBLIC_INTERFACE
def provide_supabase_client() -> SupabaseAdminClient:
    """Provide a cached Supabase admin client."""
    return _get_supabase_client()


@lru_cache()
def _get_email_service() -> EmailService:
    settings = get_settings()
    return SmtpEmailService(
        host=settings.SMTP_HOST,
        port=settings.SMTP_PORT,
        username=settings.SMTP_USER,
        password=settings.SMTP_PASSWORD,
        from_email=settings.SMTP_FROM_EMAIL,
        from_name=settings.SMTP_FROM_NAME or "Auth System",
        use_tls=True,
    )


# PUBLIC_INTERFACE
def provide_email_service() -> EmailService:
    """Provide a cached EmailService instance."""
    return _get_email_service()
