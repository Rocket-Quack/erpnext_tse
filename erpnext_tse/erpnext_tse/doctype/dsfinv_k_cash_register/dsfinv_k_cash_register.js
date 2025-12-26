// Copyright (c) 2025, RocketQuackIT and contributors
// For license information, please see license.txt

frappe.ui.form.on("DSFinV-K Cash Register", {
	refresh(frm) {
		const grid = frm.fields_dict.provider_events && frm.fields_dict.provider_events.grid;
		if (grid) {
			grid.cannot_add_rows = true;
			grid.cannot_delete_rows = true;
			grid.only_sortable();
		}
	},
});
