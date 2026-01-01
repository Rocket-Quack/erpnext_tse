# Copyright (c) 2025, RocketQuackIT and contributors
# For license information, please see LICENSE

from types import SimpleNamespace

from frappe.tests.utils import FrappeTestCase

from erpnext_tse.erpnext_tse.tss_providers import get_tse_provider
from erpnext_tse.erpnext_tse.tss_providers.fiskaly import FiskalyProvider


class TestTSEProviderFactory(FrappeTestCase):
	def test_get_tse_provider_aliases(self):
		for name in ("Fiskaly", "fiskaly", "Fiskaly (Cloud)", "fiskaly_sign_de"):
			provider = get_tse_provider(SimpleNamespace(tse_provider=name))
			self.assertIsInstance(provider, FiskalyProvider)

	def test_get_tse_provider_default(self):
		provider = get_tse_provider(SimpleNamespace())
		self.assertIsInstance(provider, FiskalyProvider)

	def test_get_tse_provider_unknown(self):
		with self.assertRaises(ValueError):
			get_tse_provider(SimpleNamespace(tse_provider="Other"))
