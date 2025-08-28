"""
DEPRECATED: Legacy verification code DAO targeting app.verification_codes.

The project now uses a unified public.users table where verification and reset codes
are stored directly on the user row. This module remains only to aid migrations and
to avoid import errors. Do not use in new code.
"""
# Intentionally left without functionality. New flows are implemented in routers/auth.py
