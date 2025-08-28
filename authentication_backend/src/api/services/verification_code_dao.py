"""
DEPRECATED: Legacy verification code DAO targeting app.verification_codes.

The project now uses:
- public.pending_signups for pre-verification signup state (email, password, code)
- public.users for verified users and password reset codes.

This module remains only to aid migrations and to avoid import errors. Do not use in new code.
"""
# Intentionally left without functionality. New flows are implemented in routers/auth.py
