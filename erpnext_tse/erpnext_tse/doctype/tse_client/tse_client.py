# Copyright (c) 2025, RocketQuackIT and contributors
# For license information, please see LICENSE

import frappe
from frappe.model.document import Document
from frappe import _

from erpnext_tse.erpnext_tse.tss_providers import get_tse_provider


class TSEClient(Document):

    # ---------- Basis / Validierung ----------

    def validate(self):
        """Nur erlauben, wenn TSE-Funktionalität aktiviert ist.
        Setzt außerdem Default-Status für neue Devices.
        """
        self.ensure_tse_enabled()
        if self.is_new():
            self.status = "DRAFT"

        # Sicherstellen, dass nur INITIALIZED-TSE verknüpft werden
        if self.tse_security_device:
            tss = frappe.get_doc("TSE Security Device", self.tse_security_device)
            if tss.tss_status != "INITIALIZED":
                frappe.throw(
                    _(
                        "Only TSE Security Devices with status 'INITIALIZED' "
                        "can be linked to a TSE Client. Current status: {0}"
                    ).format(tss.tss_status)
                )

    def ensure_tse_enabled(self):
        settings = frappe.get_single("TSE Settings")
        if not getattr(settings, "enabled", None):
            frappe.throw(
                _(
                    "TSE functionality is not enabled in TSE Settings. "
                    "Please enable it before creating a TSE Client."
                )
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

    # ---------- Aktion: Client beim Provider anlegen ----------

    @frappe.whitelist()
    def create_client_at_provider(self):
        """
        TSE Client anlegen
        Nur erlaubt im Status 'DRAFT' && Benötigt eine verknüpfte TSE Security Device mit tss_id
        """
        self.ensure_tse_enabled()

        if not self.tse_security_device:
            frappe.throw(_("Please select a TSE Security Device first."))

        if self.client_status != "DRAFT":
            frappe.throw(
                _(
                    "Client can only be created at provider when status is 'DRAFT'. "
                    "Current status: {0}"
                ).format(self.status)
            )

        if self.client_id:
            frappe.throw(
                _("This TSE Client already has a client_id ({0}).").format(
                    self.client_id
                )
            )

        # Zugehörige TSS laden
        tss = frappe.get_doc("TSE Security Device", self.tse_security_device)

        if not tss.tss_id:
            frappe.throw(_("Selected TSE Security Device has no tss_id yet."))

        settings = frappe.get_single("TSE Settings")
        provider = get_tse_provider(settings)

        old_status = self.client_status

        try:
            resp = provider.create_client(
                tss_id=tss.tss_id,
                metadata={
                    "company": self.company,
                    "pos_profile": self.pos_profile,
                    "tse_client_name": self.client_name,
                    "tse_client_docname": self.name,
                },
            )

        except Exception as e:
            self.status = "ERROR"
            self.log_provider_event(
                event_type="CREATE_CLIENT_FAILED",
                provider_action="create_client",
                resp={"error": {"message": str(e)}},
                status_before=old_status,
                status_after=self.client_status,
                message_summary=_(
                    "Error while creating client at provider for TSE Client {0}"
                ).format(self.name),
            )

            self.save(ignore_permissions=True)
            frappe.db.commit()
            raise

        # Erfolgreich angelegt → REGISTERED
        self.client_id = resp.get("_id")
        self.client_status = resp.get("state")
        self.serial_number = resp.get("serial_number")

        self.log_provider_event(
            event_type="CREATE_CLIENT",
            provider_action="create_client",
            resp=resp,
            status_before=old_status,
            status_after=self.client_status,
            message_summary=_("Client {0} created at provider for TSS {1}").format(
                self.name, tss.name
            ),
        )

        # Dokument speichern
        self.save(ignore_permissions=True)
        frappe.db.commit()

    @frappe.whitelist()
    def deregister_client_at_provider(self):
        """
        TSE Client wird auf den Status "DEREGISTERED" gesetzt somit für die Verwendung der TSS blockiert
        Nur erlaubt im Status 'REGISTERED' && Benötigt eine verknüpfte TSE Security Device mit tss_id sowie eine regestrierte client_id
        """
        self.ensure_tse_enabled()

        if self.client_status != "REGISTERED":
            frappe.throw(
                _(
                    "Client can only be deregistered at provider when status is 'REGISTERED'. "
                    "Current status: {0}"
                ).format(self.client_status)
            )

        # Zugehörige TSS laden
        tss = frappe.get_doc("TSE Security Device", self.tse_security_device)

        settings = frappe.get_single("TSE Settings")
        provider = get_tse_provider(settings)

        old_status = self.client_status

        try:
            resp = provider.deregister_client(
                tss_id=tss.tss_id, client_id=self.client_id
            )

        except Exception as e:
            self.status = "ERROR"
            self.log_provider_event(
                event_type="DEREGISTER_CLIENT_FAILED",
                provider_action="deregister_client",
                resp={"error": {"message": str(e)}},
                status_before=old_status,
                status_after=self.client_status,
                message_summary=_(
                    "Error while deregistering client at provider for TSE Client {0}"
                ).format(self.name),
            )

            self.save(ignore_permissions=True)
            frappe.db.commit()
            raise

        # Erfolgreich Client deregestriert → DEREGISTER
        self.client_status = resp.get("state")

        self.log_provider_event(
            event_type="DEREGISTER_CLIENT",
            provider_action="deregister_client",
            resp=resp,
            status_before=old_status,
            status_after=self.client_status,
            message_summary=_("Client {0} deregistered at provider for TSS {1}").format(
                self.name, tss.name
            ),
        )

        # Dokument speichern
        self.save(ignore_permissions=True)
        frappe.db.commit()

    @frappe.whitelist()
    def register_client_at_provider(self):
        """
        TSE Client wird auf den Status "REGISTERED" gesetzt somit für die Verwendung der TSS wieder verfügbar
        Nur erlaubt im Status 'DEREGISTERED' && Benötigt eine verknüpfte TSE Security Device mit tss_id sowie eine regestrierte client_id
        """
        self.ensure_tse_enabled()

        if self.client_status != "DEREGISTERED":
            frappe.throw(
                _(
                    "Client can only be registered at provider when status is 'DEREGISTERED'. "
                    "Current status: {0}"
                ).format(self.client_status)
            )

        # Zugehörige TSS laden
        tss = frappe.get_doc("TSE Security Device", self.tse_security_device)

        settings = frappe.get_single("TSE Settings")
        provider = get_tse_provider(settings)

        old_status = self.client_status

        try:
            resp = provider.register_client(tss_id=tss.tss_id, client_id=self.client_id)

        except Exception as e:
            self.status = "ERROR"
            self.log_provider_event(
                event_type="REGISTER_CLIENT_FAILED",
                provider_action="register_client",
                resp={"error": {"message": str(e)}},
                status_before=old_status,
                status_after=self.client_status,
                message_summary=_(
                    "Error while registering client at provider for TSE Client {0}"
                ).format(self.name),
            )

            self.save(ignore_permissions=True)
            frappe.db.commit()
            raise

        # Erfolgreich Client regestriert → REGISTER
        self.client_status = resp.get("state")

        self.log_provider_event(
            event_type="REGISTER_CLIENT",
            provider_action="register_client",
            resp=resp,
            status_before=old_status,
            status_after=self.client_status,
            message_summary=_("Client {0} registered at provider for TSS {1}").format(
                self.name, tss.name
            ),
        )

        # Dokument speichern
        self.save(ignore_permissions=True)
        frappe.db.commit()
