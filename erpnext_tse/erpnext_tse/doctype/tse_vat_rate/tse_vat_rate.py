# Copyright (c) 2025, RocketQuackIT and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class TSEVATRate(Document):
	def validate(self):
		if not self.company or not self.account:
			return

		account_company = frappe.db.get_value("Account", self.account, "company")
		if account_company and account_company != self.company:
			frappe.throw(
				_("This account '{0}' belongs to '{1}', and not to '{2}'.").format(
					self.account, account_company, self.company
				)
			)
