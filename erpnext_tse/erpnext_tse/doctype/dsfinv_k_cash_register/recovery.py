# Copyright (c) 2025, RocketQuackIT and contributors
# For license information, please see LICENSE

from __future__ import annotations

from datetime import datetime
from typing import Any

import frappe
from frappe import _
from frappe.realtime import publish_realtime

from erpnext_tse.erpnext_tse.doctype.tse_client.tse_client import _sync_dsfinvk_cash_register
from erpnext_tse.erpnext_tse.tss_providers import get_tse_provider

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
	for key in ("_id", "id", "cash_register_id", "cashRegisterId", "client_id", "clientId"):
		rid = _canonical_id(item.get(key))
		if rid:
			return rid
	return None


def _extract_remote_list(raw: Any) -> list[dict[str, Any]]:
	if isinstance(raw, list):
		return raw

	if isinstance(raw, dict):
		for key in ("data", "items", "cash_registers", "cashRegisters", "results"):
			val = raw.get(key)
			if isinstance(val, list):
				return val
		for val in raw.values():
			if isinstance(val, list):
				return val
		if _get_remote_id(raw):
			return [raw]

	frappe.throw(_("Unexpected response while fetching cash registers from provider."))


def _extract_metadata(remote: dict[str, Any]) -> dict[str, Any]:
	meta = remote.get("metadata")
	return meta if isinstance(meta, dict) else {}


def _meta_value(meta: dict[str, Any], *keys: str) -> str | None:
	for key in keys:
		val = meta.get(key)
		if val is None:
			continue
		cleaned = str(val).strip()
		if cleaned:
			return cleaned
	return None


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


def _extract_cash_register_type(remote: dict[str, Any]) -> tuple[str | None, str | None]:
	raw_type = remote.get("cash_register_type") or remote.get("cashRegisterType")
	tss_id = _canonical_text(remote.get("tss_id") or remote.get("tssId"))
	if isinstance(raw_type, dict):
		tss_id = _canonical_text(raw_type.get("tss_id") or raw_type.get("tssId") or tss_id)
		raw_type = (
			raw_type.get("type") or raw_type.get("cash_register_type") or raw_type.get("cashRegisterType")
		)
	return _canonical_text(raw_type), tss_id


def _extract_software(remote: dict[str, Any]) -> tuple[str | None, str | None]:
	software = remote.get("software")
	if not isinstance(software, dict):
		return None, None
	return _canonical_text(software.get("brand")), _canonical_text(software.get("version"))


def _resolve_client(
	remote: dict[str, Any],
	*,
	client_by_id: dict[str, dict[str, Any]],
	client_by_docname: dict[str, dict[str, Any]],
	client_by_client_name: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
	remote_id = _get_remote_id(remote)
	if remote_id:
		candidate = client_by_id.get(_canonical_id(remote_id))
		if candidate:
			return candidate

	meta = _extract_metadata(remote)
	docname = _canonical_text(_meta_value(meta, "tse_client", "tse_client_docname", "tse_client_doc_name"))
	if docname:
		candidate = client_by_docname.get(_canonical_text(docname))
		if candidate:
			return candidate

	client_name = _canonical_text(_meta_value(meta, "tse_client_name", "client_name", "name"))
	if client_name:
		return client_by_client_name.get(_canonical_text(client_name))

	return None


def _apply_remote_to_doc(doc, remote: dict[str, Any], client_row: dict[str, Any]) -> bool:
	updates: dict[str, Any] = {}

	remote_id = _get_remote_id(remote)
	if remote_id and doc.cash_register_id != remote_id:
		updates["cash_register_id"] = remote_id

	reg_type, tss_id = _extract_cash_register_type(remote)
	if reg_type and doc.cash_register_type != reg_type:
		updates["cash_register_type"] = reg_type
	if tss_id and doc.tss_id != tss_id:
		updates["tss_id"] = tss_id

	brand = _canonical_text(remote.get("brand"))
	if brand and doc.brand != brand:
		updates["brand"] = brand

	model = _canonical_text(remote.get("model"))
	if model and doc.model != model:
		updates["model"] = model

	base_currency = _canonical_text(remote.get("base_currency_code") or remote.get("base_currency"))
	if base_currency and doc.base_currency_code != base_currency:
		updates["base_currency_code"] = base_currency

	software_brand, software_version = _extract_software(remote)
	if software_brand and doc.software_brand != software_brand:
		updates["software_brand"] = software_brand
	if software_version and doc.software_version != software_version:
		updates["software_version"] = software_version

	revision = remote.get("revision")
	if revision is not None and revision != doc.revision:
		updates["revision"] = revision

	time_creation = _to_datetime(remote.get("time_creation"))
	if time_creation and doc.time_creation != time_creation:
		updates["time_creation"] = time_creation

	time_update = _to_datetime(remote.get("time_update"))
	if time_update and doc.time_update != time_update:
		updates["time_update"] = time_update

	metadata = _extract_metadata(remote)
	if metadata:
		metadata_json = frappe.as_json(metadata, indent=2)
		if metadata_json != doc.metadata_json:
			updates["metadata_json"] = metadata_json

	if client_row:
		if doc.tse_client != client_row.get("name"):
			updates["tse_client"] = client_row.get("name")
		if client_row.get("pos_profile") and doc.pos_profile != client_row.get("pos_profile"):
			updates["pos_profile"] = client_row.get("pos_profile")
		if client_row.get("company") and doc.company != client_row.get("company"):
			updates["company"] = client_row.get("company")

	if doc.status != "ACTIVE":
		updates["status"] = "ACTIVE"

	if updates:
		for field, value in updates.items():
			setattr(doc, field, value)

	return bool(updates)


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
		"erpnext_tse.erpnext_tse.doctype.dsfinv_k_cash_register.recovery.run_recovery_sync",
		queue="long",
		timeout=3600,
		job_id="dsfinv_k_cash_register_recovery_sync",
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
		if not hasattr(provider, "list_cash_registers"):
			frappe.throw(_("Selected provider does not support cash register recovery."))

		remote_items = _extract_remote_list(provider.list_cash_registers())
		remote_ids = {_canonical_id(_get_remote_id(item)) for item in remote_items if _get_remote_id(item)}

		clients = frappe.get_all(
			"TSE Client",
			fields=[
				"name",
				"client_id",
				"client_name",
				"tse_security_device",
				"pos_profile",
				"company",
				"client_status",
			],
		)
		client_by_id = {_canonical_id(row.client_id): row for row in clients if row.client_id}
		client_by_docname = {_canonical_text(row.name): row for row in clients}
		client_by_client_name = {_canonical_text(row.client_name): row for row in clients if row.client_name}

		registers = frappe.get_all(
			"DSFinV-K Cash Register",
			fields=["name", "cash_register_id", "tse_client", "status"],
		)
		register_by_id = {
			_canonical_id(row.cash_register_id): row for row in registers if row.cash_register_id
		}
		register_by_client = {row.tse_client: row for row in registers if row.tse_client}

		created = 0
		updated = 0
		checked = 0
		skipped_no_client = 0

		for remote in remote_items:
			remote = dict(remote)
			client_row = _resolve_client(
				remote,
				client_by_id=client_by_id,
				client_by_docname=client_by_docname,
				client_by_client_name=client_by_client_name,
			)
			if not client_row:
				skipped_no_client += 1
				continue

			register_row = register_by_client.get(client_row.get("name"))
			if not register_row:
				remote_id = _canonical_id(_get_remote_id(remote))
				if remote_id:
					register_row = register_by_id.get(remote_id)

			if register_row:
				doc = frappe.get_doc("DSFinV-K Cash Register", register_row.name)
				status_before = doc.status
				changed = _apply_remote_to_doc(doc, remote, client_row)
				message = (
					_("Updated from provider during recovery sync.")
					if changed
					else _("Checked provider during recovery sync (no changes).")
				)
				doc.log_provider_event(
					event_type="RECOVERY_SYNC",
					provider_action="list_cash_registers",
					resp=remote,
					status_before=status_before,
					status_after=doc.status,
					message_summary=message,
				)
				doc.save(ignore_permissions=True)
				if changed:
					updated += 1
				else:
					checked += 1
				continue

			doc = frappe.new_doc("DSFinV-K Cash Register")
			doc.tse_client = client_row.get("name")
			doc.pos_profile = client_row.get("pos_profile")
			doc.company = client_row.get("company")
			doc.status = "DRAFT"

			_apply_remote_to_doc(doc, remote, client_row)
			doc.log_provider_event(
				event_type="RECOVERY_SYNC",
				provider_action="list_cash_registers",
				resp=remote,
				status_before=None,
				status_after=doc.status,
				message_summary=_("Created from provider during recovery sync."),
			)
			doc.insert(ignore_permissions=True)
			created += 1

		created_remote = 0
		skipped_no_device = 0
		skipped_no_tss_id = 0
		skipped_not_registered = 0

		for row in clients:
			client_id = _canonical_id(row.client_id)
			if not client_id or client_id in remote_ids:
				continue
			if row.client_status and row.client_status != "REGISTERED":
				skipped_not_registered += 1
				continue
			if not row.tse_security_device:
				skipped_no_device += 1
				continue

			tss = frappe.get_doc("TSE Security Device", row.tse_security_device)
			if not tss.tss_id or tss.tss_status == "ORPHANED":
				skipped_no_tss_id += 1
				continue

			client_doc = frappe.get_doc("TSE Client", row.name)
			_sync_dsfinvk_cash_register(client_doc, tss, provider)
			created_remote += 1

		frappe.db.commit()

		if user:
			parts = []
			if created:
				parts.append(_("{0} created").format(created))
			if updated:
				parts.append(_("{0} updated").format(updated))
			if checked:
				parts.append(_("{0} unchanged").format(checked))
			if created_remote:
				parts.append(_("{0} created at provider").format(created_remote))
			if skipped_no_client:
				parts.append(_("{0} skipped (missing client mapping)").format(skipped_no_client))
			if skipped_no_device:
				parts.append(_("{0} skipped (missing device)").format(skipped_no_device))
			if skipped_no_tss_id:
				parts.append(_("{0} skipped (missing TSS ID)").format(skipped_no_tss_id))
			if skipped_not_registered:
				parts.append(_("{0} skipped (client not registered)").format(skipped_not_registered))

			message = _("Recovery sync completed successfully.")
			if parts:
				message = f"{message} " + ", ".join(parts) + "."

			publish_realtime(
				"dsfinv_k_cash_register_recovery_done",
				{"message": message},
				user=user,
			)
	except Exception:
		frappe.db.rollback()
		frappe.log_error(frappe.get_traceback(), _("DSFinV-K Cash Register Recovery Sync failed"))
		raise
