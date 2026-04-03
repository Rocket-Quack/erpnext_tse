// Copyright (c) 2025, RocketQuackIT and contributors
// For license information, please see license.txt

frappe.ui.form.on("DSFinV-K Cash Point Closing", {
	refresh(frm) {
		const canCleanupCashPointClosing = ["System Manager", "TSE Admin"].some((role) =>
			(frappe.user_roles || []).includes(role)
		);
		const grid = frm.fields_dict.provider_events && frm.fields_dict.provider_events.grid;
		if (grid) {
			grid.cannot_add_rows = true;
			grid.cannot_delete_rows = true;
			grid.only_sortable();
		}

		if (frm.is_new()) {
			return;
		}

		if (["PENDING", "WORKING"].includes(frm.doc.status)) {
			frm.add_custom_button(__("Refresh Status"), () => {
				frappe
					.call({
						method: "erpnext_tse.erpnext_tse.doctype.dsfinv_k_cash_point_closing.dsfinv_k_cash_point_closing.refresh_cash_point_closing_status",
						args: { closing_name: frm.doc.name },
						freeze: true,
						freeze_message: __("Refreshing cash point closing status..."),
					})
					.then(() => frm.reload_doc());
			});
		}

		if (frm.doc.status === "ERROR" && canCleanupCashPointClosing) {
			frm.add_custom_button(__("Retry Create"), () => {
				frappe.confirm(
					__(
						"This queues a new create attempt for the linked POS Closing Entry. Continue?"
					),
					() => {
						frappe
							.call({
								method: "erpnext_tse.erpnext_tse.doctype.dsfinv_k_cash_point_closing.dsfinv_k_cash_point_closing.retry_cash_point_closing_create",
								args: { name: frm.doc.name },
								freeze: true,
								freeze_message: __("Queueing cash point closing retry..."),
							})
							.then(() => frm.reload_doc());
					}
				);
			});
		}

		if (frm.doc.status === "COMPLETED" && canCleanupCashPointClosing) {
			frm.add_custom_button(__("Mark as Deleted"), () => {
				frappe.prompt(
					[
						{
							fieldname: "cleanup_reason",
							fieldtype: "Small Text",
							label: __("Cleanup Reason"),
							reqd: 1,
						},
						{
							fieldname: "cleanup_valid_record",
							fieldtype: "Link",
							label: __("Valid Record"),
							options: "DSFinV-K Cash Point Closing",
						},
					],
					(values) => {
						frappe
							.call({
								method: "erpnext_tse.erpnext_tse.doctype.dsfinv_k_cash_point_closing.dsfinv_k_cash_point_closing.mark_cash_point_closing_as_deleted",
								args: {
									name: frm.doc.name,
									cleanup_reason: values.cleanup_reason,
									cleanup_valid_record: values.cleanup_valid_record,
								},
								freeze: true,
								freeze_message: __("Marking cash point closing as deleted..."),
							})
							.then(() => frm.reload_doc());
					},
					__("Mark as Deleted"),
					__("Apply")
				);
			});
		}
	},
});
