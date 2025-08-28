"""
Pydantic models (DTOs) used by the authentication API.
"""

from pydantic import BaseModel, Field, EmailStr


class HealthResponse(BaseModel):
    """Health check response payload."""
    message: str = Field(..., description="Health message")


class SignUpRequest(BaseModel):
    """Payload for user sign up."""
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=8, description="User password")


class SignUpResponse(BaseModel):
    """Response after initiating sign up."""
    email: EmailStr = Field(..., description="Registered user email")
    requires_verification: bool = Field(True, description="Whether email verification is required")


class SendVerificationCodeRequest(BaseModel):
    """Request payload to send a verification code to an email."""
    email: EmailStr = Field(..., description="Email to send the verification code to")


class VerifyCodeRequest(BaseModel):
    """Request payload to verify a received email code."""
    email: EmailStr = Field(..., description="Email address to verify")
    code: str = Field(..., min_length=4, max_length=8, description="Verification code sent via email")


class AuthTokenResponse(BaseModel):
    """Auth token response after sign in."""
    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field("bearer", description="Token type")


class SignInRequest(BaseModel):
    """Sign in using email and password."""
    email: EmailStr = Field(..., description="User email")
    password: str = Field(..., description="User password")


class ForgotPasswordRequest(BaseModel):
    """Request to initiate the forgot password flow."""
    email: EmailStr = Field(..., description="Registered email address")


class ResetPasswordRequest(BaseModel):
    """Request to reset password using a code/token."""
    email: EmailStr = Field(..., description="Registered email address")
    code: str = Field(..., min_length=4, max_length=8, description="Password reset code received via email")
    new_password: str = Field(..., min_length=8, description="New password to set")
