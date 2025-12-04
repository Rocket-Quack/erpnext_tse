# Copyright (c) 2025, RocketQuackIT and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe import _

from erpnext_tse.erpnext_tse.tss_providers import get_tse_provider


class TSESecurityDevice(Document):

    # ---------- Basis / Validierung ----------

    def validate(self):
        """Nur erlauben, wenn TSE-Funktionalität aktiviert ist.
        Setzt außerdem Default-Status für neue Devices.
        """
        self.ensure_tse_enabled()
        if self.is_new():
            self.tss_status = "DRAFT"

    def ensure_tse_enabled(self):
        settings = frappe.get_single("TSE Settings")
        if not getattr(settings, "enabled", None):
            frappe.throw(
                _("TSE functionality is not enabled in TSE Settings. "
                  "Please enable it before creating a TSE Security Device.")
            )

    # ---------- Provider-Event-Historie ----------

    def log_provider_event(
        self,
        event_type: str,
        provider_action: str,
        resp: dict | None = None,
        status_before: str | None = None,
        status_after: str | None = None,
        message_summary: str | None = None,
    ):
        """Ein Event in die Child-Tabelle provider_events schreiben."""
        event = self.append("provider_events", {})
        event.event_time = frappe.utils.now_datetime()
        event.event_type = event_type
        event.provider_action = provider_action
        event.status_before = status_before
        event.status_after = status_after or self.tss_status
        event.message_summary = message_summary or ""

        if resp:
            event.http_status_code = resp.get("status_code")
            error = (resp or {}).get("error") or {}
            event.provider_error_code = error.get("code")
            event.provider_error_message = error.get("message")
            event.response_payload = frappe.as_json(resp, indent=2)
            event.request_id = resp.get("request_id")

        event.triggered_by = frappe.session.user

    # ---------- Aktionen: Create / Initialize / Deactivate ----------

    @frappe.whitelist()
    def create_tss_at_provider(self):
        """TSS bei Fiskaly anlegen. Erlaubt nur aus Status DRAFT."""
        self.ensure_tse_enabled()

        if self.tss_status != "DRAFT":
            frappe.throw(
                _("TSS can only be created at provider when status is 'DRAFT'. "
                  "Current status: {0}").format(self.tss_status)
            )

        settings = frappe.get_single("TSE Settings")
        provider = get_tse_provider(settings)

        old_status = self.tss_status

        try:
            resp = provider.create_tss(
                company=self.company,
                description=self.internal_name or self.company,
            )
        except Exception as e:
            self.tss_status = "ERROR"
            self.log_provider_event(
                event_type="CREATE_TSS_FAILED",
                provider_action="create_tss",
                resp={"error": {"message": str(e)}},
                status_before=old_status,
                status_after=self.tss_status,
                message_summary=_("Error while creating TSS at provider"),
            )
            raise

        # Erfolgreich angelegt → CREATED
        self.tss_id = resp.get("id")
        self.tss_status = "CREATED"

        self.log_provider_event(
            event_type="CREATE_TSS",
            provider_action="create_tss",
            resp=resp,
            status_before=old_status,
            status_after=self.tss_status,
            message_summary=_("TSS created at provider"),
        )
        
		# Dokument speichern
        self.save(ignore_permissions=True)
        frappe.db.commit()
        
    @frappe.whitelist()
    def deploy_tss_at_provider(self):
        """TSS deployen: Provider-State CREATED → UNINITIALIZED, interner Status ebenfalls."""
        self.ensure_tse_enabled()

        if not self.tss_id:
            frappe.throw(_("Cannot deploy TSS without tss_id."))

        if self.tss_status != "CREATED":
            frappe.throw(
            	_("TSS can only be deployed when status is 'CREATED'. "
				"Current status: {0}").format(self.tss_status)
			)

        settings = frappe.get_single("TSE Settings")
        provider = get_tse_provider(settings)

        old_status = self.tss_status

        try:
            resp = provider.deploy_tss(self.tss_id)
        except Exception as e:
            self.tss_status = "ERROR"
            self.log_provider_event(
				event_type="DEPLOY_TSS_FAILED",
				provider_action="deploy_tss",
				resp={"error": {"message": str(e)}},
				status_before=old_status,
				status_after=self.tss_status,
				message_summary=_("Error while deploying TSS at provider"),
			)
            raise

		# Erfolgreich → UNINITIALIZED
        self.tss_status = "UNINITIALIZED"

        self.log_provider_event(
			event_type="DEPLOY_TSS",
			provider_action="deploy_tss",
			resp=resp,
			status_before=old_status,
			status_after=self.tss_status,
			message_summary=_("TSS deployed at provider (state UNINITIALIZED)"),
		)

        # Dokument speichern
        self.save(ignore_permissions=True)
        frappe.db.commit()

        return {
			"tss_id": self.tss_id,
			"tss_status": self.tss_status,
		}
    
    @frappe.whitelist()
    def initialize_tss_at_provider(self):
        """TSS initialisieren. Nur wenn Status UNINITIALIZED und tss_id vorhanden."""
        self.ensure_tse_enabled()

        if not self.tss_id:
            frappe.throw(_("Cannot initialize TSS without tss_id."))

        if self.tss_status != "UNINITIALIZED":
            frappe.throw(
                _("TSS can only be initialized when status is 'UNINITIALIZED'. "
                  "Current status: {0}").format(self.tss_status)
            )

        settings = frappe.get_single("TSE Settings")
        provider = get_tse_provider(settings)

        old_status = self.tss_status

        try:
            resp = provider.initialize_tss(self.tss_id)
        except Exception as e:
            self.tss_status = "ERROR"
            self.log_provider_event(
                event_type="INITIALIZE_TSS_FAILED",
                provider_action="initialize_tss",
                resp={"error": {"message": str(e)}},
                status_before=old_status,
                status_after=self.tss_status,
                message_summary=_("Error while initializing TSS at provider"),
            )
            raise

        # Erfolgreich → INITIALIZED
        self.tss_status = "INITIALIZED"
        self.tss_serial_number = resp.get("serial_number")
        self.activated_at = resp.get("active_since")

        self.log_provider_event(
            event_type="INITIALIZE_TSS",
            provider_action="initialize_tss",
            resp=resp,
            status_before=old_status,
            status_after=self.tss_status,
            message_summary=_("TSS initialized at provider"),
        )
        
		# Dokument speichern
        self.save(ignore_permissions=True)
        frappe.db.commit()

    @frappe.whitelist()
    def deactivate_tss_at_provider(self):
        """TSS deaktivieren. Nur wenn aktuell INITIALIZED."""
        self.ensure_tse_enabled()

        if not self.tss_id:
            frappe.throw(_("Cannot deactivate TSS without tss_id."))

        if self.tss_status != "INITIALIZED":
            frappe.throw(
                _("TSS can only be deactivated when status is 'INITIALIZED'. "
                  "Current status: {0}").format(self.tss_status)
            )

        settings = frappe.get_single("TSE Settings")
        provider = get_tse_provider(settings)

        old_status = self.tss_status

        try:
            resp = provider.deactivate_tss(self.tss_id)
        except Exception as e:
            self.tss_status = "ERROR"
            self.log_provider_event(
                event_type="DEACTIVATE_TSS_FAILED",
                provider_action="deactivate_tss",
                resp={"error": {"message": str(e)}},
                status_before=old_status,
                status_after=self.tss_status,
                message_summary=_("Error while deactivating TSS at provider"),
            )
            raise

        self.tss_status = "DISABLED"
        self.deactivated_at = frappe.utils.now_datetime()

        self.log_provider_event(
            event_type="DEACTIVATE_TSS",
            provider_action="deactivate_tss",
            resp=resp,
            status_before=old_status,
            status_after=self.tss_status,
            message_summary=_("TSS deactivated at provider"),
        )

		# Dokument speichern
        self.save(ignore_permissions=True)
        frappe.db.commit()

    @frappe.whitelist()
    def deactivate_tss_at_provider(self):
        """TSS deaktivieren. Nur wenn aktuell INITIALIZED."""
        self.ensure_tse_enabled()

        if not self.tss_id:
            frappe.throw(_("Cannot deactivate TSS without tss_id."))

        if self.tss_status != "INITIALIZED":
            frappe.throw(
                _("TSS can only be deactivated when status is 'INITIALIZED'. "
                  "Current status: {0}").format(self.tss_status)
            )

        settings = frappe.get_single("TSE Settings")
        provider = get_tse_provider(settings)

        old_status = self.tss_status

        try:
            resp = provider.deactivate_tss(self.tss_id)
        except Exception as e:
            self.tss_status = "ERROR"
            self.log_provider_event(
                event_type="DEACTIVATE_TSS_FAILED",
                provider_action="deactivate_tss",
                resp={"error": {"message": str(e)}},
                status_before=old_status,
                status_after=self.tss_status,
                message_summary=_("Error while deactivating TSS at provider"),
            )
            raise

        self.tss_status = "DISABLED"
        self.deactivated_at = frappe.utils.now_datetime()

        self.log_provider_event(
            event_type="DEACTIVATE_TSS",
            provider_action="deactivate_tss",
            resp=resp,
            status_before=old_status,
            status_after=self.tss_status,
            message_summary=_("TSS deactivated at provider"),
        )

		# Dokument speichern
        self.save(ignore_permissions=True)
        frappe.db.commit()