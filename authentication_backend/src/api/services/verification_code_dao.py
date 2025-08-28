"""
Data access helpers for app.verification_codes in Supabase Postgres.

This module provides server-side only helpers for creating and consuming
short-lived verification codes (email verification, password reset).
It uses the Supabase PostgREST endpoint with the Service Role key.

Note: Current API routes rely on Supabase email links. If you later add
code-based flows, you can wire these helpers into the endpoints.
"""
from __future__ import annotations

import time
import secrets
from dataclasses import dataclass
from typing import Optional, Literal, Dict, Any

import httpx

Purpose = Literal["email_verification", "password_reset"]


@dataclass
class PostgrestClient:
    """Minimal client for Supabase PostgREST with service role key."""
    url: str
    service_role_key: str

    @property
    def _base(self) -> str:
        return self.url.rstrip("/")

    @property
    def _headers(self) -> Dict[str, str]:
        return {
            "apikey": self.service_role_key,
            "Authorization": f"Bearer {self.service_role_key}",
            "Content-Type": "application/json",
            "Accept-Profile": "app",
            "Content-Profile": "app",
            "Accept": "application/json",
            "Prefer": "return=representation",
        }

    def insert(self, table: str, row: Dict[str, Any]) -> Dict[str, Any]:
        """
        Insert a row and return the representation.

        Raises:
            RuntimeError: with detailed status code and response body on failure.
        """
        endpoint = f"{self._base}/rest/v1/{table}"
        with httpx.Client(timeout=20) as client:
            resp = client.post(endpoint, headers=self._headers, json=row)
            # PostgREST returns 201/200 with body when Prefer: return=representation
            if resp.status_code >= 400:
                body = resp.text
                raise RuntimeError(f"PostgREST insert failed ({table}): {resp.status_code} {body}")
            # Some setups may return 201 with an array
            try:
                data = resp.json()
            except Exception:
                # If no JSON body, return the sent row (best-effort)
                return row
            if isinstance(data, list):
                return data[0] if data else {}
            return data

    def update(self, table: str, values: Dict[str, Any], filters: str) -> Dict[str, Any]:
        endpoint = f"{self._base}/rest/v1/{table}?{filters}"
        with httpx.Client(timeout=20) as client:
            resp = client.patch(endpoint, headers=self._headers, json=values)
            if resp.status_code >= 400:
                raise RuntimeError(f"PostgREST update failed ({table}): {resp.status_code} {resp.text}")
            try:
                data = resp.json()
            except Exception:
                # No body returned
                return {}
            if isinstance(data, list):
                return data[0] if data else {}
            return data

    def select_one(self, table: str, filters: str, order: Optional[str] = None) -> Optional[Dict[str, Any]]:
        endpoint = f"{self._base}/rest/v1/{table}?{filters}"
        if order:
            endpoint += f"&order={order}"
        with httpx.Client(timeout=20) as client:
            resp = client.get(endpoint, headers={**self._headers, "Accept": "application/json"})
            if resp.status_code == 406:
                # Not acceptable (e.g., no rows and no representation allowed) - treat as not found
                return None
            if resp.status_code >= 400:
                raise RuntimeError(f"PostgREST select failed ({table}): {resp.status_code} {resp.text}")
            data = resp.json()
            if isinstance(data, list):
                return data[0] if data else None
            return data or None


def _now_ts() -> int:
    return int(time.time())


def _gen_code(length: int = 6) -> str:
    """
    Generate a numeric verification code of given length (default 6 digits).
    """
    digits = "0123456789"
    # Ensure first digit is non-zero to avoid leading zeros confusion in some clients
    first = secrets.choice("123456789")
    rest = "".join(secrets.choice(digits) for _ in range(max(0, length - 1)))
    return first + rest


@dataclass
class VerificationCodeDAO:
    """Server-side DAO for verification codes table."""
    supabase_url: str
    service_role_key: str
    default_ttl_sec: int = 600  # 10 minutes

    @property
    def _pg(self) -> PostgrestClient:
        return PostgrestClient(url=self.supabase_url, service_role_key=self.service_role_key)

    # PUBLIC_INTERFACE
    def create_code(self, user_id: str, email: str, purpose: Purpose, *, ttl_seconds: Optional[int] = None, length: int = 6) -> Dict[str, Any]:
        """
        Create a short-lived verification code for a user.

        Returns the inserted row including the 'code'. Intended for server-side use only.
        """
        ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl_sec
        expires_at = int((_now_ts() + ttl))
        # Postgres timestamptz accepts ISO format, but we can let PostgREST cast from epoch by to_timestamp()
        # However, simpler: send ISO8601 by computing on the client. Here we rely on SQL default and explicit string.
        # We'll compute ISO8601 now.
        import datetime as _dt
        expires_iso = _dt.datetime.utcfromtimestamp(expires_at).isoformat() + "Z"

        # Try to insert, retrying on unique constraint/duplicate conflicts
        attempts = 0
        last_err: Optional[Exception] = None
        while attempts < 5:
            code = _gen_code(length)
            row = {
                "user_id": user_id,
                "email": email,
                "purpose": purpose,
                "code": code,
                "expires_at": expires_iso,
            }
            try:
                created = self._pg.insert("verification_codes", row)
                return created
            except Exception as exc:
                msg = str(exc).lower()
                # Detect duplicate key/unique violation or conflict
                if "duplicate key" in msg or "unique constraint" in msg or "uq_active_code" in msg or "409" in msg or "conflict" in msg:
                    attempts += 1
                    last_err = exc
                    continue
                # For other errors, do not retry
                raise
        # If we exhausted retries, raise a descriptive error
        raise RuntimeError(f"Failed to create verification code after retries: {last_err}")

    # PUBLIC_INTERFACE
    def consume_code(self, email: str, purpose: Purpose, code: str) -> Optional[Dict[str, Any]]:
        """
        Validate and consume a code if valid and not expired.

        Returns the updated row if successful, else None.
        """
        # Find the latest matching active code
        filters = f"email=eq.{email}&purpose=eq.{purpose}&code=eq.{code}&consumed_at=is.null"
        row = self._pg.select_one("verification_codes", filters=filters, order="created_at.desc")
        if not row:
            return None

        # Check expiry
        import datetime as _dt
        expires_at = row.get("expires_at")
        if isinstance(expires_at, str):
            try:
                exp = _dt.datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            except Exception:
                exp = None
        else:
            exp = None
        if not exp or exp < _dt.datetime.now(_dt.timezone.utc):
            return None

        # Mark consumed
        import datetime as _dt2
        consumed_iso = _dt2.datetime.utcnow().isoformat() + "Z"
        filters_pk = f"id=eq.{row['id']}"
        updated = self._pg.update("verification_codes", {"consumed_at": consumed_iso}, filters_pk)
        return updated
