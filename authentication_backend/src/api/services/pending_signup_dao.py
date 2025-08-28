"""
Pending signup DAO for public.pending_signups.

This module handles temporary storage of user signup data (email and password hash placeholder)
until the user verifies the 6-digit code. It uses Supabase PostgREST endpoints with the service
role key, similar to other DAO utilities in the project.

Schema expectation for public.pending_signups:
- id uuid primary key default gen_random_uuid()
- email text unique not null
- password text not null                             -- temporarily holds user password (will not be persisted to users table)
- verification_code text not null
- code_expires_at timestamptz not null
- attempts int not null default 0
- created_at timestamptz not null default now()
- updated_at timestamptz not null default now()

Security notes:
- This table stores plaintext password temporarily to allow sign up to proceed through verification
  without creating a user in public.users. On successful verification, the user is created via Supabase
  Auth (using Admin API) and the pending row is deleted.
- Because this backend uses the Supabase Service Role key, RLS is bypassed. Ensure access to this
  backend is secured; do not expose Service Role to the frontend.

Public interfaces are documented and marked with PUBLIC_INTERFACE.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Any

import httpx

from ..config import Settings


def _headers(settings: Settings) -> Dict[str, str]:
    srk = settings.SUPABASE_SERVICE_ROLE_KEY.strip()
    return {
        "apikey": srk,
        "Authorization": f"Bearer {srk}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Prefer": "return=representation,resolution=merge-duplicates",
    }


def _endpoint(settings: Settings) -> str:
    return f"{settings.SUPABASE_URL.rstrip('/')}/rest/v1/pending_signups"


@dataclass
class PendingSignup:
    """In-memory representation of a pending signup row."""
    id: Optional[str]
    email: str
    password: str
    verification_code: str
    code_expires_at: str
    attempts: int = 0

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "PendingSignup":
        return PendingSignup(
            id=d.get("id"),
            email=d.get("email", ""),
            password=d.get("password", ""),
            verification_code=d.get("verification_code", ""),
            code_expires_at=str(d.get("code_expires_at")),
            attempts=int(d.get("attempts") or 0),
        )


# PUBLIC_INTERFACE
def get_pending_by_email(settings: Settings, email: str) -> Optional[PendingSignup]:
    """Fetch a pending signup by email. Returns None if not found."""
    ep = f"{_endpoint(settings)}?select=*&email=eq.{email}"
    with httpx.Client(timeout=20) as client:
        resp = client.get(ep, headers=_headers(settings))
        if resp.status_code >= 400:
            raise RuntimeError(f"pending_signups select failed: {resp.status_code} {resp.text}")
        data = resp.json()
        if isinstance(data, list) and data:
            return PendingSignup.from_dict(data[0])
        return None


# PUBLIC_INTERFACE
def upsert_pending(settings: Settings, email: str, password: str, code: str, code_expires_at_iso: str) -> PendingSignup:
    """Insert or update a pending signup row with new verification code and expiry."""
    payload = [{
        "email": email,
        "password": password,
        "verification_code": code,
        "code_expires_at": code_expires_at_iso,
        "attempts": 0,
    }]
    with httpx.Client(timeout=20) as client:
        resp = client.post(_endpoint(settings), headers=_headers(settings), json=payload)
        if resp.status_code >= 400:
            raise RuntimeError(f"pending_signups upsert failed: {resp.status_code} {resp.text}")
        data = resp.json()
        row = data[0] if isinstance(data, list) and data else data
        return PendingSignup.from_dict(row)


# PUBLIC_INTERFACE
def increment_attempts(settings: Settings, email: str) -> None:
    """Increment attempts counter for a pending signup."""
    row = get_pending_by_email(settings, email)
    new_attempts = (row.attempts + 1) if row else 1
    ep = f"{_endpoint(settings)}?email=eq.{email}"
    payload = {"attempts": new_attempts}
    with httpx.Client(timeout=20) as client:
        resp = client.patch(ep, headers=_headers(settings), json=payload)
        if resp.status_code >= 400:
            # Non-fatal: do not raise to caller for throttling counter
            return


# PUBLIC_INTERFACE
def delete_pending(settings: Settings, email: str) -> None:
    """Delete a pending signup row after successful verification or abandonment."""
    ep = f"{_endpoint(settings)}?email=eq.{email}"
    with httpx.Client(timeout=20) as client:
        resp = client.delete(ep, headers=_headers(settings))
        if resp.status_code >= 400:
            # Non-fatal cleanup error
            return


# PUBLIC_INTERFACE
def purge_expired(settings: Settings) -> int:
    """
    Delete all pending_signups whose code_expires_at is in the past.

    Returns:
        int: Count of rows deleted (best-effort; 0 if unknown).
    """
    deleted = 0
    try:
        with httpx.Client(timeout=20) as client:
            # Fetch ids and code_expires_at, filter locally based on current UTC time
            list_resp = client.get(f"{_endpoint(settings)}?select=id,code_expires_at", headers=_headers(settings))
            if list_resp.status_code >= 400:
                return 0
            data = list_resp.json()
            rows = data if isinstance(data, list) else []
            import datetime as _dt
            now = _dt.datetime.now(_dt.timezone.utc)
            expired_ids = []
            for r in rows:
                exp_raw = r.get("code_expires_at")
                try:
                    exp_dt = _dt.datetime.fromisoformat(str(exp_raw).replace("Z", "+00:00"))
                except Exception:
                    exp_dt = None
                if exp_dt and exp_dt < now:
                    rid = r.get("id")
                    if rid:
                        expired_ids.append(rid)
            if not expired_ids:
                return 0
            in_list = ",".join(expired_ids)
            del_ep = f"{_endpoint(settings)}?id=in.({in_list})"
            del_resp = client.delete(del_ep, headers=_headers(settings))
            if del_resp.status_code >= 400:
                return 0
            deleted = len(expired_ids)
    except Exception:
        return 0
    return deleted
