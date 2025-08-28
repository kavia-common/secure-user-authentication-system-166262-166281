"""
Supabase admin client wrapper.

Note:
- We avoid adding the official supabase-py dependency to keep the initial scaffold lean.
- This wrapper can be expanded to include specific REST calls to Supabase Auth Admin API using httpx.
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional

import httpx


@dataclass
class SupabaseAdminClient:
    """Minimal Supabase admin client using REST endpoints via httpx."""
    url: str
    service_role_key: str

    @property
    def _headers(self) -> Dict[str, str]:
        return {
            "apikey": self.service_role_key,
            "Authorization": f"Bearer {self.service_role_key}",
            "Content-Type": "application/json",
        }

    def _auth_url(self, path: str) -> str:
        # Supabase auth endpoints are at {url}/auth/v1
        base = self.url.rstrip("/")
        return f"{base}/auth/v1{path}"

    # PUBLIC_INTERFACE
    def create_user(self, email: str, password: str) -> Dict[str, Any]:
        """
        Create a user via Supabase Auth Admin.

        Returns the created user payload on success.
        Raises RuntimeError on failure.
        """
        endpoint = self._auth_url("/admin/users")
        payload = {"email": email, "password": password, "email_confirm": False}
        try:
            with httpx.Client(timeout=20) as client:
                resp = client.post(endpoint, headers=self._headers, json=payload)
                if resp.status_code >= 400:
                    raise RuntimeError(f"Supabase create_user failed: {resp.status_code} {resp.text}")
                return resp.json()
        except Exception as exc:
            raise RuntimeError(f"Supabase create_user error: {exc}") from exc

    # PUBLIC_INTERFACE
    def generate_link(self, email: str, link_type: str, redirect_to: Optional[str] = None) -> Dict[str, Any]:
        """
        Request a magic link or verification link via Supabase Auth Admin.

        link_type: 'magiclink' | 'recovery' | 'invite' | 'signup' | 'email_change_current' | 'email_change_new' | 'phone_change'
        """
        endpoint = self._auth_url("/admin/generate_link")
        payload: Dict[str, Any] = {"type": link_type, "email": email}
        if redirect_to:
            payload["redirect_to"] = redirect_to
        try:
            with httpx.Client(timeout=20) as client:
                resp = client.post(endpoint, headers=self._headers, json=payload)
                if resp.status_code >= 400:
                    raise RuntimeError(f"Supabase generate_link failed: {resp.status_code} {resp.text}")
                return resp.json()
        except Exception as exc:
            raise RuntimeError(f"Supabase generate_link error: {exc}") from exc
