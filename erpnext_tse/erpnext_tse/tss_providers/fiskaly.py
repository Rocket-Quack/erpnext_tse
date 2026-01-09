# Copyright (c) 2025, RocketQuackIT and contributors
# For license information, please see LICENSE

from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime
from typing import Any

import frappe
import requests
from frappe import _
from frappe.utils import get_datetime, now_datetime

from .base import BaseTSEProvider

logger = logging.getLogger("erpnext_tse.fiskaly")

TOKEN_SCOPE_TSE = "tse"
TOKEN_SCOPE_DSFINVK = "dsfinvk"
RATE_LIMIT_STATUS = 429
RATE_LIMIT_ERROR_CODES = {"E_TOO_MANY_REQUESTS"}
RATE_LIMIT_MAX_RETRIES = 5
RATE_LIMIT_BASE_DELAY_SECONDS = 1.0


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

	def get_dsfinvk_base_url(self) -> str:
		"""Base-URL fuer DSFinV-K Export-API (separater Host)."""
		base_url = getattr(self.doc, "dsfinvk_base_url", None) or "https://dsfinvk.fiskaly.com/api/v1"
		return base_url.rstrip("/")

	def get_api_credentials(self) -> tuple[str, str]:
		api_key = self.doc.get_password("api_key")
		api_secret = self.doc.get_password("api_secret")

		if not api_key or not api_secret:
			frappe.throw(_("Please enter TSE API Key and API Secret in TSE Settings."))

		return api_key, api_secret

	def get_dsfinvk_api_credentials(self) -> tuple[str, str]:
		api_key = self.doc.get_password("dsfinvk_api_key")
		api_secret = self.doc.get_password("dsfinvk_api_secret")

		if api_key or api_secret:
			if not api_key or not api_secret:
				frappe.throw(_("Please enter DSFinV-K API Key and API Secret in TSE Settings."))
			return api_key, api_secret

		return self.get_api_credentials()

	# --- token helpers ---------------------------------------------------

	def _token_field(self, scope: str, base: str) -> str:
		if scope == TOKEN_SCOPE_TSE:
			return base
		if scope == TOKEN_SCOPE_DSFINVK:
			return f"dsfinvk_{base}"
		raise ValueError(f"Unsupported token scope: {scope}")

	def _get_password_field(self, scope: str, base: str) -> str | None:
		fieldname = self._token_field(scope, base)
		return self.doc.get_password(fieldname) or None

	def _get_field(self, scope: str, base: str) -> Any:
		return getattr(self.doc, self._token_field(scope, base), None)

	def _set_field(self, scope: str, base: str, value: Any):
		setattr(self.doc, self._token_field(scope, base), value)

	def _clear_token_fields(self, scope: str = TOKEN_SCOPE_TSE):
		"""Clear all token-related fields when authentication is no longer valid."""
		for field in (
			"access_token",
			"access_token_expires_at",
			"refresh_token",
			"refresh_token_expires_at",
			"organization_id",
			"token_environment",
		):
			self._set_field(scope, field, None)

	def get_access_token(self, scope: str = TOKEN_SCOPE_TSE) -> str | None:
		return self._get_password_field(scope, "access_token")

	def get_refresh_token(self, scope: str = TOKEN_SCOPE_TSE) -> str | None:
		return self._get_password_field(scope, "refresh_token")

	def is_access_token_valid(self, scope: str = TOKEN_SCOPE_TSE, skew_seconds: int = 60) -> bool:
		token = self.get_access_token(scope=scope)
		expires_at = self._get_field(scope, "access_token_expires_at")

		if not token or not expires_at:
			return False

		# Frappe speichert Datetime-Felder als string → daher muss dieser wieder in datetime umgewandelt werden
		expires_dt = get_datetime(expires_at)

		delta = (expires_dt - now_datetime()).total_seconds()
		return delta > skew_seconds

	def ensure_valid_access_token(
		self,
		api_key: str | None = None,
		api_secret: str | None = None,
		scope: str = TOKEN_SCOPE_TSE,
	) -> str:
		"""Return a valid access token, refreshing it if necessary."""
		if self.is_access_token_valid(scope=scope):
			token = self.get_access_token(scope=scope)
			if token:
				return token

		# Token fehlt oder abgelaufen → neu authentifizieren
		data = self.run_auth_request(api_key=api_key, api_secret=api_secret, scope=scope)
		self.update_from_auth_response(data, scope=scope)

		token = self.get_access_token(scope=scope)
		if not token:
			frappe.throw(_("Could not obtain a valid access token from Fiskaly."))
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

	def _retry_after_seconds(self, response: requests.Response) -> int | None:
		raw = response.headers.get("Retry-After")
		if not raw:
			return None
		raw = str(raw).strip()
		if raw.isdigit():
			return max(0, int(raw))
		return None

	def _should_retry_rate_limit(self, status: int, err: dict[str, Any] | None, attempt: int) -> bool:
		if attempt >= RATE_LIMIT_MAX_RETRIES:
			return False
		if status == RATE_LIMIT_STATUS:
			return True
		if err and err.get("code") in RATE_LIMIT_ERROR_CODES:
			return True
		return False

	def _sleep_rate_limit(self, attempt: int, response: requests.Response) -> None:
		retry_after = self._retry_after_seconds(response)
		if retry_after is not None:
			delay = retry_after
		else:
			delay = RATE_LIMIT_BASE_DELAY_SECONDS * (2**attempt)
		if delay <= 0:
			return
		self._log(
			logging.WARNING,
			"Fiskaly rate limit hit, backing off",
			delay=delay,
			attempt=attempt + 1,
		)
		time.sleep(delay)

	def _request_json_with_retry(
		self,
		request_func,
		error_label: str,
		method: str,
		path: str,
		**kwargs,
	) -> dict[str, Any]:
		for attempt in range(RATE_LIMIT_MAX_RETRIES + 1):
			resp = request_func(method, path, **kwargs)
			status = resp.status_code
			try:
				data = resp.json()
			except ValueError:
				err = self._parse_error_response(resp)
				if self._should_retry_rate_limit(status, err, attempt):
					self._sleep_rate_limit(attempt, resp)
					continue
				frappe.throw(
					_("{0} returned a non-JSON response ({1}). Error: {2}").format(
						error_label, status, err.get("message") or err.get("error")
					)
				)

			if "status_code" not in data:
				data["status_code"] = status

			if 200 <= status < 300:
				return data

			err = {
				"status_code": data.get("status_code", status),
				"error": data.get("error", resp.reason),
				"code": data.get("code"),
				"message": data.get("message") or "",
			}
			if self._should_retry_rate_limit(status, err, attempt):
				self._sleep_rate_limit(attempt, resp)
				continue

			frappe.throw(
				_("{0} returned an error ({1}). Code: {2}, Message: {3}").format(
					error_label,
					status,
					err.get("code") or "N/A",
					err.get("message") or err.get("error") or "Unknown error",
				)
			)

	def _store_auth_error(
		self,
		status: str,
		error_code: str | None,
		message: str,
		scope: str = TOKEN_SCOPE_TSE,
	):
		details = f"code={error_code}, message={message}" if error_code else message

		self._log(
			logging.ERROR,
			"Storing auth error on TSESettings (Fiskaly)",
			auth_status=status,
			auth_error_code=error_code,
			auth_error_message=message,
			docname=self.doc.name,
		)

		self._set_field(scope, "last_auth_status", status)
		self._set_field(scope, "last_auth_message", details)
		self._set_field(scope, "last_auth_at", now_datetime())
		self.doc.save(ignore_permissions=True)
		frappe.db.commit()

	# ---------------------------------------------------------------------
	# Auth flow
	# ---------------------------------------------------------------------

	def run_auth_request(
		self,
		api_key: str | None = None,
		api_secret: str | None = None,
		scope: str = TOKEN_SCOPE_TSE,
	) -> dict:
		base_url = self.get_base_url()
		if api_key is None or api_secret is None:
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
				scope=scope,
			)
			frappe.throw(_("Could not reach Fiskaly auth endpoint: {0}").format(exc))

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
			self._clear_token_fields(scope=scope)
			self._store_auth_error(
				status="401_UNAUTHORIZED",
				error_code=err.get("code"),
				message=err.get("message") or err.get("error") or "Unauthorized",
				scope=scope,
			)
			frappe.throw(
				_("Authentication failed (401). Error code: {0}, message: {1}").format(
					err.get("code") or "N/A", err.get("message") or err.get("error")
				)
			)

		if 400 <= response.status_code < 500:
			err = self._parse_error_response(response)
			self._clear_token_fields(scope=scope)
			self._store_auth_error(
				status=f"{response.status_code}_CLIENT_ERROR",
				error_code=err.get("code"),
				message=err.get("message") or err.get("error") or "Client error",
				scope=scope,
			)
			frappe.throw(
				_("Fiskaly returned a client error ({0}). Error code: {1}, message: {2}").format(
					response.status_code,
					err.get("code") or "N/A",
					err.get("message") or err.get("error"),
				)
			)

		if 500 <= response.status_code < 600:
			err = self._parse_error_response(response)
			self._store_auth_error(
				status=f"{response.status_code}_SERVER_ERROR",
				error_code=err.get("code"),
				message=err.get("message") or err.get("error") or "Server error",
				scope=scope,
			)
			frappe.throw(
				_(
					"Fiskaly server error ({0}). Please try again later or check status.fiskaly.com. "
					"Details: {1}"
				).format(response.status_code, err.get("message") or err.get("error"))
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
				scope=scope,
			)
			frappe.throw(_("Could not parse Fiskaly auth response as JSON: {0}").format(exc))

		return data

	def update_from_auth_response(self, data: dict, scope: str = TOKEN_SCOPE_TSE) -> dict:
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

			self._clear_token_fields(scope=scope)
			self._store_auth_error(
				status="AUTH_ERROR",
				error_code=err_code,
				message=msg,
				scope=scope,
			)
			frappe.throw(
				_("Authentication failed. Error code: {0}, message: {1}").format(err_code or "N/A", msg)
			)

		claims = data.get("access_token_claims") or {}

		# Token values (Password fields on doc)
		self._set_field(scope, "access_token", data.get("access_token"))
		self._set_field(scope, "refresh_token", data.get("refresh_token"))

		access_exp = data.get("access_token_expires_at")
		refresh_exp = data.get("refresh_token_expires_at")

		if access_exp:
			self._set_field(scope, "access_token_expires_at", datetime.fromtimestamp(access_exp))
		if refresh_exp:
			self._set_field(scope, "refresh_token_expires_at", datetime.fromtimestamp(refresh_exp))

		self._set_field(scope, "organization_id", claims.get("organization_id"))
		self._set_field(scope, "token_environment", claims.get("env"))

		self._set_field(scope, "last_auth_at", now_datetime())
		self._set_field(scope, "last_auth_base_url", self.get_base_url())
		self._set_field(scope, "last_auth_status", "OK")
		self._set_field(
			scope,
			"last_auth_message",
			f"env={claims.get('env')}, organization_id={claims.get('organization_id')}",
		)

		self.doc.save(ignore_permissions=True)
		frappe.db.commit()

		return {
			"status": "OK",
			"environment": claims.get("env"),
			"organization_id": claims.get("organization_id"),
			"access_token_expires_at": access_exp,
		}

	def authenticate_admin(self, tss_id: str, admin_pin: str) -> dict[str, Any]:
		"""Admin-Authentifizierung für eine TSS (authenticateAdmin)."""
		payload = {
			"admin_pin": admin_pin,
		}

		return self._request_json(
			method="POST",
			path=f"/tss/{tss_id}/admin/auth",
			json=payload,
		)

	def change_admin_pin(self, tss_id: str, admin_puk: str, new_admin_pin: str) -> dict[str, Any]:
		"""Admin-PIN mit Admin-PUK setzen oder zurücksetzen (changeAdminPin). Auch für die Initialisierung einer erstellten TSS"""
		payload = {
			"admin_puk": admin_puk,
			"new_admin_pin": new_admin_pin,
		}

		return self._request_json(
			method="PATCH",
			path=f"/tss/{tss_id}/admin",
			json=payload,
		)

	def logout_admin(self, tss_id: str) -> dict[str, Any]:
		"""Admin-Session explizit beenden (logoutAdmin)."""
		return self._request_json(
			method="POST",
			path=f"/tss/{tss_id}/admin/logout",
		)

	# ---------------------------------------------------------------------
	# Provider interface implementation
	# ---------------------------------------------------------------------

	def test_auth(self) -> dict[str, Any]:
		"""Force a fresh /auth call and overwrite all token fields.

		This is used by the 'Test TSE Auth' button in the UI.
		"""
		# Alte Tokens im DocTyp entfernen
		self._clear_token_fields(scope=TOKEN_SCOPE_TSE)

		# /auth gegen Schnittstelle von Fiskaly
		data = self.run_auth_request(scope=TOKEN_SCOPE_TSE)

		# Antwort in den TSE Settings speichern (Access/Refresh Token, Expiry, Org-ID, etc.)
		return self.update_from_auth_response(data, scope=TOKEN_SCOPE_TSE)

	def test_dsfinvk_auth(self) -> dict[str, Any]:
		"""Force a fresh /auth call for DSFinV-K credentials."""
		self._clear_token_fields(scope=TOKEN_SCOPE_DSFINVK)
		api_key, api_secret = self.get_dsfinvk_api_credentials()
		data = self.run_auth_request(
			api_key=api_key,
			api_secret=api_secret,
			scope=TOKEN_SCOPE_DSFINVK,
		)
		return self.update_from_auth_response(data, scope=TOKEN_SCOPE_DSFINVK)

	def request(self, method: str, path: str, **kwargs) -> requests.Response:
		"""Generic API call using bearer token + 401-retry (core API)."""
		base_url = self.get_base_url()
		url = f"{base_url.rstrip('/')}/{path.lstrip('/')}"

		token = self.ensure_valid_access_token(scope=TOKEN_SCOPE_TSE)

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

		# 401 -> einmal neu auth + retry
		self._log(
			logging.WARNING,
			"Received 401 from Fiskaly, retrying once after reauth",
			method=method,
			url=url,
		)

		data = self.run_auth_request(scope=TOKEN_SCOPE_TSE)
		self.update_from_auth_response(data, scope=TOKEN_SCOPE_TSE)
		token = self.ensure_valid_access_token(scope=TOKEN_SCOPE_TSE)

		headers["Authorization"] = f"Bearer {token}"
		return requests.request(method, url, headers=headers, timeout=15, **kwargs)

	def _dsfinvk_request(self, method: str, path: str, **kwargs) -> requests.Response:
		"""API call for DSFinV-K endpoints (separate host)."""
		base_url = self.get_dsfinvk_base_url()
		url = f"{base_url.rstrip('/')}/{path.lstrip('/')}"

		api_key, api_secret = self.get_dsfinvk_api_credentials()
		token = self.ensure_valid_access_token(
			api_key=api_key,
			api_secret=api_secret,
			scope=TOKEN_SCOPE_DSFINVK,
		)

		headers = kwargs.pop("headers", {}) or {}
		headers.setdefault("Authorization", f"Bearer {token}")
		headers.setdefault("Content-Type", "application/json")

		resp = requests.request(method, url, headers=headers, timeout=30, **kwargs)
		if resp.status_code != 401:
			return resp

		# 401 -> re-auth einmal und Retry
		data = self.run_auth_request(
			api_key=api_key,
			api_secret=api_secret,
			scope=TOKEN_SCOPE_DSFINVK,
		)
		self.update_from_auth_response(data, scope=TOKEN_SCOPE_DSFINVK)
		token = self.ensure_valid_access_token(
			api_key=api_key,
			api_secret=api_secret,
			scope=TOKEN_SCOPE_DSFINVK,
		)

		headers["Authorization"] = f"Bearer {token}"
		return requests.request(method, url, headers=headers, timeout=30, **kwargs)

	def _request_json(self, method: str, path: str, **kwargs) -> dict[str, Any]:
		"""Wrapper um request(), der immer ein Dict zurueckgibt und Fehler schoen aufbereitet."""
		return self._request_json_with_retry(self.request, "Fiskaly", method, path, **kwargs)

	def _dsfinvk_request_json(self, method: str, path: str, **kwargs) -> dict[str, Any]:
		"""JSON-Wrapper fuer DSFinV-K Endpunkte (separater Host)."""
		return self._request_json_with_retry(
			self._dsfinvk_request, "Fiskaly DSFinV-K", method, path, **kwargs
		)

	# ---------------------------------------------------------------------
	# High-Level: TSS-Operationen für TSESecurityDevice
	# ---------------------------------------------------------------------

	def create_tss(self, company: str, description: str | None = None) -> dict[str, Any]:
		"""TSS bei Fiskaly anlegen."""

		# UUID für das anlegen der TSS generieren
		tss_id = str(uuid.uuid4())

		payload = {
			# Beim anlegen einer TSS wird keine Payload benötigt
		}

		data = self._request_json(
			method="PUT",
			path=f"/tss/{tss_id}",
			json=payload,
		)

		data.setdefault("id", tss_id)
		return data

	def deploy_tss(self, tss_id: str) -> dict[str, Any]:
		"""TSS deployen: (State → UNINITIALIZED)."""
		payload = {
			"state": "UNINITIALIZED",
		}

		data = self._request_json(
			method="PATCH",
			path=f"/tss/{tss_id}",
			json=payload,
		)
		return data

	def list_tss(self) -> dict[str, Any]:
		"""Alle TSS abrufen (fuer spaetere Synchronisation)."""
		return self._request_json(
			method="GET",
			path="/tss",
		)

	def get_tss(self, tss_id: str) -> dict[str, Any]:
		"""Einzelne TSS abrufen."""
		return self._request_json(
			method="GET",
			path=f"/tss/{tss_id}",
		)

	def initialize_tss(self, tss_id: str) -> dict[str, Any]:
		"""TSS initialisieren (State → INITIALIZED)."""
		payload = {
			"state": "INITIALIZED",
		}

		data = self._request_json(
			method="PATCH",
			path=f"/tss/{tss_id}",
			json=payload,
		)
		return data

	def disable_tss(self, tss_id: str) -> dict[str, Any]:
		"""TSS deaktivieren (State → DISABLED)."""
		payload = {
			"state": "DISABLED",
		}

		data = self._request_json(
			method="PATCH",
			path=f"/tss/{tss_id}",
			json=payload,
		)
		return data

	# ---------------------------------------------------------------------
	# High-Level: Client-Operationen für TSE Client
	# ---------------------------------------------------------------------

	def create_client(self, tss_id: str, metadata: dict) -> dict[str, Any]:
		"""Client bei Fiskaly für eine TSS anlagen
		Der Client bekommt eine UUIDv4 zugeordnet die beim anlegen erzeugt wird
		"""
		# UUID für einen Client generieren
		client_id = str(uuid.uuid4())
		# UUID für die Serial Number des Clients anlegen
		serial_number = str(uuid.uuid4())

		payload: dict[str, Any] = {
			"serial_number": serial_number,
		}

		if metadata:
			payload["metadata"] = metadata

		data = self._request_json(
			method="PUT",
			path=f"/tss/{tss_id}/client/{client_id}",
			json=payload,
		)
		return data

	def deregister_client(self, tss_id: str, client_id: str) -> dict[str, Any]:
		"""
		Client wird auf den Status "DEREGISTERED" gesetzt und kann somit eine TSS nicht mehr verwenden
		"""

		payload: dict[str, Any] = {
			"state": "DEREGISTERED",
		}

		data = self._request_json(
			method="PATCH",
			path=f"/tss/{tss_id}/client/{client_id}",
			json=payload,
		)
		return data

	def register_client(self, tss_id: str, client_id: str) -> dict[str, Any]:
		"""
		Client wird auf den Status "REGISTERED" gesetzt und kann somit eine TSS wieder verwenden
		"""

		payload: dict[str, Any] = {
			"state": "REGISTERED",
		}

		data = self._request_json(
			method="PATCH",
			path=f"/tss/{tss_id}/client/{client_id}",
			json=payload,
		)
		return data

	def list_clients(self, tss_id: str) -> dict[str, Any]:
		"""Alle Clients einer TSS abrufen (fuer spaetere Synchronisation)."""
		return self._request_json(
			method="GET",
			path=f"/tss/{tss_id}/client",
		)

	def get_client(self, tss_id: str, client_id: str) -> dict[str, Any]:
		"""Einzelnen Client abrufen."""
		return self._request_json(
			method="GET",
			path=f"/tss/{tss_id}/client/{client_id}",
		)

	# ---------------------------------------------------------------------
	# High-Level: Transaction operations (SIGN DE upsertTransaction)
	# ---------------------------------------------------------------------

	def list_transactions(self, tss_id: str, **query_params) -> dict[str, Any]:
		"""Alle Transaktionen einer TSS abrufen (fuer spaetere Synchronisation).

		Unterstuetzt optionale Query-Parameter wie limit, offset, order_by, order.
		"""
		return self._request_json(
			method="GET",
			path=f"/tss/{tss_id}/tx",
			params=query_params or None,
		)

	def get_transaction(self, tss_id: str, tx_id: str) -> dict[str, Any]:
		"""Einzelne Transaktion einer TSS abrufen."""
		return self._request_json(
			method="GET",
			path=f"/tss/{tss_id}/tx/{tx_id}",
		)

	def upsert_transaction(
		self,
		tss_id: str,
		tx_id: str,
		tx_revision: int,
		body: dict[str, Any],
	) -> dict[str, Any]:
		"""
		Low-level Wrapper upsertTransaction.
		Mit dieser werden Transaktionen am ende angelegt oder auch aktualisiert/beendet
		"""

		return self._request_json(
			method="PUT",
			path=f"/tss/{tss_id}/tx/{tx_id}?tx_revision={tx_revision}",
			json=body,
		)

	def start_transaction(
		self,
		tss_id: str,
		client_id: str,
		tx_revision: int,
	) -> dict[str, Any]:
		"""
		Transaktion starten (state=ACTIVE, tx_revision=1)
		Hinweis laut SIGN DE V2: Beim Start sollen type und data leer sein
		DSFinV-K-Vorgabe
		"""

		# UUID für die Transaction generieren dient als ID
		tx_id = str(uuid.uuid4())

		body: dict[str, Any] = {
			"state": "ACTIVE",
			"client_id": client_id,
		}

		return self.upsert_transaction(
			tss_id=tss_id,
			tx_id=tx_id,
			tx_revision=tx_revision,
			body=body,
		)

	def finish_transaction(
		self,
		tss_id: str,
		tx_revision: int,
		tx_id: str,
		client_id: str,
		schema: dict[str, Any],
		state: str = "FINISHED",
	) -> dict[str, Any]:
		"""
		Transaktion beenden
		State=FINISHED
		tx_revision muss gegenüber dem Start-Aufruf erhöht sein (Start=1 -> Finish=2) Fortlaufender Zähler für eine Transaktion
		"""
		body: dict[str, Any] = {
			"schema": schema,
			"state": state,
			"client_id": client_id,
		}

		return self.upsert_transaction(
			tss_id=tss_id,
			tx_revision=tx_revision,
			tx_id=tx_id,
			body=body,
		)

	# TODO
	def cancel_transaction(
		self,
		tss_id: str,
		tx_id: str,
		tx_revision: int,
		client_id: str,
		schema: dict[str, Any] | None = None,
	) -> dict[str, Any]:
		"""
		Transaktion abbrechen
		State=CANCELLED
		Je nach Prozess wird ein leeres oder minimales schema verwendet
		"""
		body: dict[str, Any] = {
			"state": "CANCELLED",
			"client_id": client_id,
		}
		if schema is not None:
			body["schema"] = schema

		return self.upsert_transaction(
			tss_id=tss_id,
			tx_id=tx_id,
			tx_revision=tx_revision,
			body=body,
		)

	# ---------------------------------------------------------------------
	# DSFinV-K: Exports
	# ---------------------------------------------------------------------

	def create_dsfinvk_export(
		self,
		*,
		export_id: str | None = None,
		by_creation_date: dict[str, Any] | None = None,
		by_business_date: dict[str, Any] | None = None,
		client_id: str | None = None,
		archive_format: str | None = None,
		metadata: dict[str, Any] | None = None,
	) -> dict[str, Any]:
		"""Export-Job anlegen (DSFinV-K v1 /exports/{export_id})."""
		export_id = export_id or str(uuid.uuid4())
		payload: dict[str, Any] = {}

		if by_creation_date:
			payload.update(by_creation_date)
		elif by_business_date:
			payload.update(by_business_date)
		else:
			frappe.throw(_("Export requires either by_creation_date or by_business_date payload."))

		if client_id:
			payload["client_id"] = client_id
		if archive_format:
			payload["format"] = archive_format
		if metadata:
			payload["metadata"] = metadata

		data = self._dsfinvk_request_json(
			method="PUT",
			path=f"/exports/{export_id}",
			json=payload,
		)
		data.setdefault("_id", export_id)
		return data

	def list_dsfinvk_exports(self, **query_params) -> dict[str, Any]:
		"""Alle Exporte abrufen (Supports: limit, offset, order_by, order, states, client_id, business_date_start/end)."""
		return self._dsfinvk_request_json(
			method="GET",
			path="/exports",
			params=query_params,
		)

	def get_dsfinvk_export(self, export_id: str) -> dict[str, Any]:
		"""Status eines Export-Jobs abrufen."""
		return self._dsfinvk_request_json(
			method="GET",
			path=f"/exports/{export_id}",
		)

	def cancel_dsfinvk_export(self, export_id: str) -> dict[str, Any]:
		"""Export abbrechen / löschen."""
		return self._dsfinvk_request_json(
			method="DELETE",
			path=f"/exports/{export_id}",
		)

	def get_dsfinvk_export_href(self, export_id: str) -> dict[str, Any]:
		"""Download-URL eines Exports abrufen (href)."""
		return self._dsfinvk_request_json(
			method="GET",
			path=f"/exports/{export_id}/href",
		)

	def get_dsfinvk_export_metadata(self, export_id: str) -> dict[str, Any]:
		"""Metadata eines Exports abrufen."""
		return self._dsfinvk_request_json(
			method="GET",
			path=f"/exports/{export_id}/metadata",
		)

	def upsert_dsfinvk_export_metadata(
		self, export_id: str, metadata: dict[str, Any] | None
	) -> dict[str, Any]:
		"""Metadata eines Exports erstellen/aktualisieren."""
		return self._dsfinvk_request_json(
			method="PUT",
			path=f"/exports/{export_id}/metadata",
			json=metadata,
		)

	def download_dsfinvk_export(self, export_id: str) -> bytes:
		"""Fertigen Export (ZIP) herunterladen. Liefert Rohbytes zur Weiterverarbeitung."""
		resp = self._dsfinvk_request(
			method="GET",
			path=f"/exports/{export_id}/download",
		)
		return resp.content

	# ---------------------------------------------------------------------
	# DSFinV-K: Cash Registers
	# ---------------------------------------------------------------------

	def list_cash_registers(self) -> dict[str, Any]:
		"""Alle Cash Registers abrufen (DSFinV-K)."""
		return self._dsfinvk_request_json(
			method="GET",
			path="/cash_registers",
		)

	def get_cash_register(self, cash_register_id: str) -> dict[str, Any]:
		"""Einzelnes Cash Register abrufen."""
		return self._dsfinvk_request_json(
			method="GET",
			path=f"/cash_registers/{cash_register_id}",
		)

	def create_cash_register(
		self, payload: dict[str, Any], cash_register_id: str | None = None
	) -> dict[str, Any]:
		"""Cash Register anlegen/aktualisieren (PUT /cash_registers/{client_id})."""
		cash_register_id = cash_register_id or str(uuid.uuid4())
		data = self._dsfinvk_request_json(
			method="PUT",
			path=f"/cash_registers/{cash_register_id}",
			json=payload,
		)
		data.setdefault("_id", cash_register_id)
		return data

	def get_cash_register_metadata(self, cash_register_id: str) -> dict[str, Any]:
		"""Metadata eines Cash Registers abrufen."""
		return self._dsfinvk_request_json(
			method="GET",
			path=f"/cash_registers/{cash_register_id}/metadata",
		)

	def upsert_cash_register_metadata(
		self, cash_register_id: str, metadata: dict[str, Any] | None
	) -> dict[str, Any]:
		"""Metadata eines Cash Registers erstellen/aktualisieren."""
		return self._dsfinvk_request_json(
			method="PUT",
			path=f"/cash_registers/{cash_register_id}/metadata",
			json=metadata,
		)

	# ---------------------------------------------------------------------
	# DSFinV-K: Cash Point Closings
	# ---------------------------------------------------------------------

	def list_cash_point_closings(self) -> dict[str, Any]:
		"""Alle Cash Point Closings abrufen."""
		return self._dsfinvk_request_json(
			method="GET",
			path="/cash_point_closings",
		)

	def get_cash_point_closing(self, closing_id: str) -> dict[str, Any]:
		"""Einzelnen Cash Point Closing abrufen."""
		return self._dsfinvk_request_json(
			method="GET",
			path=f"/cash_point_closings/{closing_id}",
		)

	def get_cash_point_closing_details(self, closing_id: str) -> dict[str, Any]:
		"""Details eines Cash Point Closing abrufen."""
		return self._dsfinvk_request_json(
			method="GET",
			path=f"/cash_point_closings/{closing_id}/details",
		)

	def get_cash_point_closing_reports(self, closing_id: str) -> dict[str, Any]:
		"""Reports eines Cash Point Closing abrufen."""
		return self._dsfinvk_request_json(
			method="GET",
			path=f"/cash_point_closings/{closing_id}/reports",
		)

	def get_cash_point_closing_metadata(self, closing_id: str) -> dict[str, Any]:
		"""Metadata eines Cash Point Closing abrufen."""
		return self._dsfinvk_request_json(
			method="GET",
			path=f"/cash_point_closings/{closing_id}/metadata",
		)

	def upsert_cash_point_closing_metadata(
		self, closing_id: str, metadata: dict[str, Any] | None
	) -> dict[str, Any]:
		"""Metadata eines Cash Point Closing aktualisieren."""
		return self._dsfinvk_request_json(
			method="PUT",
			path=f"/cash_point_closings/{closing_id}/metadata",
			json=metadata,
		)

	def create_cash_point_closing(self, payload: dict[str, Any]) -> dict[str, Any]:
		"""Cash Point Closing anlegen"""

		# UUID für closing eines cash points generieren
		closing_id = str(uuid.uuid4())

		data = self._dsfinvk_request_json(
			method="PUT",
			path=f"/cash_point_closings/{closing_id}",
			json=payload,
		)
		data.setdefault("closing_id", closing_id)
		return data

	def delete_cash_point_closing(self, closing_id: str) -> dict[str, Any]:
		"""Cash Point Closing löschen."""
		return self._dsfinvk_request_json(
			method="DELETE",
			path=f"/cash_point_closings/{closing_id}",
		)
