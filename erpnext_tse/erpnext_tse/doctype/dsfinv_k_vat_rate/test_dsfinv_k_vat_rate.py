# Copyright (c) 2025, RocketQuackIT and Contributors
# See license.txt

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase


class TestDSFinVKVATRate(FrappeTestCase):
	def test_validate_mismatched_company_throws(self):
		doc = frappe.new_doc("DSFinV-K VAT Rate")
		doc.company = "Company A"
		doc.account = "Account A"

		with patch("frappe.db.get_value", return_value="Other Co"):
			with self.assertRaises(frappe.ValidationError):
				doc.validate()

	def test_validate_allows_matching_company(self):
		doc = frappe.new_doc("DSFinV-K VAT Rate")
		doc.company = "Company A"
		doc.account = "Account A"

		with patch("frappe.db.get_value", return_value="Company A"):
			doc.validate()
