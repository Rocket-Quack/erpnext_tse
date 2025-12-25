# Copyright (c) 2025, RocketQuackIT and contributors
# For license information, please see LICENSE

from __future__ import annotations

from datetime import datetime
from typing import Any

import frappe
from frappe import _
from frappe.realtime import publish_realtime

from erpnext_tse.erpnext_tse.doctype.tse_security_device.tse_security_device import (
	TSESecurityDevice,
)
from erpnext_tse.erpnext_tse.tss_providers import get_tse_provider

# Mapping of provider states to local tss_status
PROVIDER_STATE_MAP = {
	"CREATED": "CREATED",
	"UNINITIALIZED": "UNINITIALIZED",
	"INITIALIZED": "INITIALIZED",
	"DISABLED": "DISABLED",
	# Fiskaly returns DELETED once a TSS is deprovisioned; locally we treat it as DISABLED
	"DELETED": "DISABLED",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _canonical_id(raw: Any) -> str | None:
	if raw is None:
		return None
	return str(raw).strip().lower() or None


def _get_remote_id(item: dict[str, Any]) -> str | None:
	"""Return the TSS id from a provider response item."""
	if not isinstance(item, dict):
		return None
	for key in ("id", "_id", "tss_id", "tssId", "tssid"):
		cid = _canonical_id(item.get(key))
		if cid:
			return cid
	return None


def _normalize_status(state: str | None) -> str | None:
	if not state:
		return None
	return PROVIDER_STATE_MAP.get(str(state).strip().upper())


def _extract_remote_list(raw: Any) -> list[dict[str, Any]]:
	"""Normalize provider list_tss responses into a list of dicts."""
	if isinstance(raw, list):
		return raw

	if isinstance(raw, dict):
		# Prefer the official Fiskaly key "data"
		for key in ("data", "items", "tss", "results"):
			val = raw.get(key)
			if isinstance(val, list):
				return val
		# Sometimes nested dicts may hold the list values
		for val in raw.values():
			if isinstance(val, list):
				return val

		# Single object
		if _get_remote_id(raw):
			return [raw]

	frappe.throw(_("Unexpected response while fetching TSS list from provider."))


def _apply_updates(doc: TSESecurityDevice, updates: dict[str, Any]):
	"""Apply updates to the doc without triggering validation."""
	for field, value in updates.items():
		setattr(doc, field, value)


def _log_event(
	doc: TSESecurityDevice,
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


DATETIME_FIELDS = {"activated_at", "deactivated_at"}


def _to_datetime(val: Any) -> datetime | None:
	"""Convert Fiskaly timestamps (unix seconds or iso strings) to datetime."""
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
			# fall back to frappe parser
			return frappe.utils.get_datetime(stripped)
	except Exception:
		return None
	return None


def _normalize_datetime_fields(doc: TSESecurityDevice):
	"""Ensure datetime fields on the doc are proper datetime objects."""
	for field in DATETIME_FIELDS:
		value = getattr(doc, field, None)
		converted = _to_datetime(value)
		if converted:
			setattr(doc, field, converted)
		elif isinstance(value, int | float | str):
			# invalid / unparsable timestamp -> reset to None
			setattr(doc, field, None)


# ---------------------------------------------------------------------------
# Core sync logic
# ---------------------------------------------------------------------------


def _update_existing_from_remote(doc: TSESecurityDevice, remote: dict[str, Any]) -> None:
	_normalize_datetime_fields(doc)

	status_before = doc.tss_status
	new_status = _normalize_status(remote.get("state") or remote.get("status"))

	updates: dict[str, Any] = {}
	if new_status and new_status != doc.tss_status:
		updates["tss_status"] = new_status

	# Map common remote fields
	field_map = {
		"tss_serial_number": "serial_number",
		"activated_at": "time_init",
		"deactivated_at": "time_disable",
	}
	for target, source in field_map.items():
		val = remote.get(source)
		if target in DATETIME_FIELDS:
			val = _to_datetime(val)
		if val and getattr(doc, target) != val:
			updates[target] = val

	# Pick up admin_puk if remote provides it and we don't have it
	if remote.get("admin_puk") and not doc.get_password("admin_puk", raise_exception=False):
		updates["admin_puk"] = remote.get("admin_puk")

	if updates:
		_apply_updates(doc, updates)
		doc.tss_status = updates.get("tss_status", doc.tss_status)

	status_after = doc.tss_status
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
	_normalize_datetime_fields(doc)
	doc.save(ignore_permissions=True)


def _create_missing_from_remote(remote: dict[str, Any]) -> TSESecurityDevice:
	raw_id = (
		remote.get("id")
		or remote.get("_id")
		or remote.get("tss_id")
		or remote.get("tssId")
		or remote.get("tssid")
	)
	tss_id_clean = str(raw_id).strip()
	provider_status = _normalize_status(remote.get("state") or remote.get("status")) or "ERROR"

	# Falls bereits eine TSS mit gleicher tss_id existiert, nur aktualisieren
	existing_name = frappe.db.get_value("TSE Security Device", {"tss_id": tss_id_clean}, "name")
	if existing_name:
		doc = frappe.get_doc("TSE Security Device", existing_name)
		_update_existing_from_remote(doc, remote)
		return doc

	doc = frappe.new_doc("TSE Security Device")
	doc.internal_name = remote.get("description") or tss_id_clean
	doc.company = remote.get("company")
	doc.tss_id = tss_id_clean
	doc.tss_status = provider_status
	doc.admin_puk = remote.get("admin_puk")
	doc.tss_serial_number = remote.get("serial_number")
	doc.activated_at = _to_datetime(remote.get("time_init"))
	doc.deactivated_at = _to_datetime(remote.get("time_disable"))

	# Skip default validate that would reset status to DRAFT
	doc.flags.ignore_validate = True
	try:
		doc.insert(ignore_permissions=True)
	except frappe.DuplicateEntryError:
		# Name collision (naming series) → load existing and update instead
		existing_name = (
			frappe.db.get_value("TSE Security Device", {"tss_id": tss_id_clean}, "name") or doc.name
		)
		existing_doc = frappe.get_doc("TSE Security Device", existing_name)
		_update_existing_from_remote(existing_doc, remote)
		return existing_doc

	# Ensure provider status persists after insert
	doc.db_set("tss_status", provider_status, update_modified=False)
	_normalize_datetime_fields(doc)
	_log_event(
		doc,
		status_before=None,
		status_after=provider_status,
		resp=remote,
		message=_("Created from provider during recovery sync."),
	)
	_normalize_datetime_fields(doc)
	doc.save(ignore_permissions=True)
	return doc


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


@frappe.whitelist()
def enqueue_recovery_sync() -> dict[str, Any]:
	"""Queue the recovery sync job from the list view button."""
	settings = frappe.get_single("TSE Settings")
	if not getattr(settings, "enabled", False):
		frappe.throw(_("TSE functionality is disabled in TSE Settings."))
	if not getattr(settings, "recovery_sync_enabled", False):
		frappe.throw(_("Recovery mode is disabled in TSE Settings."))

	job = frappe.enqueue(
		"erpnext_tse.erpnext_tse.doctype.tse_security_device.recovery.run_recovery_sync",
		queue="long",
		timeout=600,
		job_id="tse_recovery_sync",
		enqueue_after_commit=True,
		now=frappe.flags.in_test,
		user=frappe.session.user,
	)

	job_id = getattr(job, "id", None) or getattr(job, "name", None)
	return {"job_id": job_id}


def run_recovery_sync(user: str | None = None, **kwargs):
	"""Worker that pulls TSS data from Fiskaly and reconciles local records."""
	try:
		settings = frappe.get_single("TSE Settings")
		if not getattr(settings, "enabled", False):
			return
		if not getattr(settings, "recovery_sync_enabled", False):
			return

		provider = get_tse_provider(settings)
		remote_items = _extract_remote_list(provider.list_tss())

		remote_by_id: dict[str, dict[str, Any]] = {}
		for item in remote_items:
			rid = _get_remote_id(item)
			if rid:
				remote_by_id[_canonical_id(rid)] = item

		existing = frappe.get_all(
			"TSE Security Device",
			fields=["name", "tss_id", "tss_status"],
		)

		missing_puk_devices: list[dict[str, Any]] = []

		for row in existing:
			if not row.tss_id:
				continue

			remote = remote_by_id.pop(_canonical_id(row.tss_id), None)
			doc = frappe.get_doc("TSE Security Device", row.name)

			if not remote:
				if doc.tss_status != "ORPHANED":
					status_before = doc.tss_status
					doc.tss_status = "ORPHANED"
					_log_event(
						doc,
						status_before=status_before,
						status_after=doc.tss_status,
						resp={"error": {"message": "TSS missing at provider"}},
						message=_("Marked as ORPHANED because TSS was not found at provider."),
					)
					_normalize_datetime_fields(doc)
					doc.save(ignore_permissions=True)
				continue

			_update_existing_from_remote(doc, remote)

			if doc.tss_status in (
				"CREATED",
				"UNINITIALIZED",
				"INITIALIZED",
				"DISABLED",
			) and not doc.get_password("admin_puk", raise_exception=False):
				missing_puk_devices.append(
					{"name": doc.name, "tss_id": doc.tss_id, "tss_status": doc.tss_status}
				)

		# Create remaining provider TSS locally
		for remote in remote_by_id.values():
			try:
				created_doc = _create_missing_from_remote(remote)
				if created_doc.tss_status in (
					"CREATED",
					"UNINITIALIZED",
					"INITIALIZED",
					"DISABLED",
				) and not created_doc.get_password("admin_puk", raise_exception=False):
					missing_puk_devices.append(
						{
							"name": created_doc.name,
							"tss_id": created_doc.tss_id,
							"tss_status": created_doc.tss_status,
						}
					)
			except frappe.DuplicateEntryError:
				# already exists; skip
				continue

		frappe.db.commit()
		if user:
			publish_realtime(
				"tse_recovery_done",
				{
					"message": _("Recovery sync completed successfully."),
					"missing_puk": missing_puk_devices,
				},
				user=user,
			)
	except Exception:
		frappe.db.rollback()
		# Ensure failures appear in the background job log
		frappe.log_error(frappe.get_traceback(), "TSE Recovery Sync failed")
		raise


@frappe.whitelist()
def set_admin_puks(puks: list[dict[str, Any]] | None = None):
	"""Set admin PUKs for given TSE Security Devices after recovery."""
	if puks is None:
		puks = []

	if isinstance(puks, str):
		try:
			puks = frappe.parse_json(puks)
		except Exception:
			frappe.throw(_("Invalid payload for admin PUKs."))

	if not isinstance(puks, list):
		frappe.throw(_("Invalid payload for admin PUKs."))

	updated = 0
	for entry in puks:
		name = (entry or {}).get("name")
		puk = (entry or {}).get("admin_puk")
		if not name or not puk:
			continue
		doc = frappe.get_doc("TSE Security Device", name)
		doc.admin_puk = puk
		doc.save(ignore_permissions=True)
		updated += 1

	frappe.db.commit()
	return {"updated": updated}
