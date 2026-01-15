# Copyright (c) 2025, RocketQuackIT and contributors
# For license information, please see LICENSE

from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.realtime import publish_realtime

from erpnext_tse.erpnext_tse.doctype.tse_client.tse_client import TSEClient
from erpnext_tse.erpnext_tse.tss_providers import get_tse_provider

CLIENT_STATE_MAP = {
	"REGISTERED": "REGISTERED",
	"DEREGISTERED": "DEREGISTERED",
	"DELETED": "DEREGISTERED",
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
	for key in ("_id", "id", "client_id", "clientId"):
		cid = _canonical_id(item.get(key))
		if cid:
			return cid
	return None


def _normalize_status(state: str | None) -> str | None:
	if not state:
		return None
	return CLIENT_STATE_MAP.get(str(state).strip().upper(), "ERROR")


def _extract_remote_list(raw: Any) -> list[dict[str, Any]]:
	if isinstance(raw, list):
		return raw

	if isinstance(raw, dict):
		for key in ("data", "items", "clients", "results"):
			val = raw.get(key)
			if isinstance(val, list):
				return val
		for val in raw.values():
			if isinstance(val, list):
				return val
		if _get_remote_id(raw):
			return [raw]

	frappe.throw(_("Unexpected response while fetching client list from provider."))


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


def _resolve_link(doctype: str, value: str | None) -> str | None:
	if not value:
		return None
	return value if frappe.db.exists(doctype, value) else None


def _ensure_unique_client_name(name: str | None, fallback: str | None) -> str | None:
	def exists(val: str) -> bool:
		return bool(frappe.db.exists("TSE Client", {"client_name": val}))

	if name and not exists(name):
		return name

	if fallback and not exists(fallback):
		return fallback

	base = name or fallback or "recovery-client"
	candidate = base
	idx = 1
	while exists(candidate):
		candidate = f"{base}-{idx}"
		idx += 1
	return candidate


def _apply_updates(doc: TSEClient, updates: dict[str, Any]):
	for field, value in updates.items():
		setattr(doc, field, value)


def _log_event(
	doc: TSEClient,
	*,
	status_before: str | None,
	status_after: str | None,
	resp: dict[str, Any] | None,
	message: str,
):
	doc.log_provider_event(
		event_type="UPDATE_STATUS_RECOVERY",
		provider_action="recovery_sync",
		resp=resp,
		status_before=status_before,
		status_after=status_after,
		message_summary=message,
	)


# ---------------------------------------------------------------------------
# Core sync logic
# ---------------------------------------------------------------------------


def _update_existing_from_remote(doc: TSEClient, remote: dict[str, Any], tss_docname: str | None) -> bool:
	doc.flags.ignore_validate = True

	status_before = doc.client_status
	new_status = _normalize_status(remote.get("state") or remote.get("status"))

	updates: dict[str, Any] = {}
	if new_status and new_status != doc.client_status:
		updates["client_status"] = new_status

	remote_id = _get_remote_id(remote)
	if remote_id and not doc.client_id:
		updates["client_id"] = remote_id

	serial_number = remote.get("serial_number")
	if serial_number and serial_number != doc.serial_number:
		updates["serial_number"] = serial_number

	if tss_docname and doc.tse_security_device != tss_docname:
		updates["tse_security_device"] = tss_docname

	meta = _extract_metadata(remote)
	meta_name = _meta_value(meta, "tse_client_name", "client_name", "name")
	if meta_name and not doc.client_name:
		updates["client_name"] = _ensure_unique_client_name(meta_name, remote_id)

	meta_company = _resolve_link("Company", _meta_value(meta, "company"))
	if meta_company and not doc.company:
		updates["company"] = meta_company

	meta_pos_profile = _resolve_link("POS Profile", _meta_value(meta, "pos_profile", "pos_profile_name"))
	if meta_pos_profile and not doc.pos_profile:
		if not frappe.db.exists(
			"TSE Client",
			{"pos_profile": meta_pos_profile, "name": ["!=", doc.name]},
		):
			updates["pos_profile"] = meta_pos_profile

	if updates:
		_apply_updates(doc, updates)

	status_after = doc.client_status
	message = (
		_("Updated from provider during recovery sync.")
		if updates
		else _("Checked provider during recovery sync (no changes).")
	)

	_log_event(
		doc,
		status_before=status_before,
		status_after=status_after,
		resp=remote,
		message=message,
	)
	if not doc.pos_profile or not doc.client_name or not doc.tse_security_device:
		doc.flags.ignore_mandatory = True
	doc.save(ignore_permissions=True)
	return bool(updates)


def _create_missing_from_remote(remote: dict[str, Any], tss_docname: str) -> TSEClient | None:
	remote_id = _get_remote_id(remote)
	if not remote_id:
		return None

	existing_name = frappe.db.get_value("TSE Client", {"client_id": remote_id}, "name")
	if existing_name:
		doc = frappe.get_doc("TSE Client", existing_name)
		_update_existing_from_remote(doc, remote, tss_docname)
		return doc

	meta = _extract_metadata(remote)
	client_name = _meta_value(meta, "tse_client_name", "client_name", "name")
	client_name = _ensure_unique_client_name(client_name, remote_id)

	pos_profile = _resolve_link("POS Profile", _meta_value(meta, "pos_profile", "pos_profile_name"))
	if pos_profile and frappe.db.exists("TSE Client", {"pos_profile": pos_profile}):
		pos_profile = None

	company = _resolve_link("Company", _meta_value(meta, "company"))
	provider_status = _normalize_status(remote.get("state") or remote.get("status"))

	doc = frappe.new_doc("TSE Client")
	doc.client_name = client_name
	doc.company = company
	doc.tse_security_device = tss_docname
	doc.pos_profile = pos_profile
	doc.client_id = remote_id
	doc.serial_number = remote.get("serial_number")
	doc.client_status = provider_status or "ERROR"

	doc.flags.ignore_validate = True
	if not doc.pos_profile:
		doc.flags.ignore_mandatory = True

	doc.insert(ignore_permissions=True)

	_log_event(
		doc,
		status_before=None,
		status_after=doc.client_status,
		resp=remote,
		message=_("Created from provider during recovery sync."),
	)
	doc.save(ignore_permissions=True)
	return doc


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
		"erpnext_tse.erpnext_tse.doctype.tse_client.recovery.run_recovery_sync",
		queue="long",
		timeout=3600,
		job_id="tse_client_recovery_sync",
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

		devices = frappe.get_all("TSE Security Device", fields=["name", "tss_id", "tss_status"])
		remote_items: list[dict[str, Any]] = []
		processed_devices: set[str] = set()

		for row in devices:
			if not row.tss_id:
				continue
			if row.tss_status == "ORPHANED":
				continue
			processed_devices.add(row.name)
			clients = _extract_remote_list(provider.list_clients(row.tss_id))
			for item in clients:
				item = dict(item)
				item["__tss_id"] = row.tss_id
				item["__tss_docname"] = row.name
				remote_items.append(item)

		local_rows = frappe.get_all(
			"TSE Client",
			fields=[
				"name",
				"client_id",
				"client_name",
				"pos_profile",
				"company",
				"client_status",
				"tse_security_device",
			],
		)

		local_by_id = {_canonical_id(row.client_id): row for row in local_rows if row.client_id}
		local_by_name = {row.name: row for row in local_rows}
		local_by_client_name = {
			_canonical_text(row.client_name): row for row in local_rows if row.client_name
		}
		local_by_pos_profile = {
			_canonical_text(row.pos_profile): row for row in local_rows if row.pos_profile
		}

		matched_local: set[str] = set()
		created = 0
		updated = 0
		checked = 0
		orphaned = 0
		skipped_no_device = 0

		for remote in remote_items:
			remote_id = _get_remote_id(remote)
			meta = _extract_metadata(remote)
			tss_docname = remote.get("__tss_docname")

			candidate = None
			if remote_id:
				candidate = local_by_id.get(_canonical_id(remote_id))

			if not candidate:
				docname = _canonical_text(_meta_value(meta, "tse_client_docname", "docname"))
				if docname:
					candidate = local_by_name.get(docname)

			if not candidate:
				client_name = _canonical_text(_meta_value(meta, "tse_client_name", "client_name", "name"))
				if client_name:
					candidate = local_by_client_name.get(client_name)

			if not candidate:
				pos_profile = _canonical_text(_meta_value(meta, "pos_profile", "pos_profile_name"))
				if pos_profile:
					candidate = local_by_pos_profile.get(pos_profile)

			if candidate and candidate.name in matched_local:
				candidate = None

			if candidate:
				doc = frappe.get_doc("TSE Client", candidate.name)
				if _update_existing_from_remote(doc, remote, tss_docname):
					updated += 1
				else:
					checked += 1
				matched_local.add(doc.name)
				continue

			if not tss_docname:
				skipped_no_device += 1
				continue

			created_doc = _create_missing_from_remote(remote, tss_docname)
			if created_doc:
				created += 1
				matched_local.add(created_doc.name)

		for row in local_rows:
			if not row.client_id:
				continue
			if row.tse_security_device not in processed_devices:
				continue
			if row.name in matched_local:
				continue

			doc = frappe.get_doc("TSE Client", row.name)
			if doc.client_status == "ORPHANED":
				continue

			status_before = doc.client_status
			doc.client_status = "ORPHANED"
			doc.flags.ignore_validate = True
			_log_event(
				doc,
				status_before=status_before,
				status_after=doc.client_status,
				resp={"error": {"message": "Client missing at provider"}},
				message=_("Marked as ORPHANED because client was not found at provider."),
			)
			if not doc.pos_profile or not doc.client_name or not doc.tse_security_device:
				doc.flags.ignore_mandatory = True
			doc.save(ignore_permissions=True)
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
			if skipped_no_device:
				parts.append(_("{0} skipped (missing device)").format(skipped_no_device))

			message = _("Recovery sync completed successfully.")
			if parts:
				message = f"{message} " + ", ".join(parts) + "."

			publish_realtime(
				"tse_client_recovery_done",
				{"message": message},
				user=user,
			)
	except Exception:
		frappe.db.rollback()
		frappe.log_error(frappe.get_traceback(), _("TSE Client Recovery Sync failed"))
		raise
