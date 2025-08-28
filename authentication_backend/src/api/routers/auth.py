"""
Authentication API router.
Defines endpoints for sign up, send verification code, verify code, sign in, and forgot/reset password.

This refactor unifies all state into public.users:
- email, hashed_password, is_email_verified
- current_verification_code, code_expires_at, code_attempts
- password_reset_code, password_reset_expires

Legacy dependencies on app.profiles and app.verification_codes are removed.
"""

import time
import secrets
import datetime as dt
from typing import Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi import Request

from ..models import (
    SignUpRequest,
    SignUpResponse,
    SendVerificationCodeRequest,
    VerifyCodeRequest,
    SignInRequest,
    AuthTokenResponse,
    ForgotPasswordRequest,
    ResetPasswordRequest,
)
from ..deps import provide_supabase_client, provide_email_service, provide_settings
from ..services.supabase_client import SupabaseAdminClient
from ..services.email_service import EmailService
from ..config import Settings

router = APIRouter(prefix="/auth", tags=["Authentication"])

# Simple in-memory rate limiter (hook) to protect endpoints
# Not production-grade; replace with Redis/SlowAPI in production.
_RATE_LIMIT_BUCKET = {}  # key -> (reset_epoch, count)
_RATE_LIMIT_WINDOW_SEC = 60
_RATE_LIMIT_MAX = 30  # 30 requests per minute per IP by default


def _rate_limit_check(request: Request, key_suffix: str = "") -> None:
    """
    Simple leaky-bucket rate limit check using client host as key.
    This is purposely lightweight and local-only.
    """
    client_ip = request.client.host if request.client else "unknown"
    k = f"{client_ip}:{key_suffix}"
    now = int(time.time())
    reset, count = _RATE_LIMIT_BUCKET.get(k, (now + _RATE_LIMIT_WINDOW_SEC, 0))
    # Reset window if elapsed
    if now > reset:
        reset = now + _RATE_LIMIT_WINDOW_SEC
        count = 0
    count += 1
    _RATE_LIMIT_BUCKET[k] = (reset, count)
    if count > _RATE_LIMIT_MAX:
        # Avoid leaking exact limits to clients
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many requests")


def _safe_detail(exc: Exception, default_msg: str = "Unexpected error") -> str:
    """
    Create a safe error detail without leaking secrets/stack traces.
    """
    text = str(exc).strip()
    if not text:
        return default_msg
    # Avoid returning raw JSON or long responses from Supabase; truncate.
    return text[:240]


def _now_utc() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _iso_utc(dt_value: dt.datetime) -> str:
    return dt_value.astimezone(dt.timezone.utc).replace(tzinfo=dt.timezone.utc).isoformat()


def _gen_numeric_code(length: int = 6) -> str:
    digits = "0123456789"
    first = secrets.choice("123456789")
    rest = "".join(secrets.choice(digits) for _ in range(max(0, length - 1)))
    return first + rest


def _postgrest_headers(settings: Settings) -> Dict[str, str]:
    srk = settings.SUPABASE_SERVICE_ROLE_KEY.strip()
    return {
        "apikey": srk,
        "Authorization": f"Bearer {srk}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Prefer": "return=representation,resolution=merge-duplicates",
    }


def _users_endpoint(settings: Settings) -> str:
    return f"{settings.SUPABASE_URL.rstrip('/')}/rest/v1/users"


def _get_user_row_by_email(settings: Settings, email: str) -> Optional[Dict[str, Any]]:
    import httpx
    ep = f"{_users_endpoint(settings)}?select=*&email=eq.{email}"
    try:
        with httpx.Client(timeout=20) as client:
            resp = client.get(ep, headers=_postgrest_headers(settings))
            if resp.status_code >= 400:
                raise RuntimeError(f"users select failed: {resp.status_code} {resp.text}")
            data = resp.json()
            if isinstance(data, list):
                return data[0] if data else None
            return data or None
    except Exception as exc:
        raise RuntimeError(f"Failed to query users: {exc}") from exc


def _insert_user_row(settings: Settings, email: str, hashed_password: str) -> Dict[str, Any]:
    import httpx
    row = {"email": email, "hashed_password": hashed_password, "is_email_verified": False}
    try:
        with httpx.Client(timeout=20) as client:
            resp = client.post(_users_endpoint(settings), headers=_postgrest_headers(settings), json=row)
            if resp.status_code >= 400:
                msg = resp.text.lower()
                if "duplicate key" in msg or "unique" in msg or "already exists" in msg or resp.status_code in (409,):
                    raise ValueError("User with this email already exists")
                raise RuntimeError(f"users insert failed: {resp.status_code} {resp.text}")
            data = resp.json()
            return data[0] if isinstance(data, list) and data else data
    except ValueError:
        raise
    except Exception as exc:
        raise RuntimeError(f"Failed to create user row: {exc}") from exc


def _update_user_row(settings: Settings, email: str, values: Dict[str, Any]) -> Dict[str, Any]:
    import httpx
    ep = f"{_users_endpoint(settings)}?email=eq.{email}"
    try:
        with httpx.Client(timeout=20) as client:
            resp = client.patch(ep, headers=_postgrest_headers(settings), json=values)
            if resp.status_code >= 400:
                raise RuntimeError(f"users update failed: {resp.status_code} {resp.text}")
            data = resp.json()
            if isinstance(data, list):
                return data[0] if data else {}
            return data
    except Exception as exc:
        raise RuntimeError(f"Failed to update user row: {exc}") from exc


# PUBLIC_INTERFACE
@router.post(
    "/signup",
    summary="Sign up",
    description="Create a user in Supabase and send a verification code via email.",
    response_model=SignUpResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {"description": "User created and verification email sent."},
        400: {"description": "Invalid request or user already exists."},
        429: {"description": "Too many requests"},
        500: {"description": "Email delivery failure"},
    },
)
def signup(
    payload: SignUpRequest,
    request: Request,
    supabase: SupabaseAdminClient = Depends(provide_supabase_client),
    email_service: EmailService = Depends(provide_email_service),
    settings: Settings = Depends(provide_settings),
) -> SignUpResponse:
    """
    Create a user via Supabase Auth Admin and store unified state in public.users.
    Then generate a 6-digit verification code stored in public.users and email it.
    """
    _rate_limit_check(request, key_suffix="signup")

    # 1) Create user in Supabase Auth (not confirmed)
    try:
        supabase.create_user(payload.email, payload.password)
    except Exception as exc:
        # If user already exists in auth, still proceed to ensure we create/refresh unified users row/code
        msg = str(exc).lower()
        if "already registered" not in msg and "user exists" not in msg:
            raise HTTPException(status_code=400, detail=_safe_detail(exc, "Unable to create user"))

    # 2) Create/ensure unified users row
    try:
        existing = _get_user_row_by_email(settings, payload.email)
        if existing is None:
            try:
                _insert_user_row(settings, payload.email, "<managed-by-auth>")  # password managed by Supabase Auth
            except ValueError:
                # Race: created by another request
                pass
    except Exception as exc:
        raise HTTPException(status_code=400, detail=_safe_detail(exc, "Unable to initialize user"))

    # 3) Generate and persist a 6-digit code in public.users
    code = _gen_numeric_code(6)
    expires_at = _now_utc() + dt.timedelta(seconds=settings.VERIFICATION_CODE_TTL_SECONDS)
    try:
        _update_user_row(
            settings,
            payload.email,
            {
                "current_verification_code": code,
                "code_expires_at": _iso_utc(expires_at),
                "code_attempts": 0,
                "is_email_verified": False,
            },
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=_safe_detail(exc, "Failed to prepare verification code"))

    # 4) Email the code
    subject = "Your verification code"
    body = f"{code}\n\nEnter this 6-digit code in the app to verify your email. The code expires in {int(settings.VERIFICATION_CODE_TTL_SECONDS/60)} minutes."
    try:
        email_service.send_email(payload.email, subject, body)
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to send verification email")

    return SignUpResponse(email=payload.email, requires_verification=True)


# PUBLIC_INTERFACE
@router.post(
    "/send-code",
    summary="Send verification code",
    description="Sends or re-sends an email verification code.",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        204: {"description": "Verification email sent"},
        429: {"description": "Too many requests"},
        400: {"description": "Failed to request verification"},
    },
)
def send_verification_code(
    payload: SendVerificationCodeRequest,
    request: Request,
    email_service: EmailService = Depends(provide_email_service),
    supabase: SupabaseAdminClient = Depends(provide_supabase_client),
    settings: Settings = Depends(provide_settings),
) -> None:
    """
    Send or re-send a 6-digit verification code and store it on public.users.
    """
    _rate_limit_check(request, key_suffix="send-code")

    # If user doesn't exist in auth or unified users, avoid leaking info: still return 204
    try:
        user_row = _get_user_row_by_email(settings, payload.email)
        if user_row is None:
            # Try to ensure presence by creating a minimal row (no-op if auth not present)
            try:
                _insert_user_row(settings, payload.email, "<managed-by-auth>")
            except ValueError:
                pass
    except Exception:
        raise HTTPException(status_code=400, detail="Failed to request verification")

    code = _gen_numeric_code(6)
    expires_at = _now_utc() + dt.timedelta(seconds=settings.VERIFICATION_CODE_TTL_SECONDS)
    try:
        _update_user_row(
            settings,
            payload.email,
            {
                "current_verification_code": code,
                "code_expires_at": _iso_utc(expires_at),
                "code_attempts": 0,
            },
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=_safe_detail(exc, "Failed to prepare verification code"))

    subject = "Your verification code"
    body = f"{code}\n\nEnter this 6-digit code in the app to verify your email. The code expires in {int(settings.VERIFICATION_CODE_TTL_SECONDS/60)} minutes."
    try:
        email_service.send_email(payload.email, subject, body)
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to send verification email")


# PUBLIC_INTERFACE
@router.post(
    "/verify",
    summary="Verify email code",
    description="Verifies email using a code sent to the user's email.",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        204: {"description": "Email verified"},
        400: {"description": "Invalid or expired code"},
        429: {"description": "Too many requests"},
    },
)
def verify_code(
    payload: VerifyCodeRequest,
    request: Request,
    supabase: SupabaseAdminClient = Depends(provide_supabase_client),
    settings: Settings = Depends(provide_settings),
) -> None:
    """
    Verify a 6-digit code stored on public.users. On success, set is_email_verified=true and clear code fields.
    """
    _rate_limit_check(request, key_suffix="verify")

    # Load user row
    try:
        row = _get_user_row_by_email(settings, payload.email)
        if not row:
            raise HTTPException(status_code=400, detail="Invalid or expired code")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid or expired code")

    # Validate code and expiry
    code = (row.get("current_verification_code") or "").strip()
    exp = row.get("code_expires_at")
    try:
        exp_dt = dt.datetime.fromisoformat(str(exp).replace("Z", "+00:00")) if exp else None
    except Exception:
        exp_dt = None

    if (not code) or (payload.code != code):
        # Increment attempts for throttling/observability
        try:
            current_attempts = int(row.get("code_attempts") or 0) + 1
            _update_user_row(settings, payload.email, {"code_attempts": current_attempts})
        except Exception:
            pass
        raise HTTPException(status_code=400, detail="Invalid or expired code")

    if (not exp_dt) or (exp_dt < _now_utc()):
        raise HTTPException(status_code=400, detail="Invalid or expired code")

    # Consume code and mark email verified
    try:
        _update_user_row(
            settings,
            payload.email,
            {
                "is_email_verified": True,
                "current_verification_code": None,
                "code_expires_at": None,
                "code_attempts": 0,
            },
        )
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid or expired code")


# PUBLIC_INTERFACE
@router.post(
    "/signin",
    summary="Sign in",
    description="Authenticates a user and returns an access token.",
    response_model=AuthTokenResponse,
    responses={
        200: {"description": "Signed in"},
        400: {"description": "Invalid credentials"},
        429: {"description": "Too many requests"},
    },
)
def signin(
    payload: SignInRequest,
    request: Request,
    supabase: SupabaseAdminClient = Depends(provide_supabase_client),
    settings: Settings = Depends(provide_settings),
) -> AuthTokenResponse:
    """
    Authenticate using Supabase auth token endpoint and return the access token.
    """
    _rate_limit_check(request, key_suffix="signin")

    try:
        token = supabase.password_sign_in(payload.email, payload.password)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid email or password")

    access_token = token.get("access_token")
    if not access_token:
        raise HTTPException(status_code=400, detail="Invalid email or password")
    return AuthTokenResponse(access_token=access_token, token_type="bearer")


# PUBLIC_INTERFACE
@router.post(
    "/forgot-password",
    summary="Forgot password",
    description="Initiates password reset by sending a code to email.",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        204: {"description": "Password recovery email sent"},
        429: {"description": "Too many requests"},
        400: {"description": "Failed to initiate recovery"},
    },
)
def forgot_password(
    payload: ForgotPasswordRequest,
    request: Request,
    supabase: SupabaseAdminClient = Depends(provide_supabase_client),
    email_service: EmailService = Depends(provide_email_service),
    settings: Settings = Depends(provide_settings),
) -> None:
    """
    For this unified schema, we send a code for reset and store it in public.users.
    Frontend can present a reset form that calls /reset-password with code and new password.
    """
    _rate_limit_check(request, key_suffix="forgot-password")

    # Ensure user exists in unified table to avoid enumeration details
    try:
        row = _get_user_row_by_email(settings, payload.email)
        if row is None:
            # do not reveal; still send 204
            return None
    except Exception:
        # avoid leaking details
        return None

    reset_code = _gen_numeric_code(6)
    expires_at = _now_utc() + dt.timedelta(seconds=settings.PASSWORD_RESET_TOKEN_TTL_SECONDS)
    try:
        _update_user_row(
            settings,
            payload.email,
            {
                "password_reset_code": reset_code,
                "password_reset_expires": _iso_utc(expires_at),
            },
        )
    except Exception:
        # do not reveal specifics
        return None

    subject = "Password reset code"
    body = f"{reset_code}\n\nUse this code to reset your password. It expires in {int(settings.PASSWORD_RESET_TOKEN_TTL_SECONDS/60)} minutes."
    try:
        email_service.send_email(payload.email, subject, body)
    except Exception:
        # swallow email errors to prevent enumeration
        return None


# PUBLIC_INTERFACE
@router.post(
    "/reset-password",
    summary="Reset password",
    description="Resets the user's password using a previously sent code.",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        204: {"description": "Password reset successful"},
        400: {"description": "Invalid code or request"},
        429: {"description": "Too many requests"},
    },
)
def reset_password(
    payload: ResetPasswordRequest,
    request: Request,
    supabase: SupabaseAdminClient = Depends(provide_supabase_client),
    settings: Settings = Depends(provide_settings),
) -> None:
    """
    Validate the provided code against public.users.password_reset_code/_expires,
    then update the user's password via Supabase Admin, and clear reset fields.
    """
    _rate_limit_check(request, key_suffix="reset-password")

    # Validate code
    try:
        row = _get_user_row_by_email(settings, payload.email)
        if not row:
            raise HTTPException(status_code=400, detail="Invalid code or request")
        db_code = (row.get("password_reset_code") or "").strip()
        exp = row.get("password_reset_expires")
        try:
            exp_dt = dt.datetime.fromisoformat(str(exp).replace("Z", "+00:00")) if exp else None
        except Exception:
            exp_dt = None
        if (not db_code) or (payload.code != db_code) or (not exp_dt) or (exp_dt < _now_utc()):
            raise HTTPException(status_code=400, detail="Invalid code or request")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid code or request")

    # Update password in Supabase Auth
    try:
        supabase.admin_update_password_by_email(payload.email, payload.new_password)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid code or request")

    # Clear reset fields
    try:
        _update_user_row(
            settings,
            payload.email,
            {"password_reset_code": None, "password_reset_expires": None},
        )
    except Exception:
        # Even if clearing fails, do not leak; operation is effectively done
        pass
