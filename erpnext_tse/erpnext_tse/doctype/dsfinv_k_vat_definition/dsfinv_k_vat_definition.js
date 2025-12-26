// Copyright (c) 2025, RocketQuackIT and contributors
// For license information, please see license.txt

frappe.ui.form.on("DSFinV-K VAT Definition", {
	setup(frm) {
		frm.set_query("account", () => {
			return {
				filters: {
					account_type: "Tax",
					is_group: 0,
					disabled: 0,
					company: frm.doc.company,
				},
			};
		});
	},
});
