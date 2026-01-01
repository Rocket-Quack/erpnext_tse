# Copyright (c) 2025, RocketQuackIT and contributors
# For license information, please see LICENSE

from unittest.mock import patch

from frappe.tests.utils import FrappeTestCase

from erpnext_tse.erpnext_tse.utils import jinja_methods


class TestJinjaMethods(FrappeTestCase):
	def test_get_tse_qr_code_empty(self):
		self.assertEqual(jinja_methods.get_tse_qr_code(""), "")

	def test_get_tse_qr_code_bytes(self):
		with patch("frappe.twofactor.get_qr_svg_code", return_value=b"PHN2Zz4="):
			result = jinja_methods.get_tse_qr_code("payload")

		self.assertTrue(result.startswith("data:image/svg+xml;base64,"))
		self.assertIn("PHN2Zz4=", result)

	def test_get_tse_qr_code_string(self):
		with patch("frappe.twofactor.get_qr_svg_code", return_value="PHN2Zz4="):
			result = jinja_methods.get_tse_qr_code("payload")

		self.assertEqual(result, "data:image/svg+xml;base64,PHN2Zz4=")
