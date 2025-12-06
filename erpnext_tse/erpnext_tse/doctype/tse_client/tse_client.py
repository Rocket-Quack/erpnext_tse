# Copyright (c) 2025, RocketQuackIT and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe import _

class TSEClient(Document):

    # ---------- Basis / Validierung ----------

    def validate(self):
        """Nur erlauben, wenn TSE-Funktionalität aktiviert ist.
        Setzt außerdem Default-Status für neue Devices.
        """
        self.ensure_tse_enabled()
        if self.is_new():
            self.tss_status = "DRAFT"
            
		# Sicherstellen, dass nur INITIALIZED-TSE verknüpft werden
        if self.tse_security_device:
            tss = frappe.get_doc("TSE Security Device", self.tse_security_device)
            if tss.tss_status != "INITIALIZED":
                frappe.throw(
                    _("Only TSE Security Devices with status 'INITIALIZED' "
                      "can be linked to a TSE Client. Current status: {0}")
                    .format(tss.tss_status)
                )

    def ensure_tse_enabled(self):
        settings = frappe.get_single("TSE Settings")
        if not getattr(settings, "enabled", None):
            frappe.throw(
                _("TSE functionality is not enabled in TSE Settings. "
                  "Please enable it before creating a TSE Security Device.")
            )
