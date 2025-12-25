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

	if getattr(tse_doc, "transaction_status", None) and tse_doc.transaction_status != "FINISHED":
		frappe.throw(
			_("The attached TSE Transaction is not yet finished (Transaction status: {0}).").format(
				tse_doc.transaction_status
			)
		)


def show_tse_signing_success_toast(doc, method=None):
	"""
	Zeigt einen Toast nach dem Submit der POS Invoice.
	- Grün: TSE Transaction FINISHED
	- Rot + Abbruch: TSE Transaction hat nicht Status FINISHED oder andere Fehler
	"""

	# Keine verknüpfte TSE Transaction
	if not getattr(doc, "tse_transaction", None):
		frappe.throw(
			_("POS Invoice wurde ohne verknüpfte TSE-Transaktion submitted."),
			title=_("TSE Fehler"),
		)

	# TSE Transaction laden
	tse_doc = frappe.get_doc("TSE Transaction", doc.tse_transaction)
	status = getattr(tse_doc, "transaction_status", None)

	# Erfolgsfall TSE Transaktion hat Status FINISHED
	if status == "FINISHED":
		frappe.msgprint(
			_("<b>TSE-Signierung erfolgreich abgeschlossen</b><br>TSE-Transaktion: {0}").format(tse_doc.name),
			alert=True,
			indicator="green",
		)
		return

	# Fehlerfall Doc wird nicht Submitted
	frappe.throw(
		_(
			"TSE-Signierung nicht erfolgreich.<br>" "<b>Status:</b> {0}<br>" "<b>TSE-Transaktion:</b> {1}"
		).format(status or _("Unbekannt"), tse_doc.name),
		title=_("TSE Signierung fehlgeschlagen"),
	)
