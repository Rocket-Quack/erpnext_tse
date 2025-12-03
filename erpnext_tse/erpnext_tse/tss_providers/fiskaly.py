# Copyright (c) 2025, RocketQuackIT and contributors
# For license information, please see LICENSE

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import frappe
import requests
from frappe.utils import now_datetime

from .base import BaseTSEProvider

logger = logging.getLogger("erpnext_tse.fiskaly")


class FiskalyProvider(BaseTSEProvider):
    """Implementation of the TSE provider interface for Fiskaly SIGN DE."""

    # ---------------------------------------------------------------------
    # Helpers reading / writing from the settings document
    # ---------------------------------------------------------------------

    @property
    def doc(self):
        """Shortcut to the underlying TSE Settings document."""
        return self.settings

    def _debug_enabled(self) -> bool:
        return bool(getattr(self.doc, "enable_debug_logging", False))

    def _log(self, level: int, msg: str, **extra):
        if not self._debug_enabled():
            return
        if extra:
            logger.log(level, msg, extra=extra)
        else:
            logger.log(level, msg)

    # --- configuration from settings ------------------------------------

    def get_base_url(self) -> str:
        base_url = self.doc.base_url or "https://kassensichv-middleware.fiskaly.com/api/v2"
        return base_url.rstrip("/")

    def get_api_credentials(self) -> tuple[str, str]:
        api_key = self.doc.get_password("api_key")
        api_secret = self.doc.get_password("api_secret")

        if not api_key or not api_secret:
            frappe.throw("Please enter API Key and API Secret in TSE Settings.")

        return api_key, api_secret

    # --- token helpers ---------------------------------------------------

    def _clear_token_fields(self):
        """Clear all token-related fields when authentication is no longer valid."""
        self.doc.access_token = None
        self.doc.access_token_expires_at = None
        self.doc.refresh_token = None
        self.doc.refresh_token_expires_at = None
        self.doc.organization_id = None
        self.doc.token_environment = None

    def get_access_token(self) -> str | None:
        return self.doc.get_password("access_token") or None

    def get_refresh_token(self) -> str | None:
        return self.doc.get_password("refresh_token") or None

    def is_access_token_valid(self, skew_seconds: int = 60) -> bool:
        token = self.get_access_token()
        expires_at = self.doc.access_token_expires_at

        if not token or not expires_at:
            return False

        delta = (expires_at - now_datetime()).total_seconds()
        return delta > skew_seconds

    def ensure_valid_access_token(self) -> str:
        """Return a valid access token, refreshing it if necessary."""
        if self.is_access_token_valid():
            token = self.get_access_token()
            if token:
                return token

        # Token fehlt oder abgelaufen → neu authentifizieren
        data = self.run_auth_request()
        self.update_from_auth_response(data)

        token = self.get_access_token()
        if not token:
            frappe.throw("Could not obtain a valid access token from Fiskaly.")
        return token

    # --- error handling helpers -----------------------------------------

    def _parse_error_response(self, response: requests.Response) -> dict:
        try:
            data = response.json()
        except ValueError:
            self._log(
                logging.WARNING,
                "Auth error response is not JSON",
                status_code=response.status_code,
                reason=response.reason,
                raw_body_preview=response.text[:500],
            )
            return {
                "status_code": response.status_code,
                "error": response.reason,
                "code": None,
                "message": response.text,
            }

        return {
            "status_code": data.get("status_code", response.status_code),
            "error": data.get("error", response.reason),
            "code": data.get("code"),
            "message": data.get("message") or "",
        }

    def _store_auth_error(self, status: str, error_code: str | None, message: str):
        details = f"code={error_code}, message={message}" if error_code else message

        self._log(
            logging.ERROR,
            "Storing auth error on TSESettings (Fiskaly)",
            auth_status=status,
            auth_error_code=error_code,
            auth_error_message=message,
            docname=self.doc.name,
        )

        self.doc.last_auth_status = status
        self.doc.last_auth_message = details
        self.doc.last_auth_at = now_datetime()
        self.doc.save(ignore_permissions=True)
        frappe.db.commit()

    # ---------------------------------------------------------------------
    # Auth flow (basically dein bisheriger Code, aber auf self.doc)
    # ---------------------------------------------------------------------

    def run_auth_request(self) -> dict:
        base_url = self.get_base_url()
        api_key, api_secret = self.get_api_credentials()
        url = f"{base_url}/auth"

        self._log(
            logging.INFO,
            "Calling Fiskaly /auth",
            base_url=base_url,
            url=url,
        )

        try:
            response = requests.post(
                url,
                json={
                    "api_key": api_key,
                    "api_secret": api_secret,
                },
                timeout=15,
            )
        except requests.RequestException as exc:
            self._log(
                logging.ERROR,
                "Network error during Fiskaly /auth",
                request_url=url,
            )
            self._store_auth_error(
                status="NETWORK_ERROR",
                error_code="E_NETWORK_ERROR",
                message=str(exc),
            )
            frappe.throw(f"Could not reach Fiskaly auth endpoint: {exc}")

        try:
            body_preview = response.text[:500]
        except Exception:
            body_preview = "<failed to read body>"

        self._log(
            logging.INFO,
            "Fiskaly /auth response received",
            status_code=response.status_code,
            reason=response.reason,
            body_preview=body_preview,
        )

        # 401 → Credentials falsch / Token invalide
        if response.status_code == 401:
            err = self._parse_error_response(response)
            self._clear_token_fields()
            self._store_auth_error(
                status="401_UNAUTHORIZED",
                error_code=err.get("code"),
                message=err.get("message") or err.get("error") or "Unauthorized",
            )
            frappe.throw(
                f"Authentication failed (401). "
                f"Error code: {err.get('code') or 'N/A'}, message: {err.get('message') or err.get('error')}"
            )

        if 400 <= response.status_code < 500:
            err = self._parse_error_response(response)
            self._clear_token_fields()
            self._store_auth_error(
                status=f"{response.status_code}_CLIENT_ERROR",
                error_code=err.get("code"),
                message=err.get("message") or err.get("error") or "Client error",
            )
            frappe.throw(
                f"Fiskaly returned a client error ({response.status_code}). "
                f"Error code: {err.get('code') or 'N/A'}, message: {err.get('message') or err.get('error')}"
            )

        if 500 <= response.status_code < 600:
            err = self._parse_error_response(response)
            self._store_auth_error(
                status=f"{response.status_code}_SERVER_ERROR",
                error_code=err.get("code"),
                message=err.get("message") or err.get("error") or "Server error",
            )
            frappe.throw(
                f"Fiskaly server error ({response.status_code}). "
                f"Please try again later or check status.fiskaly.com. "
                f"Details: {err.get('message') or err.get('error')}"
            )

        try:
            data = response.json()
        except ValueError as exc:
            self._log(
                logging.ERROR,
                "Could not parse /auth response as JSON",
                body_preview=body_preview,
            )
            self._store_auth_error(
                status="PARSE_ERROR",
                error_code="E_INVALID_JSON",
                message=f"Could not parse JSON response: {exc}",
            )
            frappe.throw(f"Could not parse Fiskaly auth response as JSON: {exc}")

        return data

    def update_from_auth_response(self, data: dict) -> dict:
        self._log(
            logging.INFO,
            "Updating TSESettings from auth response",
            has_access_token=bool(data.get("access_token")),
            top_level_keys=list(data.keys()),
        )

        if not data.get("access_token"):
            err_code = data.get("code")
            msg = data.get("message") or data.get("error") or "Auth response did not contain an access_token."

            self._log(
                logging.WARNING,
                "Auth response without access_token, treating as AUTH_ERROR",
                error_code=err_code,
                error_message=msg,
            )

            self._clear_token_fields()
            self._store_auth_error(
                status="AUTH_ERROR",
                error_code=err_code,
                message=msg,
            )
            frappe.throw(
                f"Authentication failed. "
                f"Error code: {err_code or 'N/A'}, message: {msg}"
            )

        claims = data.get("access_token_claims") or {}

        # Token values (Password fields on doc)
        self.doc.access_token = data.get("access_token")
        self.doc.refresh_token = data.get("refresh_token")

        access_exp = data.get("access_token_expires_at")
        refresh_exp = data.get("refresh_token_expires_at")

        if access_exp:
            self.doc.access_token_expires_at = datetime.fromtimestamp(access_exp)
        if refresh_exp:
            self.doc.refresh_token_expires_at = datetime.fromtimestamp(refresh_exp)

        self.doc.organization_id = claims.get("organization_id")
        self.doc.token_environment = claims.get("env")

        self.doc.last_auth_at = now_datetime()
        self.doc.last_auth_base_url = self.get_base_url()
        self.doc.last_auth_status = "OK"
        self.doc.last_auth_message = (
            f"env={claims.get('env')}, organization_id={claims.get('organization_id')}"
        )

        self.doc.save(ignore_permissions=True)
        frappe.db.commit()

        return {
            "status": "OK",
            "environment": claims.get("env"),
            "organization_id": claims.get("organization_id"),
            "access_token_expires_at": access_exp,
        }

    # ---------------------------------------------------------------------
    # Provider interface implementation
    # ---------------------------------------------------------------------

    def test_auth(self) -> dict[str, Any]:
        """Force a fresh /auth call and overwrite all token fields.

        This is used by the 'Test Auth' button in the UI.
        """
        # Alte Tokens im DocTyp entfernen
        self._clear_token_fields()

        # /auth gegen Schnittstelle von Fiskaly
        data = self.run_auth_request()

        # Antwort in den TSE Settings speichern (Access/Refresh Token, Expiry, Org-ID, etc.)
        return self.update_from_auth_response(data)

    def request(self, method: str, path: str, **kwargs) -> requests.Response:
        """Generic API call using bearer token + 401-retry."""
        base_url = self.get_base_url()
        url = f"{base_url.rstrip('/')}/{path.lstrip('/')}"

        token = self.ensure_valid_access_token()

        headers = kwargs.pop("headers", {}) or {}
        headers.setdefault("Authorization", f"Bearer {token}")
        headers.setdefault("Content-Type", "application/json")

        self._log(
            logging.INFO,
            "Calling Fiskaly endpoint",
            method=method,
            url=url,
        )

        resp = requests.request(method, url, headers=headers, timeout=15, **kwargs)
        if resp.status_code != 401:
            return resp

        # 401 → einmal neu auth + retry
        self._log(
            logging.WARNING,
            "Received 401 from Fiskaly, retrying once after reauth",
            method=method,
            url=url,
        )

        data = self.run_auth_request()
        self.update_from_auth_response(data)
        token = self.ensure_valid_access_token()

        headers["Authorization"] = f"Bearer {token}"
        return requests.request(method, url, headers=headers, timeout=15, **kwargs)
