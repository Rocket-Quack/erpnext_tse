# Copyright (c) 2025, RocketQuackIT and contributors
# For license information, please see license.txt

from __future__ import annotations

from datetime import datetime
from typing import Any

import frappe
from frappe import _
from frappe.model.document import Document

from erpnext_tse.erpnext_tse.tss_providers import get_tse_provider


def _is_tse_enabled() -> bool:
	return bool(frappe.db.get_single_value("TSE Settings", "enabled"))


class DSFinVKCashPointClosing(Document):
	def log_provider_event(
		self,
		event_type: str,
		provider_action: str,
		resp: dict | None = None,
		status_before: str | None = None,
		status_after: str | None = None,
		message_summary: str | None = None,
	):
		"""Append a provider event entry to the child table."""
		event = self.append("provider_events", {})
		event.event_time = frappe.utils.now_datetime()
		event.event_type = event_type
		event.provider_action = provider_action
		event.status_before = status_before
		event.status_after = status_after or self.status
		event.message_summary = message_summary or ""

		if resp:
			event.http_status_code = resp.get("status_code")
			error = (resp or {}).get("error") or {}
			event.provider_error_code = error.get("code")
			event.provider_error_message = error.get("message")
			event.response_payload = frappe.as_json(resp, indent=2)
			event.request_id = resp.get("request_id")

		event.triggered_by = frappe.session.user


def create_cash_point_closing_for_pos_closing_entry(doc, method: str | None = None):
	"""DocEvent hook for POS Closing Entry (on_submit)."""
	if isinstance(doc, dict):
		doc = frappe.get_doc(doc)

	if doc.doctype != "POS Closing Entry":
		return
	if not _is_tse_enabled():
		return

	if not getattr(doc, "pos_profile", None):
		frappe.throw(_("POS Closing Entry is missing a POS Profile."))

	pos_profile = frappe.get_doc("POS Profile", doc.pos_profile)
	if not getattr(pos_profile, "tse_client", None):
		frappe.throw(_("POS Profile {0} has no TSE Client set.").format(pos_profile.name))

	tse_client = frappe.get_doc("TSE Client", pos_profile.tse_client)
	register_name = frappe.db.get_value("DSFinV-K Cash Register", {"tse_client": tse_client.name}, "name")
	if not register_name:
		frappe.throw(_("No DSFinV-K Cash Register found for TSE Client {0}.").format(tse_client.name))

	register = frappe.get_doc("DSFinV-K Cash Register", register_name)
	if register.status not in ("ACTIVE", "DRAFT"):
		frappe.throw(
			_("DSFinV-K Cash Register {0} is not active (status: {1}).").format(
				register.name, register.status
			)
		)

	existing = frappe.db.get_value(
		"DSFinV-K Cash Point Closing",
		{"pos_closing_entry": doc.name},
		["name", "status"],
		as_dict=True,
	)
	if existing:
		if existing.status == "COMPLETED":
			return
		frappe.throw(
			_("DSFinV-K Cash Point Closing already exists for POS Closing Entry {0} (status: {1}).").format(
				doc.name, existing.status
			)
		)

	payload = _build_cash_point_closing_payload(doc, register, tse_client)
	closing_doc = _create_cash_point_closing_doc(doc, register, tse_client, payload)

	settings = frappe.get_single("TSE Settings")
	provider = get_tse_provider(settings)

	status_before = closing_doc.status
	try:
		resp = provider.create_cash_point_closing(payload)
		_apply_cash_point_closing_response(closing_doc, resp)
		closing_doc.log_provider_event(
			event_type="CREATE",
			provider_action="create_cash_point_closing",
			resp=resp,
			status_before=status_before,
			status_after=closing_doc.status,
			message_summary="Cash Point Closing created at provider",
		)
		closing_doc.flags.ignore_permissions = True
		closing_doc.save()
		if closing_doc.status in ("PENDING", "WORKING"):
			enqueue_cash_point_closing_status_refresh(closing_doc.name)
	except Exception as exc:
		closing_doc.status = "ERROR"
		closing_doc.log_provider_event(
			event_type="ERROR",
			provider_action="create_cash_point_closing",
			status_before=status_before,
			status_after="ERROR",
			message_summary=str(exc),
		)
		closing_doc.flags.ignore_permissions = True
		closing_doc.save()
		frappe.log_error(frappe.get_traceback(), _("DSFinV-K Cash Point Closing failed"))
		frappe.throw(
			_("DSFinV-K Cash Point Closing failed. Please review the DSFinV-K Cash Point Closing record.")
		)


def _create_cash_point_closing_doc(doc, register, tse_client, payload: dict[str, Any]):
	closing_doc = frappe.get_doc(
		{
			"doctype": "DSFinV-K Cash Point Closing",
			"pos_closing_entry": doc.name,
			"dsfinv_k_cash_register": register.name,
			"tse_client": tse_client.name,
			"pos_profile": doc.pos_profile,
			"company": doc.company,
			"status": "PENDING",
			"client_id": payload.get("client_id"),
			"cash_point_closing_export_id": payload.get("cash_point_closing_export_id"),
			"business_date": payload.get("head", {}).get("business_date"),
			"export_creation_date": _to_datetime(payload.get("head", {}).get("export_creation_date")),
			"request_payload": frappe.as_json(payload, indent=2),
		}
	)
	closing_doc.flags.ignore_permissions = True
	closing_doc.insert()
	return closing_doc


def _apply_cash_point_closing_response(doc, resp: dict[str, Any]):
	doc.closing_id = resp.get("closing_id") or resp.get("_id")
	doc.client_id = resp.get("client_id") or doc.client_id
	doc.status = resp.get("state") or doc.status
	doc.time_creation = _to_datetime(resp.get("time_creation"))
	doc.time_update = _to_datetime(resp.get("time_update"))
	doc.time_deleted = _to_datetime(resp.get("time_deleted"))

	error = resp.get("error") or {}
	doc.error_code = error.get("code")
	doc.error_message = error.get("message")
	doc.response_payload = frappe.as_json(resp, indent=2)


def _build_cash_point_closing_payload(doc, register, tse_client) -> dict[str, Any]:
	cash_register_id = register.cash_register_id or tse_client.client_id
	if not cash_register_id:
		frappe.throw(_("Missing cash register/client ID for DSFinV-K closing."))

	pos_invoices = _get_pos_invoices_from_closing(doc)
	company_currency = _get_company_currency(doc.company)

	transactions = [_build_transaction_from_pos_invoice(inv, company_currency) for inv in pos_invoices]
	if not transactions:
		frappe.throw(_("No transactions available for DSFinV-K Cash Point Closing."))

	closing_export_id = _reserve_cash_point_closing_export_id(register)
	head = _build_cash_point_closing_head(doc, transactions)

	return {
		"client_id": cash_register_id,
		"cash_point_closing_export_id": closing_export_id,
		"head": head,
		"cash_statement": {
			"payment": _build_cash_statement_payment(doc, company_currency),
		},
		"transactions": transactions,
	}


def _reserve_cash_point_closing_export_id(register) -> int:
	last_id = register.last_cash_point_closing_export_id or 0
	next_id = int(last_id) + 1
	register.db_set("last_cash_point_closing_export_id", next_id)
	register.last_cash_point_closing_export_id = next_id
	return next_id


def _build_cash_point_closing_head(doc, transactions: list[dict[str, Any]]) -> dict[str, Any]:
	first_tx = transactions[0]["head"]["transaction_export_id"]
	last_tx = transactions[-1]["head"]["transaction_export_id"]

	export_creation_date = _to_unix(doc.period_end_date) or _to_unix(_build_posting_datetime(doc))
	if not export_creation_date:
		frappe.throw(_("Could not determine export creation date for POS Closing Entry."))

	head = {
		"export_creation_date": export_creation_date,
		"first_transaction_export_id": first_tx,
		"last_transaction_export_id": last_tx,
	}

	if getattr(doc, "posting_date", None):
		head["business_date"] = doc.posting_date

	return head


def _build_cash_statement_payment(doc, company_currency: str) -> dict[str, Any]:
	rows = doc.get("payment_reconciliation") or []
	if not rows:
		frappe.throw(_("POS Closing Entry has no payment reconciliation rows."))

	full_amount = 0.0
	cash_amount = 0.0
	sums: dict[tuple[str, str], float] = {}

	for row in rows:
		mode_of_payment = getattr(row, "mode_of_payment", None) or (
			row.get("mode_of_payment") if isinstance(row, dict) else None
		)
		if not mode_of_payment:
			frappe.throw(_("POS Closing Entry payment row is missing Mode of Payment."))

		amount = (
			getattr(row, "expected_amount", None) if not isinstance(row, dict) else row.get("expected_amount")
		)
		if amount is None:
			amount = (
				getattr(row, "closing_amount", None)
				if not isinstance(row, dict)
				else row.get("closing_amount")
			)

		try:
			amount_f = float(amount or 0)
		except Exception:
			frappe.throw(
				_("Invalid payment amount for Mode of Payment {0}: {1}").format(mode_of_payment, amount)
			)

		if amount_f == 0:
			continue

		payment_type = _get_dsfinvk_payment_type(mode_of_payment)
		key = (payment_type, mode_of_payment)
		sums[key] = sums.get(key, 0.0) + amount_f
		full_amount += amount_f
		if payment_type == "Bar":
			cash_amount += amount_f

	if not sums:
		frappe.throw(_("POS Closing Entry has no non-zero payments."))

	payment_types = [
		{
			"type": payment_type,
			"name": mode_of_payment,
			"currency_code": company_currency,
			"amount": round(amount, 2),
		}
		for (payment_type, mode_of_payment), amount in sums.items()
	]

	return {
		"full_amount": round(full_amount, 2),
		"cash_amount": round(cash_amount, 2),
		"cash_amounts_by_currency": [{"currency_code": company_currency, "amount": round(cash_amount, 2)}],
		"payment_types": payment_types,
	}


def _build_transaction_from_pos_invoice(pos_inv, company_currency: str) -> dict[str, Any]:
	tse_tx = _get_tse_transaction_for_pos_invoice(pos_inv)

	tx_number = getattr(tse_tx, "transaction_number", None)
	try:
		number_int = int(tx_number)
	except Exception:
		frappe.throw(
			_("TSE Transaction {0} has invalid transaction number: {1}.").format(tse_tx.name, tx_number)
		)

	timestamp_start = _to_unix(tse_tx.start_time) or _to_unix(_build_pos_invoice_datetime(pos_inv))
	timestamp_end = _to_unix(tse_tx.end_time) or _to_unix(_build_pos_invoice_datetime(pos_inv))

	if not timestamp_start or not timestamp_end:
		frappe.throw(
			_("Missing timestamps for POS Invoice {0} / TSE Transaction {1}.").format(
				pos_inv.name, tse_tx.name
			)
		)

	amount = getattr(pos_inv, "base_grand_total", None) or getattr(pos_inv, "grand_total", None) or 0

	data = {"full_amount_incl_vat": round(float(amount or 0), 2)}
	data["payment_types"] = _build_payment_types_for_pos_invoice(pos_inv, company_currency)
	data["amounts_per_vat_id"] = _build_amounts_per_vat_definition(pos_inv)

	if not tse_tx.transaction_id:
		frappe.throw(_("Missing transaction ID for TSE Transaction {0}.").format(tse_tx.name))

	return {
		"head": {
			"transaction_export_id": pos_inv.name,
			"type": "Beleg",
			"storno": bool(getattr(pos_inv, "is_return", 0)),
			"number": number_int,
			"timestamp_start": timestamp_start,
			"timestamp_end": timestamp_end,
		},
		"data": data,
		"security": {"tss_tx_id": tse_tx.transaction_id},
	}


def _build_amounts_per_vat_definition(pos_inv) -> list[dict[str, Any]]:
	items = pos_inv.get("items") or []
	if not items:
		frappe.throw(_("POS Invoice has no items."))

	taxes = pos_inv.get("taxes") or []
	if not taxes:
		frappe.throw(_("POS Invoice has no taxes rows."))

	net_amount_by_item_code: dict[str, float] = {}
	for item_row in items:
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
		frappe.throw(_("POS Invoice items are missing item_code values."))

	vat_sums: dict[int, dict[str, float]] = {}
	vat_id_by_tax_account: dict[str, int] = {}

	def parse_item_wise_detail(detail_value) -> tuple[float, float]:
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

		if not tax_account or not item_wise_tax_detail_json:
			continue

		vat_id = vat_id_by_tax_account.get(tax_account)
		if not vat_id:
			vat_id = frappe.db.get_value(
				"DSFinV-K VAT Rate", {"account": tax_account}, "vat_definition_export_id"
			)
			if not vat_id:
				frappe.throw(
					_("No DSFinV-K VAT Rate mapping found for Tax Account '{0}'.").format(tax_account)
				)
			vat_id_by_tax_account[tax_account] = int(vat_id)

		item_wise_details = frappe.parse_json(item_wise_tax_detail_json)
		if not isinstance(item_wise_details, dict):
			continue

		for item_code, detail_value in item_wise_details.items():
			if item_code not in net_amount_by_item_code:
				continue

			rate_percent, tax_amount = parse_item_wise_detail(detail_value)
			bucket = vat_sums.setdefault(int(vat_id), {"excl_vat": 0.0, "vat": 0.0})
			bucket["excl_vat"] += net_amount_by_item_code[item_code]
			bucket["vat"] += float(tax_amount or 0)

	if not vat_sums:
		frappe.throw(_("Could not derive VAT amounts for POS Invoice {0}.").format(pos_inv.name))

	result: list[dict[str, Any]] = []
	for vat_id, amounts in vat_sums.items():
		excl_vat = round(amounts["excl_vat"], 2)
		vat = round(amounts["vat"], 2)
		incl_vat = round(excl_vat + vat, 2)
		result.append(
			{
				"vat_definition_export_id": int(vat_id),
				"incl_vat": incl_vat,
				"excl_vat": excl_vat,
				"vat": vat,
			}
		)

	return result


def _build_payment_types_for_pos_invoice(pos_inv, company_currency: str) -> list[dict[str, Any]]:
	payments_rows = pos_inv.get("payments") or []
	if not payments_rows:
		frappe.throw(_("POS Invoice has no payments rows."))

	try:
		change_remaining = float(getattr(pos_inv, "change_amount", 0) or 0)
	except Exception:
		frappe.throw(
			_("Invalid change_amount on POS Invoice: {0}").format(getattr(pos_inv, "change_amount", None))
		)

	sums: dict[tuple[str, str], float] = {}

	for row in payments_rows:
		mode_of_payment = getattr(row, "mode_of_payment", None) or (
			row.get("mode_of_payment") if isinstance(row, dict) else None
		)
		amount = getattr(row, "amount", None) if not isinstance(row, dict) else row.get("amount")

		if not mode_of_payment:
			frappe.throw(_("POS Invoice payment row is missing Mode of Payment."))

		try:
			amount_f = float(amount or 0)
		except Exception:
			frappe.throw(
				_("Invalid payment amount for Mode of Payment {0}: {1}").format(mode_of_payment, amount)
			)

		if amount_f == 0:
			continue

		final_amount = amount_f
		payment_type = _get_dsfinvk_payment_type(mode_of_payment)

		if change_remaining > 0:
			if final_amount >= change_remaining:
				final_amount -= change_remaining
				change_remaining = 0.0
			else:
				change_remaining -= final_amount
				final_amount = 0.0

		if final_amount == 0:
			continue

		key = (payment_type, mode_of_payment)
		sums[key] = sums.get(key, 0.0) + final_amount

	if not sums:
		frappe.throw(_("POS Invoice has no non-zero payments after change deduction."))

	return [
		{
			"type": payment_type,
			"name": mode_of_payment,
			"currency_code": company_currency,
			"amount": round(amount, 2),
		}
		for (payment_type, mode_of_payment), amount in sums.items()
	]


def _get_pos_invoices_from_closing(doc) -> list[Document]:
	rows = doc.get("pos_transactions") or []
	if not rows:
		frappe.throw(_("POS Closing Entry has no POS Transactions."))

	pos_invoices: list[Document] = []
	seen: set[str] = set()
	for row in rows:
		pos_invoice_name = getattr(row, "pos_invoice", None) or (
			row.get("pos_invoice") if isinstance(row, dict) else None
		)
		if not pos_invoice_name or pos_invoice_name in seen:
			continue

		seen.add(pos_invoice_name)
		pos_invoices.append(frappe.get_doc("POS Invoice", pos_invoice_name))

	if not pos_invoices:
		frappe.throw(_("POS Closing Entry has no valid POS Invoice references."))

	return pos_invoices


def _get_tse_transaction_for_pos_invoice(pos_inv) -> Document:
	if not getattr(pos_inv, "tse_transaction", None):
		frappe.throw(_("POS Invoice {0} has no TSE Transaction.").format(pos_inv.name))

	tse_tx = frappe.get_doc("TSE Transaction", pos_inv.tse_transaction)
	if tse_tx.transaction_status != "FINISHED":
		frappe.throw(
			_("TSE Transaction {0} is not finished (status: {1}).").format(
				tse_tx.name, tse_tx.transaction_status
			)
		)
	return tse_tx


def _get_dsfinvk_payment_type(mode_of_payment: str) -> str:
	payment_type = frappe.db.get_value(
		"DSFinV-K Payment Type", {"mode_of_payment": mode_of_payment}, "payment_type"
	)
	if not payment_type:
		frappe.throw(
			_("No DSFinV-K Payment Type mapping found for Mode of Payment '{0}'.").format(mode_of_payment)
		)
	return payment_type


def _get_company_currency(company: str) -> str:
	return frappe.get_cached_value("Company", company, "default_currency") or "EUR"


def _build_posting_datetime(doc) -> datetime | None:
	if not getattr(doc, "posting_date", None):
		return None

	posting_time = getattr(doc, "posting_time", None)
	if posting_time:
		return frappe.utils.get_datetime(f"{doc.posting_date} {posting_time}")
	return frappe.utils.get_datetime(doc.posting_date)


def _build_pos_invoice_datetime(pos_inv) -> datetime | None:
	if not getattr(pos_inv, "posting_date", None):
		return None

	posting_time = getattr(pos_inv, "posting_time", None)
	if posting_time:
		return frappe.utils.get_datetime(f"{pos_inv.posting_date} {posting_time}")
	return frappe.utils.get_datetime(pos_inv.posting_date)


def _to_datetime(value) -> datetime | None:
	if not value:
		return None
	if isinstance(value, datetime):
		return value
	if isinstance(value, int | float):
		return datetime.fromtimestamp(value)
	return frappe.utils.get_datetime(value)


def _to_unix(value) -> int | None:
	dt = _to_datetime(value)
	if not dt:
		return None
	return int(dt.timestamp())


def enqueue_cash_point_closing_status_refresh(closing_name: str):
	frappe.enqueue(
		"erpnext_tse.erpnext_tse.doctype.dsfinv_k_cash_point_closing.dsfinv_k_cash_point_closing.refresh_cash_point_closing_status",
		queue="short",
		job_id=f"dsfinvk_cpc_refresh:{closing_name}",
		deduplicate=True,
		closing_name=closing_name,
		enqueue_after_commit=True,
	)


def refresh_cash_point_closing_status(closing_name: str):
	if not _is_tse_enabled():
		return

	closing_doc = frappe.get_doc("DSFinV-K Cash Point Closing", closing_name)
	if not closing_doc.closing_id:
		return

	if closing_doc.status in ("COMPLETED", "CANCELLED", "EXPIRED", "DELETED", "ERROR"):
		return

	settings = frappe.get_single("TSE Settings")
	provider = get_tse_provider(settings)
	status_before = closing_doc.status

	try:
		resp = provider.get_cash_point_closing(closing_doc.closing_id)
		_apply_cash_point_closing_response(closing_doc, resp)
		closing_doc.log_provider_event(
			event_type="STATUS_REFRESH",
			provider_action="get_cash_point_closing",
			resp=resp,
			status_before=status_before,
			status_after=closing_doc.status,
			message_summary="Cash Point Closing status refreshed",
		)
		closing_doc.flags.ignore_permissions = True
		closing_doc.save()
	except Exception as exc:
		closing_doc.log_provider_event(
			event_type="ERROR",
			provider_action="get_cash_point_closing",
			status_before=status_before,
			status_after=closing_doc.status,
			message_summary=str(exc),
		)
		closing_doc.flags.ignore_permissions = True
		closing_doc.save()
		frappe.log_error(
			frappe.get_traceback(),
			_("DSFinV-K Cash Point Closing status refresh failed"),
		)


def refresh_pending_cash_point_closings():
	if not _is_tse_enabled():
		return

	pending = frappe.get_all(
		"DSFinV-K Cash Point Closing",
		filters={
			"status": ["in", ["PENDING", "WORKING"]],
			"closing_id": ["is", "set"],
		},
		fields=["name"],
		limit=50,
	)
	for row in pending:
		refresh_cash_point_closing_status(row.name)
