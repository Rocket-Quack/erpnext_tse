// Copyright (c) 2025, RocketQuackIT and contributors
// For license information, please see license.txt

frappe.ui.form.on("DSFinV-K Export", {
	refresh(frm) {
		const grid = frm.fields_dict.provider_events && frm.fields_dict.provider_events.grid;
		if (grid) {
			grid.cannot_add_rows = true;
			grid.cannot_delete_rows = true;
			grid.only_sortable();
		}

		if (!frm.doc.export_id) {
			frm.add_custom_button(__("Trigger Export"), () => {
				frappe
					.call({
						method: "erpnext_tse.erpnext_tse.doctype.dsfinv_k_export.dsfinv_k_export.trigger_export",
						args: { name: frm.doc.name },
						freeze: true,
						freeze_message: __("Triggering export..."),
					})
					.then(() => frm.reload_doc());
			});
			return;
		}

		if (["PENDING", "WORKING"].includes(frm.doc.status)) {
			frm.add_custom_button(__("Refresh Status"), () => {
				frappe
					.call({
						method: "erpnext_tse.erpnext_tse.doctype.dsfinv_k_export.dsfinv_k_export.refresh_export_status",
						args: { name: frm.doc.name },
						freeze: true,
						freeze_message: __("Refreshing export status..."),
					})
					.then(() => frm.reload_doc());
			});
		}

		if (frm.doc.status === "COMPLETED") {
			frm.add_custom_button(__("Download Export"), () => {
				frappe
					.call({
						method: "erpnext_tse.erpnext_tse.doctype.dsfinv_k_export.dsfinv_k_export.download_export",
						args: { name: frm.doc.name },
						freeze: true,
						freeze_message: __("Downloading export..."),
					})
					.then((r) => {
						if (r && r.message) {
							window.open(r.message);
						}
						frm.reload_doc();
					});
			});
		}
	},
});
