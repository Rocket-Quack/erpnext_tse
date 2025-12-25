# Copyright (c) 2025, RocketQuackIT and Contributors
# See license.txt

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext_tse.erpnext_tse.doctype.tse_client import recovery


class _FakeProvider:
	def __init__(self, client_map):
		self._client_map = client_map

	def list_clients(self, tss_id):
		return self._client_map.get(tss_id, [])


class TestTSEClientRecovery(FrappeTestCase):
	def setUp(self):
		settings = frappe.get_single("TSE Settings")
		settings.enabled = 1
		settings.recovery_sync_enabled = 1
		settings.tse_provider = "Fiskaly"
		settings.save(ignore_permissions=True)

		frappe.db.delete(
			"TSE Client",
			{"client_id": ["in", ["client-1", "client-2", "client-missing"]]},
		)
		frappe.db.delete("TSE Security Device", {"tss_id": ["in", ["tss-1"]]})
		frappe.db.commit()

	def _create_security_device(self, tss_id, status="INITIALIZED"):
		doc = frappe.new_doc("TSE Security Device")
		doc.internal_name = f"Device {tss_id}"
		doc.tss_id = tss_id
		doc.tss_status = status
		doc.flags.ignore_validate = True
		doc.insert(ignore_permissions=True)
		return doc

	def _create_client(self, name, device_name, client_id, status):
		doc = frappe.new_doc("TSE Client")
		doc.client_name = name
		doc.tse_security_device = device_name
		doc.client_id = client_id
		doc.client_status = status
		doc.flags.ignore_validate = True
		doc.flags.ignore_mandatory = True
		doc.insert(ignore_permissions=True)
		return doc

	def test_recovery_sync_updates_creates_and_orphans(self):
		device = self._create_security_device("tss-1")
		existing = self._create_client("Local Client 1", device.name, "client-1", "DRAFT")
		orphan = self._create_client("Local Orphan", device.name, "client-missing", "REGISTERED")

		remote_map = {
			"tss-1": [
				{"_id": "client-1", "state": "REGISTERED", "serial_number": "SN-1"},
				{"_id": "client-2", "state": "DEREGISTERED", "serial_number": "SN-2"},
			]
		}
		provider = _FakeProvider(remote_map)

		with patch(
			"erpnext_tse.erpnext_tse.doctype.tse_client.recovery.get_tse_provider",
			return_value=provider,
		):
			recovery.run_recovery_sync()

		updated = frappe.get_doc("TSE Client", existing.name)
		self.assertEqual(updated.client_status, "REGISTERED")
		self.assertEqual(updated.serial_number, "SN-1")

		created_name = frappe.db.get_value("TSE Client", {"client_id": "client-2"}, "name")
		self.assertTrue(created_name)
		created = frappe.get_doc("TSE Client", created_name)
		self.assertEqual(created.client_status, "DEREGISTERED")
		self.assertEqual(created.tse_security_device, device.name)

		orphan_doc = frappe.get_doc("TSE Client", orphan.name)
		self.assertEqual(orphan_doc.client_status, "ORPHANED")
