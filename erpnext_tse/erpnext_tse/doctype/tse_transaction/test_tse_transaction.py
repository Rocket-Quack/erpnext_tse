# Copyright (c) 2025, RocketQuackIT and Contributors
# See license.txt

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext_tse.erpnext_tse.doctype.tse_transaction import tse_transaction
from erpnext_tse.erpnext_tse.doctype.tse_transaction import recovery


class _FakeTxProvider:
	def __init__(self, pages):
		self.pages = pages
		self.calls = []

	def list_transactions(self, tss_id, **query_params):
		self.calls.append({"tss_id": tss_id, **query_params})
		limit = query_params.get("limit") or 100
		offset = query_params.get("offset") or 0
		page_index = offset // limit if limit else 0
		if page_index < len(self.pages):
			return self.pages[page_index]
		return []


class _FakeManageProvider:
	def __init__(self, *, remote_get, remote_cancel=None):
		self.remote_get = remote_get
		self.remote_cancel = remote_cancel or remote_get

	def get_transaction(self, tss_id, tx_id):
		return dict(self.remote_get)

	def cancel_transaction(self, **kwargs):
		return dict(self.remote_cancel)


class TestTSETransactionRecoveryHelpers(FrappeTestCase):
	def test_normalize_status(self):
		self.assertEqual(recovery._normalize_status("finished"), "FINISHED")
		self.assertEqual(recovery._normalize_status("canceled"), "CANCELLED")
		self.assertEqual(recovery._normalize_status("unknown"), "ERROR")
		self.assertIsNone(recovery._normalize_status(None))

	def test_get_remote_ids(self):
		item = {"transaction_id": "Tx-1", "client_id": "Client-1"}
		self.assertEqual(recovery._get_remote_id(item), "tx-1")
		self.assertEqual(recovery._get_remote_client_id(item), "client-1")

	def test_extract_remote_list_variants(self):
		raw_list = [{"id": "x"}]
		self.assertEqual(recovery._extract_remote_list(raw_list), raw_list)

		raw_data = {"data": [{"id": "y"}]}
		self.assertEqual(recovery._extract_remote_list(raw_data), raw_data["data"])

		raw_single = {"id": "z"}
		self.assertEqual(recovery._extract_remote_list(raw_single), [raw_single])

		with self.assertRaises(frappe.ValidationError):
			recovery._extract_remote_list("invalid")

	def test_normalize_tx_type(self):
		self.assertEqual(recovery._normalize_tx_type({"transaction_type": "SALE"}, None), "SALE")

		schema = {"standard_v1": {"receipt": {"receipt_type": "RECEIPT"}}}
		self.assertEqual(recovery._normalize_tx_type({}, schema), "RECEIPT")

		self.assertEqual(recovery._normalize_tx_type({}, None), "UNKNOWN")

	def test_receipt_type_extract(self):
		schema = {"standard_v1": {"receipt": {"receipt_type": "BILL"}}}
		self.assertEqual(recovery._extract_receipt_type(schema), "BILL")

		self.assertIsNone(recovery._extract_receipt_type(None))

	def test_to_datetime(self):
		self.assertIsNotNone(recovery._to_datetime(1710000000))
		self.assertIsNotNone(recovery._to_datetime("1710000000"))
		self.assertIsNone(recovery._to_datetime("not-a-date"))

	def test_fetch_remote_transactions_paginates_and_dedupes(self):
		pages = [
			[{"_id": "tx-1"}, {"_id": "tx-2"}],
			[{"_id": "tx-2"}, {"_id": "tx-3"}],
		]
		provider = _FakeTxProvider(pages)

		items = recovery._fetch_remote_transactions(
			provider,
			tss_id="tss-1",
			tss_docname="TSS-1",
			tss_company="My Company",
			page_size=2,
		)

		ids = [recovery._get_remote_id(item) for item in items]
		self.assertEqual(ids, ["tx-1", "tx-2", "tx-3"])
		for item in items:
			self.assertEqual(item["__tss_docname"], "TSS-1")
			self.assertEqual(item["__tss_company"], "My Company")

		offsets = [call["offset"] for call in provider.calls]
		self.assertIn(offsets, ([0, 2], [0, 2, 4]))
		self.assertTrue(all(call["limit"] == 2 for call in provider.calls))
		self.assertTrue(all(call["order_by"] == recovery.RECOVERY_ORDER_BY for call in provider.calls))
		self.assertTrue(all(call["order"] == recovery.RECOVERY_ORDER for call in provider.calls))


class TestTSETransactionManagementHelpers(FrappeTestCase):
	def _create_transaction_doc(self, **overrides):
		doc = frappe.new_doc("TSE Transaction")
		doc.tse_security_device = overrides.get("tse_security_device", "DEVICE-TEST")
		doc.tse_client = overrides.get("tse_client", "CLIENT-TEST")
		doc.company = overrides.get("company", "My Company")
		doc.pos_invoice = overrides.get("pos_invoice")
		doc.transaction_type = overrides.get("transaction_type", "SALE")
		doc.transaction_id = overrides.get("transaction_id", "tx-1")
		doc.transaction_revision = overrides.get("transaction_revision", 1)
		doc.transaction_status = overrides.get("transaction_status", "ACTIVE")
		doc.flags.ignore_validate = True
		doc.flags.ignore_links = True
		doc.insert(ignore_permissions=True)
		return doc

	def test_refresh_tse_transaction_status_marks_finished(self):
		doc = self._create_transaction_doc()
		provider = _FakeManageProvider(
			remote_get={
				"_id": "tx-1",
				"state": "FINISHED",
				"revision": 2,
				"time_start": 1710000000,
				"time_end": 1710000060,
				"number": 7,
			}
		)

		with patch(
			"erpnext_tse.erpnext_tse.doctype.tse_transaction.tse_transaction._get_transaction_provider_context",
			return_value=(provider, "tss-1", "client-1"),
		):
			result = tse_transaction.refresh_tse_transaction_status(doc.name)

		self.assertEqual(result["transaction_status"], "FINISHED")
		reloaded = frappe.get_doc("TSE Transaction", doc.name)
		self.assertEqual(reloaded.transaction_status, "FINISHED")
		self.assertEqual(reloaded.docstatus, 1)

	def test_resolve_active_tse_transaction_cancels_and_unlinks(self):
		doc = self._create_transaction_doc(pos_invoice="POS-INV-1")
		provider = _FakeManageProvider(
			remote_get={"_id": "tx-1", "state": "ACTIVE", "revision": 1},
			remote_cancel={"_id": "tx-1", "state": "CANCELLED", "revision": 2, "time_end": 1710000060},
		)

		with patch(
			"erpnext_tse.erpnext_tse.doctype.tse_transaction.tse_transaction._get_transaction_provider_context",
			return_value=(provider, "tss-1", "client-1"),
		), patch(
			"erpnext_tse.erpnext_tse.doctype.tse_transaction.tse_transaction._get_linked_pos_invoice_docstatus",
			return_value=0,
		), patch(
			"erpnext_tse.erpnext_tse.doctype.tse_transaction.tse_transaction._unlink_pos_invoice_tse_transaction"
		) as unlink:
			result = tse_transaction.resolve_active_tse_transaction(doc.name)

		self.assertEqual(result["transaction_status"], "CANCELLED")
		reloaded = frappe.get_doc("TSE Transaction", doc.name)
		self.assertEqual(reloaded.transaction_status, "CANCELLED")
		self.assertEqual(reloaded.docstatus, 1)
		unlink.assert_called_once_with("POS-INV-1", doc.name)

	def test_resolve_active_tse_transaction_rejects_submitted_invoice(self):
		doc = self._create_transaction_doc(pos_invoice="POS-INV-2")
		provider = _FakeManageProvider(remote_get={"_id": "tx-1", "state": "ACTIVE", "revision": 1})

		with patch(
			"erpnext_tse.erpnext_tse.doctype.tse_transaction.tse_transaction._get_transaction_provider_context",
			return_value=(provider, "tss-1", "client-1"),
		), patch(
			"erpnext_tse.erpnext_tse.doctype.tse_transaction.tse_transaction._get_linked_pos_invoice_docstatus",
			return_value=1,
		):
			with self.assertRaises(frappe.ValidationError):
				tse_transaction.resolve_active_tse_transaction(doc.name)
