# Copyright (c) 2025, RocketQuackIT and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext_tse.erpnext_tse.doctype.tse_transaction import recovery


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
