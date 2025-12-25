# Copyright (c) 2025, RocketQuackIT and contributors
# For license information, please see LICENSE

from __future__ import annotations

from datetime import datetime
from typing import Any

import frappe
from frappe import _
from frappe.realtime import publish_realtime

from erpnext_tse.erpnext_tse.tss_providers import get_tse_provider

TRANSACTION_STATE_MAP = {
	"ACTIVE": "ACTIVE",
	"FINISHED": "FINISHED",
	"CANCELLED": "CANCELLED",
	"CANCELED": "CANCELLED",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _canonical_id(raw: Any) -> str | None:
	if raw is None:
		return None
	return str(raw).strip().lower() or None


def _canonical_text(raw: Any) -> str | None:
	if raw is None:
		return None
	return str(raw).strip() or None


def _get_remote_id(item: dict[str, Any]) -> str | None:
	if not isinstance(item, dict):
		return None
	for key in ("_id", "id", "transaction_id", "tx_id", "txId"):
		rid = _canonical_id(item.get(key))
		if rid:
			return rid
	return None


def _get_remote_client_id(item: dict[str, Any]) -> str | None:
	if not isinstance(item, dict):
		return None
	for key in ("client_id", "clientId"):
		cid = _canonical_id(item.get(key))
		if cid:
			return cid
	return None


def _normalize_status(state: str | None) -> str | None:
	if not state:
		return None
	return TRANSACTION_STATE_MAP.get(str(state).strip().upper(), "ERROR")


def _extract_remote_list(raw: Any) -> list[dict[str, Any]]:
	if isinstance(raw, list):
		return raw

	if isinstance(raw, dict):
		for key in ("data", "items", "transactions", "tx", "results"):
			val = raw.get(key)
			if isinstance(val, list):
				return val
		for val in raw.values():
			if isinstance(val, list):
				return val
		if _get_remote_id(raw):
			return [raw]

	frappe.throw(_("Unexpected response while fetching transaction list from provider."))


def _to_datetime(val: Any) -> datetime | None:
	if val is None:
		return None
	if isinstance(val, datetime):
		return val
	try:
		if isinstance(val, int | float):
			return datetime.fromtimestamp(val)
		if isinstance(val, str):
			stripped = val.strip()
			if stripped.isdigit():
				return datetime.fromtimestamp(int(stripped))
			return frappe.utils.get_datetime(stripped)
	except Exception:
		return None
	return None


def _extract_schema(remote: dict[str, Any]) -> dict[str, Any] | None:
	schema = remote.get("schema")
	return schema if isinstance(schema, dict) else None


def _extract_receipt_type(schema: dict[str, Any] | None) -> str | None:
	if not schema:
		return None
	std = schema.get("standard_v1") or {}
	receipt = std.get("receipt") or {}
	return _canonical_text(receipt.get("receipt_type"))


def _normalize_tx_type(remote: dict[str, Any], schema: dict[str, Any] | None) -> str:
	for key in ("transaction_type", "type"):
		val = _canonical_text(remote.get(key))
		if val:
			return val
	receipt_type = _extract_receipt_type(schema)
	if receipt_type:
		return receipt_type
	return "UNKNOWN"


def _update_existing_from_remote(
	doc,
	remote: dict[str, Any],
	*,
	tss_docname: str | None,
	client_by_id: dict[str, dict[str, Any]],
	tss_company: str | None,
) -> bool:
	updates: dict[str, Any] = {}

	remote_id = _get_remote_id(remote)
	if remote_id and not doc.transaction_id:
		updates["transaction_id"] = remote_id

	status = _normalize_status(remote.get("state") or remote.get("status"))
	if status and status != doc.transaction_status:
		updates["transaction_status"] = status

	if tss_docname and doc.tse_security_device != tss_docname:
		updates["tse_security_device"] = tss_docname

	remote_client_id = _get_remote_client_id(remote)
	client_row = client_by_id.get(_canonical_id(remote_client_id)) if remote_client_id else None
	if client_row:
		if not doc.tse_client or doc.tse_client != client_row["name"]:
			updates["tse_client"] = client_row["name"]

	if not doc.company:
		if client_row and client_row.get("company"):
			updates["company"] = client_row.get("company")
		elif tss_company:
			updates["company"] = tss_company

	if not doc.transaction_type:
		schema = _extract_schema(remote)
		updates["transaction_type"] = _normalize_tx_type(remote, schema)

	if not doc.receipt_type:
		receipt_type = _extract_receipt_type(_extract_schema(remote))
		if receipt_type:
			updates["receipt_type"] = receipt_type

	revision = remote.get("revision") or remote.get("tx_revision")
	if revision and revision != doc.transaction_revision:
		updates["transaction_revision"] = revision

	number = remote.get("number") or remote.get("transaction_number")
	if number and number != doc.transaction_number:
		updates["transaction_number"] = number

	signature = remote.get("signature") or {}
	sig_counter = signature.get("counter") if isinstance(signature, dict) else remote.get("signature_counter")
	if sig_counter and sig_counter != doc.signature_counter:
		updates["signature_counter"] = sig_counter

	start_time = _to_datetime(remote.get("time_start") or remote.get("timeStart"))
	if start_time and start_time != doc.start_time:
		updates["start_time"] = start_time

	end_time = _to_datetime(remote.get("time_end") or remote.get("timeEnd"))
	if end_time and end_time != doc.end_time:
		updates["end_time"] = end_time

	qr_code_data = _canonical_text(remote.get("qr_code_data"))
	if qr_code_data and qr_code_data != doc.qr_code_data:
		updates["qr_code_data"] = qr_code_data

	if not doc.full_schema_res:
		updates["full_schema_res"] = frappe.as_json(remote, indent=2)

	if updates:
		frappe.db.set_value(
			"TSE Transaction",
			doc.name,
			updates,
			update_modified=False,
		)

	return bool(updates)


def _create_missing_from_remote(
	remote: dict[str, Any],
	*,
	tss_docname: str,
	client_by_id: dict[str, dict[str, Any]],
	tss_company: str | None,
) -> str | None:
	remote_id = _get_remote_id(remote)
	if not remote_id:
		return None

	existing_name = frappe.db.get_value("TSE Transaction", {"transaction_id": remote_id}, "name")
	if existing_name:
		doc = frappe.get_doc("TSE Transaction", existing_name)
		_update_existing_from_remote(
			doc,
			remote,
			tss_docname=tss_docname,
			client_by_id=client_by_id,
			tss_company=tss_company,
		)
		return existing_name

	remote_client_id = _get_remote_client_id(remote)
	client_row = client_by_id.get(_canonical_id(remote_client_id)) if remote_client_id else None

	schema = _extract_schema(remote)

	doc = frappe.new_doc("TSE Transaction")
	doc.tse_security_device = tss_docname
	doc.tse_client = client_row.get("name") if client_row else None
	doc.company = client_row.get("company") if client_row and client_row.get("company") else tss_company
	doc.transaction_type = _normalize_tx_type(remote, schema)
	doc.transaction_id = remote_id
	doc.transaction_status = _normalize_status(remote.get("state") or remote.get("status"))
	doc.transaction_revision = remote.get("revision") or remote.get("tx_revision")
	doc.transaction_number = remote.get("number") or remote.get("transaction_number")
	doc.signature_counter = (
		(remote.get("signature") or {}).get("counter")
		if isinstance(remote.get("signature"), dict)
		else remote.get("signature_counter")
	)
	doc.start_time = _to_datetime(remote.get("time_start") or remote.get("timeStart"))
	doc.end_time = _to_datetime(remote.get("time_end") or remote.get("timeEnd"))
	doc.qr_code_data = remote.get("qr_code_data")
	doc.receipt_type = _extract_receipt_type(schema)
	doc.full_schema_res = frappe.as_json(remote, indent=2)

	doc.flags.ignore_validate = True
	if not doc.tse_client or not doc.company or not doc.transaction_type:
		doc.flags.ignore_mandatory = True

	doc.insert(ignore_permissions=True)

	if doc.transaction_status in ("FINISHED", "CANCELLED"):
		frappe.db.set_value(
			"TSE Transaction",
			doc.name,
			{"docstatus": 1},
			update_modified=False,
		)

	return doc.name


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


@frappe.whitelist()
def enqueue_recovery_sync() -> dict[str, Any]:
	settings = frappe.get_single("TSE Settings")
	if not getattr(settings, "enabled", False):
		frappe.throw(_("TSE functionality is disabled in TSE Settings."))
	if not getattr(settings, "recovery_sync_enabled", False):
		frappe.throw(_("Recovery mode is disabled in TSE Settings."))

	job = frappe.enqueue(
		"erpnext_tse.erpnext_tse.doctype.tse_transaction.recovery.run_recovery_sync",
		queue="long",
		timeout=600,
		job_id="tse_transaction_recovery_sync",
		enqueue_after_commit=True,
		now=frappe.flags.in_test,
		user=frappe.session.user,
	)

	job_id = getattr(job, "id", None) or getattr(job, "name", None)
	return {"job_id": job_id}


def run_recovery_sync(user: str | None = None, **kwargs):
	try:
		settings = frappe.get_single("TSE Settings")
		if not getattr(settings, "enabled", False):
			return
		if not getattr(settings, "recovery_sync_enabled", False):
			return

		provider = get_tse_provider(settings)

		devices = frappe.get_all(
			"TSE Security Device",
			fields=["name", "tss_id", "tss_status", "company"],
		)

		clients = frappe.get_all(
			"TSE Client",
			fields=["name", "client_id", "company"],
		)
		client_by_id = {_canonical_id(row.client_id): row for row in clients if row.client_id}

		remote_items: list[dict[str, Any]] = []
		processed_devices: set[str] = set()

		for device in devices:
			if not device.tss_id:
				continue
			if device.tss_status == "ORPHANED":
				continue
			processed_devices.add(device.name)
			items = _extract_remote_list(provider.list_transactions(device.tss_id))
			for item in items:
				item = dict(item)
				item["__tss_docname"] = device.name
				item["__tss_company"] = device.company
				remote_items.append(item)

		local_rows = frappe.get_all(
			"TSE Transaction",
			fields=[
				"name",
				"transaction_id",
				"transaction_status",
				"tse_security_device",
			],
		)
		local_by_id = {_canonical_id(row.transaction_id): row for row in local_rows if row.transaction_id}

		matched_local: set[str] = set()
		created = 0
		updated = 0
		checked = 0
		orphaned = 0
		skipped_no_id = 0

		for remote in remote_items:
			remote_id = _get_remote_id(remote)
			if not remote_id:
				skipped_no_id += 1
				continue

			candidate = local_by_id.get(_canonical_id(remote_id))
			if candidate:
				doc = frappe.get_doc("TSE Transaction", candidate.name)
				if _update_existing_from_remote(
					doc,
					remote,
					tss_docname=remote.get("__tss_docname"),
					client_by_id=client_by_id,
					tss_company=remote.get("__tss_company"),
				):
					updated += 1
				else:
					checked += 1
				matched_local.add(doc.name)
				continue

			tss_docname = remote.get("__tss_docname")
			if not tss_docname:
				continue

			created_name = _create_missing_from_remote(
				remote,
				tss_docname=tss_docname,
				client_by_id=client_by_id,
				tss_company=remote.get("__tss_company"),
			)
			if created_name:
				created += 1
				matched_local.add(created_name)

		for row in local_rows:
			if not row.transaction_id:
				continue
			if row.tse_security_device not in processed_devices:
				continue
			if row.name in matched_local:
				continue

			doc = frappe.get_doc("TSE Transaction", row.name)
			if doc.transaction_status == "ORPHANED":
				continue

			frappe.db.set_value(
				"TSE Transaction",
				doc.name,
				{"transaction_status": "ORPHANED"},
				update_modified=False,
			)
			orphaned += 1

		frappe.db.commit()

		if user:
			parts = []
			if created:
				parts.append(_("{0} created").format(created))
			if updated:
				parts.append(_("{0} updated").format(updated))
			if checked:
				parts.append(_("{0} unchanged").format(checked))
			if orphaned:
				parts.append(_("{0} orphaned").format(orphaned))
			if skipped_no_id:
				parts.append(_("{0} skipped (missing transaction id)").format(skipped_no_id))

			message = _("Recovery sync completed successfully.")
			if parts:
				message = f"{message} " + ", ".join(parts) + "."

			publish_realtime(
				"tse_transaction_recovery_done",
				{"message": message},
				user=user,
			)
	except Exception:
		frappe.db.rollback()
		frappe.log_error(frappe.get_traceback(), "TSE Transaction Recovery Sync failed")
		raise
