# Copyright (c) 2025, RocketQuackIT and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

class TSETransaction(Document):
    def before_cancel(self):
        frappe.throw(_("TSE Transactions cannot be cancelled."))

    def before_delete(self):
        frappe.throw(_("TSE Transactions cannot be deleted."))