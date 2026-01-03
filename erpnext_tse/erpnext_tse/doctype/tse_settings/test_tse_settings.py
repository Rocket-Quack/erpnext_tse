# Copyright (c) 2025, RocketQuackIT and Contributors
# See license.txt

from unittest.mock import Mock, patch

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext_tse.erpnext_tse.doctype.tse_settings import tse_settings


class TestTSESettings(FrappeTestCase):
	def setUp(self):
		self.settings = frappe.get_single("TSE Settings")
		self._original = {
			"enabled": self.settings.enabled,
			"tse_provider": self.settings.tse_provider,
			"tse_disable_acknowledged": getattr(self.settings, "tse_disable_acknowledged", 0),
		}

	def tearDown(self):
		frappe.db.set_single_value("TSE Settings", self._original, update_modified=False)

	def test_validate_requires_provider_when_enabled(self):
		self.settings.enabled = 1
		self.settings.tse_provider = ""
		with self.assertRaises(frappe.ValidationError):
			self.settings.validate()

	def test_get_provider_name_requires_value(self):
		self.settings.tse_provider = ""
		with self.assertRaises(frappe.ValidationError):
			self.settings.get_provider_name()

	def test_get_provider_name_normalizes(self):
		self.settings.tse_provider = " Fiskaly "
		self.assertEqual(self.settings.get_provider_name(), "fiskaly")

	def test_test_tse_auth_success(self):
		self.settings.enabled = 1
		self.settings.tse_provider = self.settings.tse_provider or "Fiskaly"
		self.settings.save(ignore_permissions=True)

		provider = Mock()
		provider.test_auth.return_value = {
			"status": "OK",
			"environment": "test",
			"organization_id": "org",
			"access_token_expires_at": 123,
		}

		with patch.object(tse_settings.TSESettings, "get_provider", return_value=provider):
			result = tse_settings.test_tse_auth()

		self.assertTrue(result["success"])
		self.assertEqual(result["status"], "OK")
		self.assertEqual(result["environment"], "test")
		self.assertEqual(result["organization_id"], "org")

	def test_test_tse_auth_disabled_raises(self):
		self.settings.enabled = 0
		self.settings.save(ignore_permissions=True)

		with self.assertRaises(frappe.ValidationError):
			tse_settings.test_tse_auth()

	def test_test_tse_auth_handles_validation_error(self):
		self.settings.enabled = 1
		self.settings.tse_provider = self.settings.tse_provider or "Fiskaly"
		self.settings.save(ignore_permissions=True)

		class ErrorProvider:
			def test_auth(self):
				raise frappe.ValidationError("bad")

		with patch.object(tse_settings.TSESettings, "get_provider", return_value=ErrorProvider()):
			result = tse_settings.test_tse_auth()

		self.assertFalse(result["success"])
		self.assertEqual(result["error_type"], "ValidationError")
		self.assertIn("bad", result["error_message"])

	def test_test_tse_auth_handles_unexpected_error(self):
		self.settings.enabled = 1
		self.settings.tse_provider = self.settings.tse_provider or "Fiskaly"
		self.settings.save(ignore_permissions=True)

		class ErrorProvider:
			def test_auth(self):
				raise Exception("boom")

		with patch.object(tse_settings.TSESettings, "get_provider", return_value=ErrorProvider()):
			result = tse_settings.test_tse_auth()

		self.assertFalse(result["success"])
		self.assertEqual(result["error_type"], "Error")
		self.assertEqual(result["error_message"], "Authentication failed. Please check your settings.")

	def test_validate_requires_disable_ack_when_disabling(self):
		self.settings.enabled = 1
		self.settings.tse_provider = self.settings.tse_provider or "Fiskaly"
		self.settings.tse_disable_acknowledged = 0
		self.settings.save(ignore_permissions=True)

		disabled = frappe.get_single("TSE Settings")
		disabled.enabled = 0
		disabled.tse_disable_acknowledged = 0

		with self.assertRaises(frappe.ValidationError):
			disabled.validate()

	def test_validate_allows_disable_with_ack(self):
		self.settings.enabled = 1
		self.settings.tse_provider = self.settings.tse_provider or "Fiskaly"
		self.settings.tse_disable_acknowledged = 0
		self.settings.save(ignore_permissions=True)

		disabled = frappe.get_single("TSE Settings")
		disabled.enabled = 0
		disabled.tse_disable_acknowledged = 1

		disabled.validate()
