# Copyright (c) 2025, RocketQuackIT and contributors
# For license information, please see LICENSE

from datetime import datetime

import frappe
from erpnext import __version__ as erpnext_version
from frappe import _
from frappe.model.document import Document

from erpnext_tse.erpnext_tse.tss_providers import get_tse_provider


class TSEClient(Document):
	# ---------- Basis / Validierung ----------

	def validate(self):
		"""Nur erlauben, wenn TSE-Funktionalität aktiviert ist.
		Setzt außerdem Default-Status für neue Devices.
		"""
		self.ensure_tse_enabled()
		if self.is_new():
			self.status = "DRAFT"

		# Sicherstellen, dass nur INITIALIZED-TSE verknüpft werden
		if self.tse_security_device:
			tss = frappe.get_doc("TSE Security Device", self.tse_security_device)
			if tss.tss_status != "INITIALIZED":
				frappe.throw(
					_(
						"Only TSE Security Devices with status 'INITIALIZED' "
						"can be linked to a TSE Client. Current status: {0}"
					).format(tss.tss_status)
				)

	def ensure_tse_enabled(self):
		settings = frappe.get_single("TSE Settings")
		if not getattr(settings, "enabled", None):
			frappe.throw(
				_(
					"TSE functionality is not enabled in TSE Settings. "
					"Please enable it before creating a TSE Client."
				)
			)

	# ---------- Provider-Event-Historie ----------

	def log_provider_event(
		self,
		event_type: str,
		provider_action: str,
		resp: dict | None = None,
		status_before: str | None = None,
		status_after: str | None = None,
		message_summary: str | None = None,
	):
		"""Ein Event in die Child-Tabelle provider_events schreiben."""
		event = self.append("provider_events", {})
		event.event_time = frappe.utils.now_datetime()
		event.event_type = event_type
		event.provider_action = provider_action
		event.status_before = status_before
		event.status_after = status_after or self.tss_status
		event.message_summary = message_summary or ""

		if resp:
			event.http_status_code = resp.get("status_code")
			error = (resp or {}).get("error") or {}
			event.provider_error_code = error.get("code")
			event.provider_error_message = error.get("message")
			event.response_payload = frappe.as_json(resp, indent=2)
			event.request_id = resp.get("request_id")

		event.triggered_by = frappe.session.user

	# ---------- Aktion: Client beim Provider anlegen ----------

	@frappe.whitelist()
	def create_client_at_provider(self):
		"""
		TSE Client anlegen
		Nur erlaubt im Status 'DRAFT' && Benötigt eine verknüpfte TSE Security Device mit tss_id
		"""
		self.ensure_tse_enabled()

		if not self.tse_security_device:
			frappe.throw(_("Please select a TSE Security Device first."))

		if self.client_status != "DRAFT":
			frappe.throw(
				_(
					"Client can only be created at provider when status is 'DRAFT'. " "Current status: {0}"
				).format(self.status)
			)

		if self.client_id:
			frappe.throw(_("This TSE Client already has a client_id ({0}).").format(self.client_id))

		# Zugehörige TSS laden
		tss = frappe.get_doc("TSE Security Device", self.tse_security_device)

		if not tss.tss_id:
			frappe.throw(_("Selected TSE Security Device has no tss_id yet."))

		settings = frappe.get_single("TSE Settings")
		provider = get_tse_provider(settings)

		old_status = self.client_status

		try:
			# Fiskaly verlangt Administrator-Authentifizierung für Client-Operationen
			tss._ensure_admin_pin_and_auth(provider)

			resp = provider.create_client(
				tss_id=tss.tss_id,
				metadata={
					"company": self.company,
					"pos_profile": self.pos_profile,
					"tse_client_name": self.client_name,
					"tse_client_docname": self.name,
				},
			)

		except Exception as e:
			self.status = "ERROR"
			self.log_provider_event(
				event_type="CREATE_CLIENT_FAILED",
				provider_action="create_client",
				resp={"error": {"message": str(e)}},
				status_before=old_status,
				status_after=self.client_status,
				message_summary=_("Error while creating client at provider for TSE Client {0}").format(
					self.name
				),
			)

			self.save(ignore_permissions=True)
			frappe.db.commit()
			raise

		# Erfolgreich angelegt → REGISTERED
		self.client_id = resp.get("_id")
		self.client_status = resp.get("state")
		self.serial_number = resp.get("serial_number")

		self.log_provider_event(
			event_type="CREATE_CLIENT",
			provider_action="create_client",
			resp=resp,
			status_before=old_status,
			status_after=self.client_status,
			message_summary=_("Client {0} created at provider for TSS {1}").format(self.name, tss.name),
		)

		# Dokument speichern
		self.save(ignore_permissions=True)

		# DSFinV-K Cash Register automatisch anlegen
		_sync_dsfinvk_cash_register(self, tss, provider)

		frappe.db.commit()

	@frappe.whitelist()
	def deregister_client_at_provider(self):
		"""
		TSE Client wird auf den Status "DEREGISTERED" gesetzt somit für die Verwendung der TSS blockiert
		Nur erlaubt im Status 'REGISTERED' && Benötigt eine verknüpfte TSE Security Device mit tss_id sowie eine regestrierte client_id
		"""
		self.ensure_tse_enabled()

		if self.client_status != "REGISTERED":
			frappe.throw(
				_(
					"Client can only be deregistered at provider when status is 'REGISTERED'. "
					"Current status: {0}"
				).format(self.client_status)
			)

		# Zugehörige TSS laden
		tss = frappe.get_doc("TSE Security Device", self.tse_security_device)

		settings = frappe.get_single("TSE Settings")
		provider = get_tse_provider(settings)

		old_status = self.client_status

		try:
			resp = provider.deregister_client(tss_id=tss.tss_id, client_id=self.client_id)

		except Exception as e:
			self.status = "ERROR"
			self.log_provider_event(
				event_type="DEREGISTER_CLIENT_FAILED",
				provider_action="deregister_client",
				resp={"error": {"message": str(e)}},
				status_before=old_status,
				status_after=self.client_status,
				message_summary=_("Error while deregistering client at provider for TSE Client {0}").format(
					self.name
				),
			)

			self.save(ignore_permissions=True)
			frappe.db.commit()
			raise

		# Erfolgreich Client deregestriert → DEREGISTER
		self.client_status = resp.get("state")

		self.log_provider_event(
			event_type="DEREGISTER_CLIENT",
			provider_action="deregister_client",
			resp=resp,
			status_before=old_status,
			status_after=self.client_status,
			message_summary=_("Client {0} deregistered at provider for TSS {1}").format(self.name, tss.name),
		)

		# Dokument speichern
		self.save(ignore_permissions=True)
		frappe.db.commit()

	@frappe.whitelist()
	def register_client_at_provider(self):
		"""
		TSE Client wird auf den Status "REGISTERED" gesetzt somit für die Verwendung der TSS wieder verfügbar
		Nur erlaubt im Status 'DEREGISTERED' && Benötigt eine verknüpfte TSE Security Device mit tss_id sowie eine regestrierte client_id
		"""
		self.ensure_tse_enabled()

		if self.client_status != "DEREGISTERED":
			frappe.throw(
				_(
					"Client can only be registered at provider when status is 'DEREGISTERED'. "
					"Current status: {0}"
				).format(self.client_status)
			)

		# Zugehörige TSS laden
		tss = frappe.get_doc("TSE Security Device", self.tse_security_device)

		settings = frappe.get_single("TSE Settings")
		provider = get_tse_provider(settings)

		old_status = self.client_status

		try:
			resp = provider.register_client(tss_id=tss.tss_id, client_id=self.client_id)

		except Exception as e:
			self.status = "ERROR"
			self.log_provider_event(
				event_type="REGISTER_CLIENT_FAILED",
				provider_action="register_client",
				resp={"error": {"message": str(e)}},
				status_before=old_status,
				status_after=self.client_status,
				message_summary=_("Error while registering client at provider for TSE Client {0}").format(
					self.name
				),
			)

			self.save(ignore_permissions=True)
			frappe.db.commit()
			raise

		# Erfolgreich Client regestriert → REGISTER
		self.client_status = resp.get("state")

		self.log_provider_event(
			event_type="REGISTER_CLIENT",
			provider_action="register_client",
			resp=resp,
			status_before=old_status,
			status_after=self.client_status,
			message_summary=_("Client {0} registered at provider for TSS {1}").format(self.name, tss.name),
		)

		# Dokument speichern
		self.save(ignore_permissions=True)
		frappe.db.commit()


def _build_dsfinvk_cash_register_payload(client, tss):
	brand = "ERPNext"
	model = client.pos_profile or client.client_name or client.name
	software = {
		"brand": "ERPNext",
		"version": erpnext_version,
	}
	base_currency = (
		frappe.db.get_value("Company", client.company, "default_currency") if client.company else None
	)
	if not base_currency:
		raise ValueError("Missing default currency for company.")

	metadata = {
		"company": client.company,
		"pos_profile": client.pos_profile,
		"tse_client": client.name,
		"tse_client_name": client.client_name,
	}
	metadata = {k: str(v) for k, v in metadata.items() if v}

	payload = {
		"cash_register_type": {
			"type": "MASTER",
			"tss_id": tss.tss_id,
		},
		"brand": brand,
		"model": model,
		"base_currency_code": base_currency,
		"software": software,
		"metadata": metadata,
	}

	return payload, metadata


def _get_or_create_dsfinvk_cash_register(client):
	name = frappe.db.get_value(
		"DSFinV-K Cash Register",
		{"tse_client": client.name},
		"name",
	)
	if name:
		return frappe.get_doc("DSFinV-K Cash Register", name)

	doc = frappe.new_doc("DSFinV-K Cash Register")
	doc.tse_client = client.name
	doc.pos_profile = client.pos_profile
	doc.company = client.company
	doc.status = "DRAFT"
	return doc


def _to_datetime(value):
	if value is None:
		return None
	try:
		if isinstance(value, int | float):
			return datetime.fromtimestamp(value)
		return frappe.utils.get_datetime(value)
	except Exception:
		return None


def _apply_dsfinvk_payload(doc, payload, metadata):
	doc.cash_register_type = payload.get("cash_register_type", {}).get("type")
	doc.tss_id = payload.get("cash_register_type", {}).get("tss_id")
	doc.brand = payload.get("brand")
	doc.model = payload.get("model")
	doc.base_currency_code = payload.get("base_currency_code")
	software = payload.get("software") or {}
	doc.software_brand = software.get("brand")
	doc.software_version = software.get("version")
	if metadata:
		doc.metadata_json = frappe.as_json(metadata, indent=2)


def _apply_dsfinvk_response(doc, payload, metadata, resp):
	doc.cash_register_id = resp.get("client_id") or doc.cash_register_id
	doc.cash_register_type = resp.get("cash_register_type") or payload.get("cash_register_type", {}).get(
		"type"
	)
	doc.tss_id = resp.get("tss_id") or payload.get("cash_register_type", {}).get("tss_id")
	doc.brand = resp.get("brand") or payload.get("brand")
	doc.model = resp.get("model") or payload.get("model")
	doc.base_currency_code = resp.get("base_currency_code") or payload.get("base_currency_code")
	software = resp.get("software") or payload.get("software") or {}
	doc.software_brand = software.get("brand")
	doc.software_version = software.get("version")
	doc.revision = resp.get("revision")
	doc.time_creation = _to_datetime(resp.get("time_creation"))
	doc.time_update = _to_datetime(resp.get("time_update"))
	metadata_value = resp.get("metadata") or metadata
	if metadata_value is not None:
		doc.metadata_json = frappe.as_json(metadata_value, indent=2)


def _sync_dsfinvk_cash_register(client, tss, provider):
	if not client.client_id:
		return

	doc = _get_or_create_dsfinvk_cash_register(client)
	doc.cash_register_id = client.client_id
	doc.pos_profile = client.pos_profile
	doc.company = client.company
	doc.tss_id = tss.tss_id
	doc.cash_register_type = "MASTER"
	status_before = doc.status
	payload = None
	metadata = None

	try:
		payload, metadata = _build_dsfinvk_cash_register_payload(client, tss)
		_apply_dsfinvk_payload(doc, payload, metadata)
		resp = provider.create_cash_register(payload, cash_register_id=client.client_id)
		_apply_dsfinvk_response(doc, payload, metadata, resp)
		doc.status = "ACTIVE"
		doc.log_provider_event(
			event_type="UPSERT_CASH_REGISTER",
			provider_action="upsert_cash_register",
			resp=resp,
			status_before=status_before,
			status_after=doc.status,
			message_summary="Cash Register upserted at provider",
		)
		if doc.is_new():
			doc.insert(ignore_permissions=True)
		else:
			doc.save(ignore_permissions=True)
	except Exception as exc:
		if payload:
			_apply_dsfinvk_payload(doc, payload, metadata or {})
		doc.status = "ERROR"
		doc.log_provider_event(
			event_type="UPSERT_CASH_REGISTER_FAILED",
			provider_action="upsert_cash_register",
			resp={"error": {"message": str(exc)}},
			status_before=status_before,
			status_after=doc.status,
			message_summary="Cash Register upsert failed",
		)
		if doc.is_new():
			doc.insert(ignore_permissions=True)
		else:
			doc.save(ignore_permissions=True)
		frappe.log_error(frappe.get_traceback(), _("DSFinV-K Cash Register sync failed"))
		frappe.msgprint(
			_("DSFinV-K Cash Register sync failed. Please review the DSFinV-K Cash Register record."),
			indicator="orange",
		)
