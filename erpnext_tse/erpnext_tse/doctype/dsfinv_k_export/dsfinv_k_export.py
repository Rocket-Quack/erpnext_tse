# Copyright (c) 2025, RocketQuackIT and contributors
# For license information, please see license.txt

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

import frappe
from frappe import _
from frappe.model.document import Document

from erpnext_tse.erpnext_tse.tss_providers import get_tse_provider


def _is_tse_enabled() -> bool:
	return bool(frappe.db.get_single_value("TSE Settings", "enabled"))


class DSFinVKExport(Document):
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


@frappe.whitelist()
def trigger_export(name: str):
	if not _is_tse_enabled():
		frappe.throw(_("TSE integration is disabled. Please enable it in TSE Settings."))

	doc = frappe.get_doc("DSFinV-K Export", name)
	if doc.export_id:
		frappe.throw(_("Export has already been triggered."))

	payload, export_id = _build_export_payload(doc)
	status_before = doc.status or "DRAFT"
	doc.export_id = export_id
	doc.request_payload = frappe.as_json(payload, indent=2)
	doc.status = "PENDING"

	settings = frappe.get_single("TSE Settings")
	provider = get_tse_provider(settings)

	try:
		resp = provider.create_dsfinvk_export(**payload)
		_apply_export_response(doc, resp)
		doc.log_provider_event(
			event_type="CREATE",
			provider_action="create_dsfinvk_export",
			resp=resp,
			status_before=status_before,
			status_after=doc.status,
			message_summary="Export triggered at provider",
		)
		doc.flags.ignore_permissions = True
		doc.save()
		if doc.status in ("PENDING", "WORKING"):
			enqueue_export_status_refresh(doc.name)
	except Exception as exc:
		doc.status = "ERROR"
		doc.log_provider_event(
			event_type="ERROR",
			provider_action="create_dsfinvk_export",
			resp={"error": {"message": str(exc)}},
			status_before=status_before,
			status_after=doc.status,
			message_summary="Export trigger failed",
		)
		doc.flags.ignore_permissions = True
		doc.save()
		frappe.log_error(frappe.get_traceback(), _("DSFinV-K Export trigger failed"))
		frappe.throw(_("DSFinV-K Export trigger failed."))


@frappe.whitelist()
def refresh_export_status(name: str):
	doc = frappe.get_doc("DSFinV-K Export", name)
	_refresh_export_status_doc(doc)


@frappe.whitelist()
def download_export(name: str):
	if not _is_tse_enabled():
		frappe.throw(_("TSE integration is disabled. Please enable it in TSE Settings."))

	doc = frappe.get_doc("DSFinV-K Export", name)
	if not doc.export_id:
		frappe.throw(_("Export has not been triggered yet."))

	if doc.status != "COMPLETED":
		frappe.throw(_("Export is not completed yet."))

	settings = frappe.get_single("TSE Settings")
	provider = get_tse_provider(settings)

	resp = provider.download_dsfinvk_export(doc.export_id)
	ext = "zip" if (doc.format or "").lower() == "zip" else "tar"
	filename = f"dsfinvk-export-{doc.export_id}.{ext}"

	_file = frappe.get_doc(
		{
			"doctype": "File",
			"file_name": filename,
			"attached_to_doctype": doc.doctype,
			"attached_to_name": doc.name,
			"content": resp,
			"is_private": 1,
		}
	)
	_file.save(ignore_permissions=True)

	doc.export_file = _file.file_url
	doc.file_downloaded_at = frappe.utils.now_datetime()
	doc.flags.ignore_permissions = True
	doc.save()
	return doc.export_file


def _build_export_payload(doc: Document) -> tuple[dict[str, Any], str]:
	export_id = str(uuid4())

	client_id = None
	if doc.dsfinv_k_cash_register:
		reg = frappe.get_doc("DSFinV-K Cash Register", doc.dsfinv_k_cash_register)
		client_id = reg.cash_register_id
		if not client_id and reg.tse_client:
			client_id = frappe.db.get_value("TSE Client", reg.tse_client, "client_id")
		doc.company = reg.company
		doc.client_id = client_id or doc.client_id

	by_creation_date = None
	by_business_date = None

	if doc.filter_type == "Business Date":
		if not doc.business_date_start or not doc.business_date_end:
			frappe.throw(_("Business date start/end is required."))
		by_business_date = {
			"by_business_date": {
				"business_date_start": _to_date_string(doc.business_date_start),
				"business_date_end": _to_date_string(doc.business_date_end),
			}
		}
	else:
		if not doc.creation_date_start or not doc.creation_date_end:
			frappe.throw(_("Creation date start/end is required."))
		by_creation_date = {
			"by_creation_date": {
				"start_date": _to_unix(doc.creation_date_start),
				"end_date": _to_unix(doc.creation_date_end),
			}
		}

	payload = {
		"export_id": export_id,
		"by_creation_date": by_creation_date.get("by_creation_date") if by_creation_date else None,
		"by_business_date": by_business_date.get("by_business_date") if by_business_date else None,
		"client_id": client_id,
		"archive_format": doc.format,
	}
	payload = {k: v for k, v in payload.items() if v}

	return payload, export_id


def _apply_export_response(doc: Document, resp: dict[str, Any]):
	doc.status = resp.get("state") or doc.status
	doc.time_request = _to_datetime(resp.get("time_request"))
	doc.time_start = _to_datetime(resp.get("time_start"))
	doc.time_completed = _to_datetime(resp.get("time_completed"))
	doc.time_expiration = _to_datetime(resp.get("time_expiration"))
	doc.time_error = _to_datetime(resp.get("time_error"))

	error = resp.get("error") or {}
	doc.error_code = error.get("code")
	doc.error_message = error.get("message")
	doc.response_payload = frappe.as_json(resp, indent=2)


def _refresh_export_status_doc(doc: Document):
	if not _is_tse_enabled():
		return

	if not doc.export_id:
		frappe.throw(_("Export has not been triggered yet."))

	if doc.status in ("COMPLETED", "CANCELLED", "EXPIRED", "DELETED", "ERROR"):
		return

	settings = frappe.get_single("TSE Settings")
	provider = get_tse_provider(settings)
	status_before = doc.status

	try:
		resp = provider.get_dsfinvk_export(doc.export_id)
		_apply_export_response(doc, resp)
		doc.log_provider_event(
			event_type="STATUS_REFRESH",
			provider_action="get_dsfinvk_export",
			resp=resp,
			status_before=status_before,
			status_after=doc.status,
			message_summary="Export status refreshed",
		)
		doc.flags.ignore_permissions = True
		doc.save()
	except Exception as exc:
		doc.log_provider_event(
			event_type="ERROR",
			provider_action="get_dsfinvk_export",
			status_before=status_before,
			status_after=doc.status,
			message_summary=str(exc),
		)
		doc.flags.ignore_permissions = True
		doc.save()
		frappe.log_error(frappe.get_traceback(), _("DSFinV-K Export status refresh failed"))


def enqueue_export_status_refresh(export_name: str):
	frappe.enqueue(
		"erpnext_tse.erpnext_tse.doctype.dsfinv_k_export.dsfinv_k_export.refresh_export_status",
		queue="short",
		job_id=f"dsfinvk_export_refresh:{export_name}",
		deduplicate=True,
		name=export_name,
		enqueue_after_commit=True,
	)


def refresh_pending_exports():
	if not _is_tse_enabled():
		return

	pending = frappe.get_all(
		"DSFinV-K Export",
		filters={
			"status": ["in", ["PENDING", "WORKING"]],
			"export_id": ["is", "set"],
		},
		fields=["name"],
		limit=50,
	)
	for row in pending:
		_refresh_export_status_doc(frappe.get_doc("DSFinV-K Export", row.name))


def cleanup_expired_export_files():
	if not _is_tse_enabled():
		return

	retention_days = frappe.db.get_single_value("TSE Settings", "dsfinvk_export_retention_days") or 0
	try:
		retention_days = int(retention_days)
	except Exception:
		retention_days = 0

	if retention_days <= 0:
		return

	cutoff = frappe.utils.add_days(frappe.utils.now_datetime(), -retention_days)
	exports = frappe.get_all(
		"DSFinV-K Export",
		filters={
			"export_file": ["is", "set"],
			"file_downloaded_at": ["<", cutoff],
		},
		fields=["name", "export_file"],
		limit=100,
	)

	for row in exports:
		file_doc = frappe.db.get_value("File", {"file_url": row.export_file}, "name")
		if file_doc:
			frappe.delete_doc("File", file_doc, ignore_permissions=True)
		frappe.db.set_value("DSFinV-K Export", row.name, "export_file", None)
		frappe.db.set_value("DSFinV-K Export", row.name, "file_downloaded_at", None)


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


def _to_date_string(value) -> str:
	if not value:
		return ""
	try:
		return frappe.utils.getdate(value).isoformat()
	except Exception:
		return str(value)
