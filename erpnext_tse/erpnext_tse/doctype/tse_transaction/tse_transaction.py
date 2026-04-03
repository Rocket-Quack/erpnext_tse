# Copyright (c) 2025, RocketQuackIT and contributors
# For license information, please see LICENSE

from datetime import datetime
from typing import Any

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint

from erpnext_tse.erpnext_tse.tss_providers import get_tse_provider

TRANSACTION_STATE_MAP = {
	"ACTIVE": "ACTIVE",
	"FINISHED": "FINISHED",
	"CANCELLED": "CANCELLED",
	"CANCELED": "CANCELLED",
}
FINAL_TRANSACTION_STATUSES = ("FINISHED", "CANCELLED")


class TSETransaction(Document):
	def before_cancel(self):
		frappe.throw(_("TSE Transactions cannot be cancelled."))

	def before_delete(self):
		frappe.throw(_("TSE Transactions cannot be deleted."))

	# ---------- Basis / Validierung ----------

	def validate(self):
		"""
		Nur erlauben, wenn TSE-Funktionalität aktiviert ist
		"""
		self.ensure_tse_enabled()

		# Sicherstellen, dass nur INITIALIZED-TSE verknüpft werden
		if self.tse_security_device:
			tss = frappe.get_doc("TSE Security Device", self.tse_security_device)
			if tss.tss_status != "INITIALIZED":
				frappe.throw(
					_(
						"Only TSE Security Devices with status 'INITIALIZED' "
						"can be used for Transaction. Current status: {0}"
					).format(tss.tss_status)
				)

		# Sicherstellen, dass verknüpfter Client auf REGISTERED steht
		if self.tse_client:
			client = frappe.get_doc("TSE Client", self.tse_client)
			if client.client_status != "REGISTERED":
				frappe.throw(
					_(
						"Only Client with status 'REGISTERED' "
						"can be used for Transaction. Current status: {0}"
					).format(client.client_status)
				)

	def ensure_tse_enabled(self):
		settings = frappe.get_single("TSE Settings")
		if not cint(getattr(settings, "enabled", None)):
			frappe.throw(
				_(
					"TSE functionality is not enabled in TSE Settings. "
					"Please enable it before creating a TSE Security Device."
				)
			)


def _normalize_transaction_status(state: str | None) -> str | None:
	if not state:
		return None
	return TRANSACTION_STATE_MAP.get(str(state).strip().upper(), "ERROR")


def _to_datetime(value: Any) -> datetime | None:
	if not value:
		return None
	if isinstance(value, datetime):
		return value
	if isinstance(value, int | float):
		return datetime.fromtimestamp(value)
	try:
		return frappe.utils.get_datetime(value)
	except Exception:
		return None


def _to_int(value: Any, default: int | None = None) -> int | None:
	if value is None:
		return default
	try:
		return int(value)
	except Exception:
		return default


def _get_transaction_provider_context(tse_tx: Document):
	settings = frappe.get_single("TSE Settings")
	provider = get_tse_provider(settings)

	tse_device = frappe.get_doc("TSE Security Device", tse_tx.tse_security_device)
	tse_client = frappe.get_doc("TSE Client", tse_tx.tse_client)

	tss_id = getattr(tse_device, "tss_id", None)
	client_id = getattr(tse_client, "client_id", None)
	if not tss_id or not client_id:
		frappe.throw(_("TSE Transaction is missing provider identifiers (tss_id / client_id)."))

	return provider, tss_id, client_id


def _persist_transaction_state(tse_tx: Document, submit_if_final: bool = False):
	if not getattr(tse_tx, "name", None) or not frappe.db.exists("TSE Transaction", tse_tx.name):
		return

	frappe.db.set_value(
		"TSE Transaction",
		tse_tx.name,
		{
			"transaction_id": tse_tx.transaction_id,
			"transaction_status": tse_tx.transaction_status,
			"transaction_revision": tse_tx.transaction_revision,
			"transaction_number": tse_tx.transaction_number,
			"signature_counter": tse_tx.signature_counter,
			"start_time": tse_tx.start_time,
			"end_time": tse_tx.end_time,
			"qr_code_data": tse_tx.qr_code_data,
			"full_schema_req": tse_tx.full_schema_req,
			"full_schema_res": tse_tx.full_schema_res,
		},
		update_modified=False,
	)

	if submit_if_final and tse_tx.docstatus == 0 and tse_tx.transaction_status in FINAL_TRANSACTION_STATUSES:
		frappe.db.set_value("TSE Transaction", tse_tx.name, "docstatus", 1, update_modified=False)
		tse_tx.docstatus = 1


def _apply_transaction_response(
	tse_tx: Document,
	response: dict[str, Any],
	*,
	request_payload: dict[str, Any] | None = None,
	submit_if_final: bool = False,
):
	state = _normalize_transaction_status(response.get("state") or response.get("status"))
	if state:
		tse_tx.transaction_status = state

	tx_id = response.get("_id") or response.get("transaction_id") or response.get("id")
	if tx_id:
		tse_tx.transaction_id = tx_id

	revision = response.get("revision") or response.get("tx_revision")
	if revision is not None:
		tse_tx.transaction_revision = revision

	transaction_number = response.get("number") or response.get("transaction_number")
	if transaction_number is not None:
		tse_tx.transaction_number = transaction_number

	signature = response.get("signature") or {}
	if isinstance(signature, dict) and signature.get("counter") is not None:
		tse_tx.signature_counter = signature.get("counter")

	start_time = _to_datetime(response.get("time_start") or response.get("timeStart"))
	if start_time:
		tse_tx.start_time = start_time

	end_time = _to_datetime(response.get("time_end") or response.get("timeEnd"))
	if end_time:
		tse_tx.end_time = end_time

	qr_code_data = response.get("qr_code_data")
	if qr_code_data:
		tse_tx.qr_code_data = qr_code_data

	if request_payload is not None:
		tse_tx.full_schema_req = frappe.as_json(request_payload, indent=2)
	tse_tx.full_schema_res = frappe.as_json(response, indent=2)

	_persist_transaction_state(tse_tx, submit_if_final=submit_if_final)
	return tse_tx


def _get_linked_pos_invoice_docstatus(pos_invoice_name: str | None) -> int | None:
	if not pos_invoice_name or not frappe.db.exists("POS Invoice", pos_invoice_name):
		return None
	return cint(frappe.db.get_value("POS Invoice", pos_invoice_name, "docstatus"))


def _unlink_pos_invoice_tse_transaction(pos_invoice_name: str | None, tse_tx_name: str | None):
	if not pos_invoice_name or not tse_tx_name:
		return
	if not frappe.db.exists("POS Invoice", pos_invoice_name):
		return
	if cint(frappe.db.get_value("POS Invoice", pos_invoice_name, "docstatus")) != 0:
		return
	current_link = frappe.db.get_value("POS Invoice", pos_invoice_name, "tse_transaction")
	if current_link != tse_tx_name:
		return
	frappe.db.set_value("POS Invoice", pos_invoice_name, "tse_transaction", None, update_modified=False)


def _sync_existing_transaction_from_remote(
	tse_tx: Document,
	response: dict[str, Any],
	*,
	request_payload: dict[str, Any] | None = None,
	clear_pos_invoice_link_on_cancel: bool = False,
):
	_apply_transaction_response(
		tse_tx,
		response,
		request_payload=request_payload,
		submit_if_final=True,
	)
	if clear_pos_invoice_link_on_cancel and tse_tx.transaction_status == "CANCELLED":
		_unlink_pos_invoice_tse_transaction(tse_tx.pos_invoice, tse_tx.name)
	return tse_tx


def _resolve_started_transaction_failure(
	*,
	provider,
	pos_invoice,
	tse_tx: Document | None,
	tss_id: str,
	client_id: str,
	schema: dict[str, Any],
):
	if not tse_tx or not getattr(tse_tx, "transaction_id", None):
		return

	stored_tse_tx = None
	if getattr(tse_tx, "name", None) and frappe.db.exists("TSE Transaction", tse_tx.name):
		stored_tse_tx = frappe.get_doc("TSE Transaction", tse_tx.name)

	try:
		remote = provider.get_transaction(tss_id, tse_tx.transaction_id)
	except Exception:
		frappe.log_error(
			frappe.get_traceback(),
			_("Could not fetch Fiskaly transaction status after TSE submit failure."),
		)
		return

	remote_status = _normalize_transaction_status(remote.get("state") or remote.get("status"))
	if remote_status == "FINISHED" and stored_tse_tx:
		_sync_existing_transaction_from_remote(
			stored_tse_tx,
			remote,
			request_payload={
				"schema": schema,
				"client_id": client_id,
				"state": "FINISHED",
			},
		)
		return

	if remote_status != "ACTIVE":
		if not stored_tse_tx:
			if remote_status == "CANCELLED":
				pos_invoice.tse_transaction = None
			return
		_sync_existing_transaction_from_remote(
			stored_tse_tx,
			remote,
			clear_pos_invoice_link_on_cancel=(remote_status == "CANCELLED"),
		)
		if remote_status == "CANCELLED":
			pos_invoice.tse_transaction = None
		return

	try:
		next_revision = (_to_int(remote.get("revision") or remote.get("tx_revision"), 1) or 1) + 1
		cancel_response = provider.cancel_transaction(
			tss_id=tss_id,
			tx_id=tse_tx.transaction_id,
			tx_revision=next_revision,
			client_id=client_id,
		)
		if stored_tse_tx:
			_sync_existing_transaction_from_remote(
				stored_tse_tx,
				cancel_response,
				request_payload={
					"state": "CANCELLED",
					"client_id": client_id,
				},
				clear_pos_invoice_link_on_cancel=True,
			)
		pos_invoice.tse_transaction = None
	except Exception:
		frappe.log_error(
			frappe.get_traceback(),
			_("Could not cancel ACTIVE Fiskaly transaction after TSE submit failure."),
		)


# ---------------------------------------------------------------------------
# Hilfsfunktionen zur Schema Erstellung
# ---------------------------------------------------------------------------


def _build_receipt_schema_from_pos_invoice(pos_inv) -> dict[str, Any]:
	"""
	Schema-Body aus einer POS Invoice erzeugen
	Hierbei werden die VAT Rates sowie Payment Type über Hilfsfunktionen ermittelt
	"""

	receipt = {
		"receipt_type": "RECEIPT",
		"amounts_per_vat_rate": _build_amounts_per_vat_rate(pos_inv),
		"amounts_per_payment_type": _build_amounts_per_payment_type(pos_inv),
	}

	return {
		"standard_v1": {
			"receipt": receipt,
		}
	}


# TODO Payment Amount darf nur aus Sicht der Kasse enthaltene Menge erhalten also Ohne Wechselgeld
def _build_amounts_per_payment_type(pos_inv) -> list[dict[str, str]]:
	"""
	Es erfolgt das Mapping der Payment Types hierbei gibt es Cash und Non_Cash
	Diese werden aus einer POS Invoice extrahiert und je nach Klasse welche über die DocTypes angelegt wurden Zusammen addiert

	Wechselgeld muss abgezogen werden darf nicht in die Summe der Payment Types einfließen

	"""
	payments_rows = pos_inv.get("payments") or []
	if not payments_rows:
		frappe.throw(_("POS Invoice has no payments rows. Cannot build receipt schema for TSE Transaction"))

	try:
		change_remaining = float(getattr(pos_inv, "change_amount", 0) or 0)
	except Exception:
		frappe.throw(
			_("Invalid change_amount on POS Invoice: {0}").format(getattr(pos_inv, "change_amount", None))
		)

	sums: dict[str, float] = {}

	for row in payments_rows:
		mode_of_payment = getattr(row, "mode_of_payment", None) or (
			row.get("mode_of_payment") if isinstance(row, dict) else None
		)
		amount = getattr(row, "amount", None) if not isinstance(row, dict) else row.get("amount")

		if not mode_of_payment:
			frappe.throw(_("POS Invoice payment row is missing 'mode_of_payment'."))

		try:
			amount_f = float(amount or 0)
		except Exception:
			frappe.throw(
				_("Invalid payment amount for Mode of Payment {0}: {1}").format(mode_of_payment, amount)
			)

		if amount_f == 0:
			continue

		final_amount = amount_f

		payment_code = frappe.db.get_value(
			"TSE Payment Type",
			{"mode_of_payment": mode_of_payment},
			"payment_code",
		)
		if not payment_code:
			frappe.throw(
				_("No TSE Payment Type mapping found for Mode of Payment '{0}'").format(mode_of_payment)
			)

		# Wechselgeld abziehen
		if change_remaining > 0:
			if final_amount >= change_remaining:
				final_amount -= change_remaining
				change_remaining = 0.0
			else:
				change_remaining -= final_amount
				final_amount = 0.0

		sums[payment_code] = sums.get(payment_code, 0.0) + final_amount

	if not sums:
		frappe.throw(_("POS Invoice has no non-zero payments. Cannot build receipt schema"))

	return [{"payment_type": k, "amount": f"{v:.2f}"} for k, v in sums.items()]


def _build_amounts_per_vat_rate(pos_inv) -> list[dict[str, str]]:
	"""
	Es werden die Summen für die Steuersätze zusammen gerechnet
	Hierbei erfolt auch ein Mapping über den DocType von TSE_VAT_RATE

	Vorgehen:
	1) Aus der POS Invoice werden die Items gelesen (net amounts pro Item).
	2) Aus der POS Invoice werden die Steuerzeilen (taxes) gelesen.
	3) Pro Steuerzeile wird der Steuer-Account (account_head) über den DocType "TSE VAT Rate"
	   auf einen fiskaly VAT Code gemappt (z. B. NORMAL / REDUCED_1).
	4) Über item_wise_tax_detail wird pro Item der Steuerbetrag und der Steuersatz ermittelt.
	   Für diesen Schritt berücksichtigen wir aktuell nur 19% und 7%.
	5) Für jedes Item wird der Bruttobetrag berechnet: net_amount + tax_amount
	   und danach je VAT Code aufsummiert.

	Hinweis:
	- 0% wird hier bewusst noch nicht behandelt. #TODO
	- Falls ein Mapping fehlt, wird "fail-fast" abgebrochen, damit keine falsche Signatur entsteht.
	"""

	invoice_items = pos_inv.get("items") or []
	if not invoice_items:
		frappe.throw(_("POS Invoice has no items."))

	taxes = pos_inv.get("taxes") or []
	if not taxes:
		frappe.throw(_("POS Invoice has no taxes rows."))

	# item_code -> net amount (base bevorzugt, fallback net_amount)
	net_amount_by_item_code: dict[str, float] = {}
	for item_row in invoice_items:
		item_code = getattr(item_row, "item_code", None) or (
			item_row.get("item_code") if isinstance(item_row, dict) else None
		)
		if not item_code:
			continue

		base_net_amount = (
			getattr(item_row, "base_net_amount", None)
			if not isinstance(item_row, dict)
			else item_row.get("base_net_amount")
		)
		if base_net_amount is None:
			base_net_amount = (
				getattr(item_row, "net_amount", None)
				if not isinstance(item_row, dict)
				else item_row.get("net_amount")
			)

		net_amount_by_item_code[item_code] = float(base_net_amount or 0)

	if not net_amount_by_item_code:
		frappe.throw(_("POS Invoice items are missing item_code values. Cannot build VAT breakdown."))

	# vat_code -> gross amount sum
	gross_amount_by_vat_code: dict[str, float] = {}

	# Cache: Tax Account -> VAT Code (spart DB Calls)
	vat_code_by_tax_account: dict[str, str] = {}

	def parse_item_wise_detail(detail_value) -> tuple[float, float]:
		"""
		item_wise_tax_detail ist [rate, tax_amount]
		Ergebnis: (rate_percent, tax_amount)
		"""
		if isinstance(detail_value, list | tuple) and len(detail_value) >= 2:
			return float(detail_value[0] or 0), float(detail_value[1] or 0)

		if isinstance(detail_value, dict):
			rate_percent = float(detail_value.get("tax_rate") or detail_value.get("rate") or 0)
			tax_amount = float(detail_value.get("tax_amount") or detail_value.get("amount") or 0)
			return rate_percent, tax_amount

		return 0.0, 0.0

	for tax_row in taxes:
		tax_account = getattr(tax_row, "account_head", None) or (
			tax_row.get("account_head") if isinstance(tax_row, dict) else None
		)
		item_wise_tax_detail_json = (
			getattr(tax_row, "item_wise_tax_detail", None)
			if not isinstance(tax_row, dict)
			else tax_row.get("item_wise_tax_detail")
		)

		# Steuerzeilen ohne Account oder ohne Details können nicht verwendet werden (z. B. leere/sonstige Charges)
		if not tax_account or not item_wise_tax_detail_json:
			continue

		# Tax Account -> VAT Code (über Mapping DocType), mit Cache
		vat_code = vat_code_by_tax_account.get(tax_account)
		if not vat_code:
			vat_code = frappe.db.get_value("TSE VAT Rate", {"account": tax_account}, "vat_rate_code")
			if not vat_code:
				frappe.throw(_("No TSE VAT Rate mapping found for Tax Account '{0}'.").format(tax_account))
			vat_code_by_tax_account[tax_account] = vat_code

		# JSON aus item_wise_tax_detail parsen
		item_wise_details = frappe.parse_json(item_wise_tax_detail_json)
		if not isinstance(item_wise_details, dict):
			continue

		# Pro Item auswerten
		for item_code, detail_value in item_wise_details.items():
			# Wenn Keys nicht matchen (z. B. Item Name statt Item Code), wird dieses Item übersprungen
			if item_code not in net_amount_by_item_code:
				continue

			rate_percent, tax_amount = parse_item_wise_detail(detail_value)

			# Aktuell nur 19% / 7%
			if rate_percent not in (19.0, 7.0):
				continue

			# Bruttoanteil je Item: net + tax
			item_net_amount = net_amount_by_item_code[item_code]
			item_gross_amount = item_net_amount + float(tax_amount or 0)

			gross_amount_by_vat_code[vat_code] = (
				gross_amount_by_vat_code.get(vat_code, 0.0) + item_gross_amount
			)

	if not gross_amount_by_vat_code:
		frappe.throw(_("Could not derive VAT amounts (no 19%/7% data found in item_wise_tax_detail)."))

	return [
		{"vat_rate": vat_code, "amount": f"{gross_amount:.2f}"}
		for vat_code, gross_amount in gross_amount_by_vat_code.items()
		if gross_amount
	]


# ---------------------------------------------------------------------------
# Aus POS Invoice wird eine TSE Transaction generiert
# ---------------------------------------------------------------------------


def create_tse_transaction_for_pos_invoice(doc, method: str | None = None):
	"""
	DocEvent-Hook für POS Invoice (before_submit)

	Erwartet, dass die POS Invoice ein Feld `tse_client` (Link auf "TSE Client")
	hat. Von dort wird der verknüpfte TSE Client sowie dessen Security Device geladen
	"""

	# 1. POS Invoice aus dict laden
	if isinstance(doc, dict):
		doc = frappe.get_doc(doc)

	# 2. Check ob wirklich POS Invoice
	if doc.doctype != "POS Invoice":
		return

	if not cint(frappe.db.get_single_value("TSE Settings", "enabled")):
		return

	# 3. POS Profile holen
	if not getattr(doc, "pos_profile", None):
		frappe.throw(_("POS Invoice is missing a POS Profile."))

	pos_profile = frappe.get_doc("POS Profile", doc.pos_profile)

	# 4. TSE Client aus POS Profile
	if not getattr(pos_profile, "tse_client", None):
		frappe.throw(_("POS Profile {0} has no TSE Client set.").format(pos_profile.name))

	tse_client = frappe.get_doc("TSE Client", pos_profile.tse_client)

	# 5. TSE Security Device aus TSE Client
	if not getattr(tse_client, "tse_security_device", None):
		frappe.throw(_("TSE Client {0} is missing a linked TSE Security Device.").format(tse_client.name))

	tse_device = frappe.get_doc("TSE Security Device", tse_client.tse_security_device)

	# 6. Setzen der benötigten IDS in welcher TSS und mit welchem CLient die SPeicherung erfolgt
	tss_id = tse_device.tss_id
	client_id = tse_client.client_id

	if not tss_id or not client_id:
		frappe.throw(_("TSE Device or TSE Client is missing provider IDs (tss_id / client_id)."))

	# 7. Falls bereits eine TSE Transaction verknüpft ist, Idempotenz sicherstellen
	existing_tx_name = getattr(doc, "tse_transaction", None)
	if existing_tx_name:
		existing_tx = frappe.get_doc("TSE Transaction", existing_tx_name)

		if getattr(existing_tx, "pos_invoice", None) and existing_tx.pos_invoice != doc.name:
			frappe.throw(
				_(
					"POS Invoice {0} is linked to TSE Transaction {1}, "
					"which belongs to another POS Invoice ({2})."
				).format(doc.name, existing_tx_name, existing_tx.pos_invoice)
			)

		status = getattr(existing_tx, "transaction_status", None)
		if status == "FINISHED":
			# Bereits erfolgreich signiert -> keine neue Transaktion erzeugen
			return

		frappe.throw(
			_(
				"POS Invoice already has TSE Transaction {0} with status {1}. "
				"Please resolve it before submitting again."
			).format(existing_tx_name, status or _("Unknown"))
		)

	# 7. Transaction-Typ bestimmen SALE / REFUND aus dem POS Invoice DocType
	tx_type = "SALE"
	if getattr(doc, "is_return", 0):
		tx_type = "REFUND"

	# 8. Provider holen
	settings = frappe.get_single("TSE Settings")
	provider = get_tse_provider(settings)

	# 9. Schema aus der POS Invoice bauen
	schema = _build_receipt_schema_from_pos_invoice(doc)

	# 10. Revision wird auf eins gesetzt ist somit die erste
	#    Beim Anlegen Fachlich gesehen immer die erste
	tx_revision = 1

	tse_tx = None

	try:
		# 11. Transaktion starten (start_transaction) und Transaction Details zwischen Speichern
		response = provider.start_transaction(
			tss_id=tss_id,
			client_id=client_id,
			tx_revision=1,
		)

		# 12. Anlegen des Docs mit Zwischenstand
		tse_tx = frappe.get_doc(
			{
				"doctype": "TSE Transaction",
				"tse_security_device": tse_device.name,
				"tse_client": tse_client.name,
				"company": doc.company,
				"pos_invoice": doc.name,
				"transaction_type": tx_type,
				"transaction_id": response.get("_id"),
				"transaction_revision": tx_revision,  # Sollte beim anlegen zuerst 1 sein
				"transaction_status": response.get("state"),  # Sollte ACTIVE sein
				"start_time": datetime.fromtimestamp(response.get("time_start")),
			}
		)

		# 13. Zwischenstand speichern falls etwas schief läuft
		tse_tx.flags.ignore_permissions = True
		tse_tx.insert()
		tse_tx.flags.ignore_permissions = True
		tse_tx.save()

		# 14. TSE Transaktion wird in der POS Invoice verlinkt
		doc.db_set("tse_transaction", tse_tx.name)

		# 15. Transaktion update (update_transaction)
		#    Transaktion kann beednet werden im Restaurant Umfeld müsste noch die Update Funktion kommen
		# TODO

		# 16. Transaktion finish (finish_transaction)
		response = provider.finish_transaction(
			tss_id=tss_id,
			client_id=client_id,
			tx_id=tse_tx.transaction_id,
			tx_revision=tx_revision + 1,  # TODO Revisions Nummer noch korrekt erfassen und hochzählen
			schema=schema,
		)

		# 17. Vorhandene TSE Transaction wieder laden
		tse_tx = frappe.get_doc("TSE Transaction", tse_tx.name)

		# 18. TSE Transactions Daten in Doc nachtragen und speichern
		tse_tx.transaction_status = response.get("state")
		tse_tx.end_time = datetime.fromtimestamp(response.get("time_end"))
		tse_tx.qr_code_data = response.get("qr_code_data")
		tse_tx.transaction_revision = response.get("revision")
		tse_tx.signature_counter = response.get("signature", {}).get("counter")
		tse_tx.transaction_number = response.get("number")
		tse_tx.full_schema_req = frappe.as_json(
			{
				"schema": schema,
				"client_id": client_id,
				"state": "FINISHED",
			},
			indent=2,
		)
		tse_tx.full_schema_res = frappe.as_json(response, indent=2)

		# 19. VAT-Childs aus Schema
		receipt = schema.get("standard_v1", {}).get("receipt", {})

		for vat_row in receipt.get("amounts_per_vat_rate", []):
			vat_code = vat_row.get("vat_rate")
			amount = vat_row.get("amount")

			vat_rate_name = frappe.db.get_value(
				"TSE VAT Rate",
				{"vat_rate_code": vat_code},
				"name",
			)

			if not vat_rate_name:
				frappe.throw(
					_("Missing TSE VAT Rate configuration for vat_rate_code '{0}'.").format(vat_code)
				)

			tse_tx.append(
				"vat_rate",
				{
					"vat_rate": vat_rate_name,
					"amount": amount,
				},
			)

		# 20. Payment-Childs aus Schema
		for pay_row in receipt.get("amounts_per_payment_type", []):
			pay_code = pay_row.get("payment_type")
			amount = pay_row.get("amount")

			payment_type_name = frappe.db.get_value(
				"TSE Payment Type",
				{"payment_code": pay_code},
				"name",
			)

			if not payment_type_name:
				frappe.throw(
					_("Missing TSE Payment Type configuration for payment_code '{0}'.").format(pay_code)
				)

			tse_tx.append(
				"payment_types",
				{
					"payment_type": payment_type_name,
					"amount": amount,
				},
			)

		# 21. TSE Transaction Updaten mit Daten und dann Submit
		tse_tx.flags.ignore_permissions = True
		tse_tx.save()
		tse_tx.flags.ignore_permissions = True
		tse_tx.submit()
	except Exception:
		_resolve_started_transaction_failure(
			provider=provider,
			pos_invoice=doc,
			tse_tx=tse_tx,
			tss_id=tss_id,
			client_id=client_id,
			schema=schema,
		)
		raise


@frappe.whitelist()
def refresh_tse_transaction_status(name: str):
	frappe.only_for(("System Manager", "TSE Admin"))

	doc = frappe.get_doc("TSE Transaction", name)
	if not doc.transaction_id:
		frappe.throw(_("Cannot refresh a TSE Transaction without a transaction_id."))

	provider, tss_id, _client_id = _get_transaction_provider_context(doc)
	response = provider.get_transaction(tss_id, doc.transaction_id)
	_sync_existing_transaction_from_remote(doc, response, clear_pos_invoice_link_on_cancel=True)
	return {"name": doc.name, "transaction_status": doc.transaction_status}


@frappe.whitelist()
def resolve_active_tse_transaction(name: str):
	frappe.only_for(("System Manager", "TSE Admin"))

	doc = frappe.get_doc("TSE Transaction", name)
	if not doc.transaction_id:
		frappe.throw(_("Cannot resolve a TSE Transaction without a transaction_id."))

	provider, tss_id, client_id = _get_transaction_provider_context(doc)
	remote = provider.get_transaction(tss_id, doc.transaction_id)
	remote_status = _normalize_transaction_status(remote.get("state") or remote.get("status"))

	if remote_status != "ACTIVE":
		_sync_existing_transaction_from_remote(
			doc,
			remote,
			clear_pos_invoice_link_on_cancel=(remote_status == "CANCELLED"),
		)
		return {"name": doc.name, "transaction_status": doc.transaction_status}

	pos_invoice_docstatus = _get_linked_pos_invoice_docstatus(doc.pos_invoice)
	if pos_invoice_docstatus == 1:
		frappe.throw(_("Cannot resolve an ACTIVE TSE Transaction that is linked to a submitted POS Invoice."))

	next_revision = (_to_int(remote.get("revision") or remote.get("tx_revision"), 1) or 1) + 1
	cancel_response = provider.cancel_transaction(
		tss_id=tss_id,
		tx_id=doc.transaction_id,
		tx_revision=next_revision,
		client_id=client_id,
	)
	_sync_existing_transaction_from_remote(
		doc,
		cancel_response,
		request_payload={
			"state": "CANCELLED",
			"client_id": client_id,
		},
		clear_pos_invoice_link_on_cancel=True,
	)
	return {"name": doc.name, "transaction_status": doc.transaction_status}
