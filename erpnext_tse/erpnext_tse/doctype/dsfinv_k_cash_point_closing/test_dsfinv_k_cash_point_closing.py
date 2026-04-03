# Copyright (c) 2026, RocketQuackIT and Contributors
# See license.txt

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext_tse.erpnext_tse.doctype.dsfinv_k_cash_point_closing import dsfinv_k_cash_point_closing as cpc


class _FakeProvider:
	def get_cash_point_closing(self, closing_id):
		return {
			"closing_id": closing_id,
			"state": "COMPLETED",
			"time_creation": 1710000000,
		}

	def delete_cash_point_closing(self, closing_id):
		return {
			"closing_id": closing_id,
			"state": "DELETED",
			"time_deleted": 1710003600,
		}


class _FakePosClosingDoc:
	doctype = "POS Closing Entry"

	def __init__(self, *, name: str, docstatus: int, status: str):
		self.name = name
		self.docstatus = docstatus
		self.status = status


class TestDSFinVKCashPointClosingHelpers(FrappeTestCase):
	def setUp(self):
		settings = frappe.get_single("TSE Settings")
		settings.enabled = 1
		settings.tse_provider = "Fiskaly"
		settings.save(ignore_permissions=True)

	def _create_closing_doc(self, **overrides):
		doc = frappe.new_doc("DSFinV-K Cash Point Closing")
		doc.pos_closing_entry = overrides.get("pos_closing_entry", "POS-CLOSING-TEST")
		doc.dsfinv_k_cash_register = overrides.get("dsfinv_k_cash_register", "REGISTER-TEST")
		doc.status = overrides.get("status", "COMPLETED")
		doc.closing_id = overrides.get("closing_id", "closing-1")
		doc.client_id = overrides.get("client_id", "client-1")
		doc.business_date = overrides.get("business_date", "2026-04-02")
		doc.source_hash = overrides.get("source_hash", "hash-1")
		doc.flags.ignore_links = True
		doc.insert(ignore_permissions=True)
		return doc

	def test_should_enqueue_for_submitted_pos_closing(self):
		doc = _FakePosClosingDoc(name="PCE-1", docstatus=1, status="Submitted")
		self.assertTrue(cpc._should_enqueue_for_pos_closing(doc))

	def test_should_not_enqueue_for_failed_pos_closing(self):
		doc = _FakePosClosingDoc(name="PCE-2", docstatus=1, status="Failed")
		self.assertFalse(cpc._should_enqueue_for_pos_closing(doc))

	def test_enqueue_cash_point_closing_for_pos_closing_entry(self):
		doc = _FakePosClosingDoc(name="PCE-3", docstatus=1, status="Submitted")

		with patch("frappe.enqueue") as enqueue:
			cpc.enqueue_cash_point_closing_for_pos_closing_entry(doc)

		enqueue.assert_called_once()
		self.assertEqual(
			enqueue.call_args.kwargs["job_id"],
			"dsfinvk_cash_point_closing_create:PCE-3",
		)

	def test_build_source_hash_is_stable_for_invoice_order(self):
		doc_a = frappe._dict(
			company="My Company",
			pos_profile="POS-1",
			pos_transactions=[frappe._dict(pos_invoice="INV-2"), frappe._dict(pos_invoice="INV-1")],
		)
		doc_b = frappe._dict(
			company="My Company",
			pos_profile="POS-1",
			pos_transactions=[frappe._dict(pos_invoice="INV-1"), frappe._dict(pos_invoice="INV-2")],
		)
		self.assertEqual(
			cpc._build_source_hash(doc_a, "client-1", "2026-04-02"),
			cpc._build_source_hash(doc_b, "client-1", "2026-04-02"),
		)

	def test_mark_cash_point_closing_as_deleted(self):
		doc = self._create_closing_doc()
		provider = _FakeProvider()

		with patch(
			"erpnext_tse.erpnext_tse.doctype.dsfinv_k_cash_point_closing.dsfinv_k_cash_point_closing.get_tse_provider",
			return_value=provider,
		):
			result = cpc.mark_cash_point_closing_as_deleted(
				doc.name,
				"Duplicate cash closing after failed POS closing retry",
			)

		self.assertEqual(result["status"], "DELETED")
		reloaded = frappe.get_doc("DSFinV-K Cash Point Closing", doc.name)
		self.assertEqual(reloaded.status, "DELETED")
		self.assertEqual(reloaded.cleanup_reason, "Duplicate cash closing after failed POS closing retry")
		self.assertIsNotNone(reloaded.cleanup_performed_at)

	def test_cleanup_requires_completed_status(self):
		doc = self._create_closing_doc(status="ERROR", closing_id="closing-error")
		provider = _FakeProvider()

		with patch(
			"erpnext_tse.erpnext_tse.doctype.dsfinv_k_cash_point_closing.dsfinv_k_cash_point_closing.get_tse_provider",
			return_value=provider,
		):
			with self.assertRaises(frappe.ValidationError):
				cpc.mark_cash_point_closing_as_deleted(doc.name, "not allowed")
