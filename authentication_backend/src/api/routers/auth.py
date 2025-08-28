"""
Authentication API router.
Defines endpoints for sign up, send verification code, verify code, sign in, and forgot/reset password.
"""

from fastapi import APIRouter, Depends, HTTPException, status

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

# PUBLIC_INTERFACE
@router.post(
    "/signup",
    summary="Sign up",
    description="Create a user in Supabase and send a verification code via email.",
    response_model=SignUpResponse,
    status_code=status.HTTP_201_CREATED,
)
def signup(
    payload: SignUpRequest,
    supabase: SupabaseAdminClient = Depends(provide_supabase_client),
    email_service: EmailService = Depends(provide_email_service),
    settings: Settings = Depends(provide_settings),
) -> SignUpResponse:
    """
    Create a user with Supabase and send an email verification code.
    Note: Verification code generation/storage handled in later steps.
    """
    try:
        supabase.create_user(payload.email, payload.password)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # Placeholder: In later steps, generate and store a code and email it
    subject = "Verify your email"
    body = "Your verification code will appear here in the next implementation step."
    try:
        email_service.send_email(payload.email, subject, body)
    except Exception as exc:
        # Optional: rollback user creation in future step
        raise HTTPException(status_code=500, detail=f"Failed to send verification email: {exc}")

    return SignUpResponse(email=payload.email, requires_verification=True)


# PUBLIC_INTERFACE
@router.post(
    "/send-code",
    summary="Send verification code",
    description="Sends or re-sends an email verification code.",
    status_code=status.HTTP_204_NO_CONTENT,
)
def send_verification_code(
    payload: SendVerificationCodeRequest,
    email_service: EmailService = Depends(provide_email_service),
    settings: Settings = Depends(provide_settings),
) -> None:
    """
    Generate a code and send via email. Will be fully implemented later.
    """
    try:
        email_service.send_email(payload.email, "Your verification code", "123456")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to send verification email: {exc}")


# PUBLIC_INTERFACE
@router.post(
    "/verify",
    summary="Verify email code",
    description="Verifies email using a code sent to the user's email.",
    status_code=status.HTTP_204_NO_CONTENT,
)
def verify_code(payload: VerifyCodeRequest) -> None:
    """
    Verify the provided code. To be implemented later with persistence and TTL checks.
    """
    # Placeholder no-op
    return None


# PUBLIC_INTERFACE
@router.post(
    "/signin",
    summary="Sign in",
    description="Authenticates a user and returns an access token.",
    response_model=AuthTokenResponse,
)
def signin(payload: SignInRequest) -> AuthTokenResponse:
    """
    Sign in logic to be implemented using Supabase Auth in future steps.
    """
    # Placeholder token
    return AuthTokenResponse(access_token="placeholder-token", token_type="bearer")


# PUBLIC_INTERFACE
@router.post(
    "/forgot-password",
    summary="Forgot password",
    description="Initiates password reset by sending a code to email.",
    status_code=status.HTTP_204_NO_CONTENT,
)
def forgot_password(payload: ForgotPasswordRequest) -> None:
    """
    Initiates password reset flow. Implementation in later steps.
    """
    return None


# PUBLIC_INTERFACE
@router.post(
    "/reset-password",
    summary="Reset password",
    description="Resets the user's password using a previously sent code.",
    status_code=status.HTTP_204_NO_CONTENT,
)
def reset_password(payload: ResetPasswordRequest) -> None:
    """
    Resets password after validating code. Implementation in later steps.
    """
    return None
