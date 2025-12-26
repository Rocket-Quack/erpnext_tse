# Copyright (c) 2025, RocketQuackIT and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class DSFinVKCashRegister(Document):
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
