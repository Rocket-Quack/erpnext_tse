# Copyright (c) 2025, RocketQuackIT and Contributors
# See license.txt

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext_tse.erpnext_tse.doctype.tse_security_device import recovery


class _FakeProvider:
	def __init__(self, items):
		self._items = items

	def list_tss(self):
		return self._items


class TestTSESecurityDeviceRecovery(FrappeTestCase):
	def setUp(self):
		settings = frappe.get_single("TSE Settings")
		settings.enabled = 1
		settings.recovery_sync_enabled = 1
		settings.tse_provider = "Fiskaly"
		settings.save(ignore_permissions=True)

		frappe.db.delete("TSE Security Device", {"tss_id": ["in", ["tss-1", "tss-2", "tss-missing"]]})
		frappe.db.commit()

	def _create_device(self, internal_name: str, tss_id: str, status: str):
		doc = frappe.new_doc("TSE Security Device")
		doc.internal_name = internal_name
		doc.tss_id = tss_id
		doc.tss_status = status
		doc.flags.ignore_validate = True
		doc.insert(ignore_permissions=True)
		return doc

	def test_recovery_sync_updates_creates_and_orphans(self):
		existing = self._create_device("Existing", "tss-1", "UNINITIALIZED")
		orphan = self._create_device("Orphan", "tss-missing", "INITIALIZED")

		remote_items = [
			{
				"id": "tss-1",
				"state": "INITIALIZED",
				"serial_number": "SER-1",
				"time_init": 1710000000,
				"admin_puk": "PUK-1",
			},
			{
				"id": "tss-2",
				"state": "CREATED",
				"serial_number": "SER-2",
				"description": "Recovered Device",
				"admin_puk": "PUK-2",
			},
		]

		provider = _FakeProvider(remote_items)

		with patch(
			"erpnext_tse.erpnext_tse.doctype.tse_security_device.recovery.get_tse_provider",
			return_value=provider,
		):
			recovery.run_recovery_sync()

		updated = frappe.get_doc("TSE Security Device", existing.name)
		self.assertEqual(updated.tss_status, "INITIALIZED")
		self.assertEqual(updated.tss_serial_number, "SER-1")
		self.assertIsNotNone(updated.activated_at)
		self.assertEqual(updated.get_password("admin_puk", raise_exception=False), "PUK-1")

		created_name = frappe.db.get_value("TSE Security Device", {"tss_id": "tss-2"}, "name")
		self.assertTrue(created_name)
		created = frappe.get_doc("TSE Security Device", created_name)
		self.assertEqual(created.tss_status, "CREATED")
		self.assertEqual(created.internal_name, "Recovered Device")
		self.assertEqual(created.get_password("admin_puk", raise_exception=False), "PUK-2")

		orphan_doc = frappe.get_doc("TSE Security Device", orphan.name)
		self.assertEqual(orphan_doc.tss_status, "ORPHANED")


class TestTSESecurityDeviceRecoveryHelpers(FrappeTestCase):
	def test_normalize_status(self):
		self.assertEqual(recovery._normalize_status("deleted"), "DISABLED")
		self.assertEqual(recovery._normalize_status("initialized"), "INITIALIZED")
		self.assertIsNone(recovery._normalize_status(None))

	def test_extract_remote_list_variants(self):
		raw = {"data": [{"id": "tss-1"}]}
		self.assertEqual(recovery._extract_remote_list(raw), raw["data"])

		raw_single = {"id": "tss-2"}
		self.assertEqual(recovery._extract_remote_list(raw_single), [raw_single])

		with self.assertRaises(frappe.ValidationError):
			recovery._extract_remote_list("invalid")

	def test_to_datetime(self):
		self.assertIsNotNone(recovery._to_datetime(1710000000))
		self.assertIsNotNone(recovery._to_datetime("1710000000"))
		self.assertIsNone(recovery._to_datetime("not-a-date"))
