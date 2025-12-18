# Copyright (c) 2025, RocketQuackIT and contributors
# For license information, please see LICENSE

from __future__ import annotations

from typing import Any

import frappe
from frappe.model.document import Document

from erpnext_tse.erpnext_tse.tss_providers.base import BaseTSEProvider
from erpnext_tse.erpnext_tse.tss_providers.fiskaly import FiskalyProvider


class TSESettings(Document):
    """Global settings for TSE integration."""

    def get_provider_name(self) -> str:
        """Return the normalized provider name from settings."""
        name = (self.tse_provider or "").strip().lower()
        if not name:
            frappe.throw(
                "No TSE provider configured. Please select a TSE Provider in TSE Settings."
            )
        return name

    def get_provider(self) -> BaseTSEProvider:
        """Instantiate the configured provider."""
        name = self.get_provider_name()

        if name in ("fiskaly", "fiskaly (cloud)", "fiskaly_sign_de"):
            return FiskalyProvider(self)

        # Placeholder for future providers
        frappe.throw(f"Unsupported TSE provider: {self.tse_provider or name}")

    def validate(self):
        """Basic validation for TSE Settings."""
        if self.enabled and not self.tse_provider:
            frappe.throw(
                "You must choose a TSE Provider before enabling the TSE integration."
            )


# -------------------------------------------------------------------------
# Whitelisted API for the client script (Test Auth button)
# -------------------------------------------------------------------------


@frappe.whitelist()
def test_tse_auth() -> dict[str, Any]:
    settings = frappe.get_single("TSE Settings")

    # TSE muss aktiviert sein
    if not getattr(settings, "enabled", None):
        frappe.throw(
            "TSE integration is disabled. Please enable it in TSE Settings before testing auth."
        )

    provider = settings.get_provider()

    try:
        result = provider.test_auth()
        return {
            "success": True,
            "status": result.get("status"),
            "environment": result.get("environment"),
            "organization_id": result.get("organization_id"),
            "access_token_expires_at": result.get("access_token_expires_at"),
        }
    except frappe.ValidationError as exc:
        # Auth-Fehler etc. -> kontrolliert zurückgeben
        return {
            "success": False,
            "error_type": exc.__class__.__name__,
            "error_message": str(exc),
            "last_auth_status": getattr(settings, "last_auth_status", None),
            "last_auth_message": getattr(settings, "last_auth_message", None),
        }
    except Exception as exc:
        # Fallback
        return {
            "success": False,
            "error_type": exc.__class__.__name__,
            "error_message": str(exc),
            "last_auth_status": getattr(settings, "last_auth_status", None),
            "last_auth_message": getattr(settings, "last_auth_message", None),
        }
