"""
Diagnostics utilities to validate environment configuration and critical integrations.

This module performs:
- Environment validation for Supabase admin usage
- Detection of accidental frontend-style environment variable usage (REACT_APP_, NEXT_PUBLIC_)
- A lightweight HTTP header self-check for Supabase admin client (without sending network requests)

All messages are logged; secrets are never logged.
"""

from __future__ import annotations

import os
from typing import Dict, List, Tuple

from .logging_config import get_logger

logger = get_logger(__name__)


def _mask(s: str, keep: int = 4) -> str:
    """Return a masked form of a secret to avoid leaking it in logs."""
    if not s:
        return ""
    if len(s) <= keep:
        return "*" * len(s)
    return s[:keep] + "…" + "*" * 6


# PUBLIC_INTERFACE
def run_startup_diagnostics() -> None:
    """Run diagnostics checks for environment variables and configuration."""
    issues: List[str] = []

    # 1) Verify that backend envs are used (not frontend-style)
    forbidden_prefixes = ("REACT_APP_", "NEXT_PUBLIC_")
    accidental: List[Tuple[str, str]] = []
    for k, v in os.environ.items():
        if k.startswith(forbidden_prefixes):
            accidental.append((k, v))

    if accidental:
        issues.append(
            "Found frontend-style environment variables in backend process: "
            + ", ".join([kv[0] for kv in accidental])
        )
        logger.warning(
            "Frontend-style env vars detected in backend; remove or rename to backend-safe names",
            extra={"vars": [kv[0] for kv in accidental]},
        )

    # 2) Required backend envs
    supabase_url = os.getenv("SUPABASE_URL", "")
    service_role = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    if not supabase_url:
        issues.append("Missing SUPABASE_URL.")
    if not service_role:
        issues.append("Missing SUPABASE_SERVICE_ROLE_KEY.")

    # 3) SUPABASE_URL sanity
    if supabase_url and not supabase_url.startswith("http"):
        issues.append("SUPABASE_URL does not look like a URL (must start with http/https).")

    # 4) SERVICE ROLE sanity (do not log entire token)
    if service_role:
        # Supabase service role keys are JWT-like strings with 2 dots
        dot_count = service_role.count(".")
        if dot_count < 2:
            issues.append("SUPABASE_SERVICE_ROLE_KEY does not appear to be a JWT (expected two dots).")
        logger.info(
            "Supabase Service Role key present",
            extra={"key_prefix": service_role[:8], "masked": _mask(service_role)},
        )

    # 5) Explicitly log how headers would be set (only show non-secret parts)
    if service_role:
        header_preview: Dict[str, str] = {
            "apikey": _mask(service_role, keep=6),
            "Authorization": f"Bearer {_mask(service_role, keep=6)}",
            "Content-Type": "application/json",
        }
        logger.info("Supabase admin header preview (masked)", extra={"headers": header_preview})

    if issues:
        logger.error("Startup diagnostics found configuration issues", extra={"issues": issues})
    else:
        logger.info("Startup diagnostics passed with no critical issues")
