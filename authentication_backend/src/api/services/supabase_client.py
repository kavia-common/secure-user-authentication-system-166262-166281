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
    """Minimal Supabase admin client using REST endpoints via httpx.

    This client MUST be initialized with the Supabase Service Role key.
    Do not pass the anon/public key here; admin endpoints will return 403 not_admin.
    """
    url: str
    service_role_key: str

    @property
    def _headers(self) -> Dict[str, str]:
        # Ensure we never accidentally put a blank or whitespace-padded key
        srk = (self.service_role_key or "").strip()
        if not srk:
            raise RuntimeError("Supabase Service Role key is missing; cannot perform admin requests")
        return {
            # Both headers are required by Supabase admin endpoints
            "apikey": srk,
            "Authorization": f"Bearer {srk}",
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
                    detail = resp.text
                    if resp.status_code == 403 and "not_admin" in detail:
                        raise RuntimeError(
                            "Supabase create_user failed with 403 not_admin. "
                            "Ensure SUPABASE_SERVICE_ROLE_KEY (service role) is configured in backend and used for admin calls. "
                            "Do not use anon/public keys."
                        )
                    raise RuntimeError(f"Supabase create_user failed: {resp.status_code} {detail}")
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

    # PUBLIC_INTERFACE
    def password_sign_in(self, email: str, password: str) -> Dict[str, Any]:
        """
        Perform password sign in and return the token response.

        Uses the /token endpoint with grant_type=password.
        """
        endpoint = self._auth_url("/token")
        payload = {
            "grant_type": "password",
            "email": email,
            "password": password,
        }
        headers = {
            **self._headers,
            # Form-encoded is the canonical method, but JSON is also accepted by Supabase GoTrue.
            # Keep JSON for simplicity with our httpx client.
        }
        try:
            with httpx.Client(timeout=20) as client:
                resp = client.post(endpoint, headers=headers, json=payload)
                if resp.status_code >= 400:
                    raise RuntimeError(f"Supabase sign-in failed: {resp.status_code} {resp.text}")
                return resp.json()
        except Exception as exc:
            raise RuntimeError(f"Supabase password_sign_in error: {exc}") from exc

    # PUBLIC_INTERFACE
    def admin_update_password_by_email(self, email: str, new_password: str) -> Dict[str, Any]:
        """
        Update user password via Admin API by email.

        Steps:
        - List users with the filter email eq.
        - Pick first matching user and update password.
        """
        # 1) Get user by email
        list_ep = self._auth_url("/admin/users")
        params = {"email": email}
        try:
            with httpx.Client(timeout=20) as client:
                list_resp = client.get(list_ep, headers=self._headers, params=params)
                if list_resp.status_code >= 400:
                    raise RuntimeError(f"Supabase get user failed: {list_resp.status_code} {list_resp.text}")
                data = list_resp.json()
                # data may be either list or object depending on API version; handle both
                if isinstance(data, dict) and "users" in data:
                    users = data.get("users") or []
                elif isinstance(data, list):
                    users = data
                else:
                    users = []
                if not users:
                    raise RuntimeError("User not found")

                user_id = users[0].get("id")
                if not user_id:
                    raise RuntimeError("User id not found")

                # 2) Update password
                upd_ep = self._auth_url(f"/admin/users/{user_id}")
                upd_payload = {"password": new_password}
                upd_resp = client.put(upd_ep, headers=self._headers, json=upd_payload)
                if upd_resp.status_code >= 400:
                    raise RuntimeError(f"Supabase update password failed: {upd_resp.status_code} {upd_resp.text}")
                return upd_resp.json()
        except Exception as exc:
            raise RuntimeError(f"Supabase admin_update_password_by_email error: {exc}") from exc
