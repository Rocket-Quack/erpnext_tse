# Copyright (c) 2025, RocketQuackIT and contributors
# For license information, please see LICENSE

import frappe
from frappe import _

def ensure_tse_transaction_present_and_finished(doc, method):

    # Sicherstellen, dass eine TSE Transaction vorhanden ist und den Status Finished hat
    # Ohne sollte um auch rechtlich sicher zu sein keine Buchung erfolgen
    if not doc.tse_transaction:
        frappe.throw(
            _("A TSE transaction is mandatory, bevor POS Invoice can be submitted."),
            frappe.MandatoryError,
        )

    tse_doc = frappe.get_doc("TSE Transaction", doc.tse_transaction)

    if getattr(tse_doc, "status", None) and tse_doc.status != "FINISHED":
        frappe.throw(
            _("The attached TSE Transaction is not yet finished (Status: {0}).")
            .format(tse_doc.status)
        )