# Copyright (c) 2025, RocketQuackIT and contributors
# For license information, please see LICENSE

from types import SimpleNamespace
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext_tse.erpnext_tse.pos.pos_invoice import pos_invoice_hooks


class TestPosInvoiceHooks(FrappeTestCase):
	def test_ensure_requires_transaction(self):
		doc = SimpleNamespace(tse_transaction=None)

		with patch("frappe.db.get_single_value", return_value=1):
			with self.assertRaises(frappe.MandatoryError):
				pos_invoice_hooks.ensure_tse_transaction_present_and_finished(doc, None)

	def test_ensure_requires_finished(self):
		doc = SimpleNamespace(tse_transaction="TX-1")

		with patch("frappe.db.get_single_value", return_value=1):
			with patch("frappe.get_doc", return_value=SimpleNamespace(transaction_status="ACTIVE")):
				with self.assertRaises(frappe.ValidationError):
					pos_invoice_hooks.ensure_tse_transaction_present_and_finished(doc, None)

	def test_ensure_passes_finished(self):
		doc = SimpleNamespace(tse_transaction="TX-1")

		with patch("frappe.db.get_single_value", return_value=1):
			with patch("frappe.get_doc", return_value=SimpleNamespace(transaction_status="FINISHED")):
				pos_invoice_hooks.ensure_tse_transaction_present_and_finished(doc, None)

	def test_show_toast_requires_transaction(self):
		doc = SimpleNamespace(tse_transaction=None)

		with patch("frappe.db.get_single_value", return_value=1):
			with self.assertRaises(frappe.ValidationError):
				pos_invoice_hooks.show_tse_signing_success_toast(doc)

	def test_show_toast_success(self):
		doc = SimpleNamespace(tse_transaction="TX-1")
		tse_doc = SimpleNamespace(name="TX-1", transaction_status="FINISHED")

		with patch("frappe.db.get_single_value", return_value=1):
			with patch("frappe.get_doc", return_value=tse_doc), patch("frappe.msgprint") as msgprint:
				pos_invoice_hooks.show_tse_signing_success_toast(doc)

		_, kwargs = msgprint.call_args
		self.assertEqual(kwargs.get("indicator"), "green")

	def test_show_toast_failure(self):
		doc = SimpleNamespace(tse_transaction="TX-1")
		tse_doc = SimpleNamespace(name="TX-1", transaction_status="ACTIVE")

		with patch("frappe.db.get_single_value", return_value=1):
			with patch("frappe.get_doc", return_value=tse_doc):
				with self.assertRaises(frappe.ValidationError):
					pos_invoice_hooks.show_tse_signing_success_toast(doc)

	def test_ensure_skips_when_disabled(self):
		doc = SimpleNamespace(tse_transaction=None)

		with patch("frappe.db.get_single_value", return_value=0):
			pos_invoice_hooks.ensure_tse_transaction_present_and_finished(doc, None)

	def test_show_toast_skips_when_disabled(self):
		doc = SimpleNamespace(tse_transaction=None)

		with patch("frappe.db.get_single_value", return_value=0):
			pos_invoice_hooks.show_tse_signing_success_toast(doc)
