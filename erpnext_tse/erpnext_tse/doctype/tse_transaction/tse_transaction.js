// Copyright (c) 2025, RocketQuackIT and contributors
// For license information, please see license.txt

frappe.ui.form.on("TSE Transaction", {
	refresh(frm) {
		const canManage = ["System Manager", "TSE Admin"].some((role) =>
			(frappe.user_roles || []).includes(role)
		);
		if (frm.is_new() || !canManage || !frm.doc.transaction_id) {
			return;
		}

		frm.add_custom_button(__("Refresh Status"), () => {
			frappe
				.call({
					method: "erpnext_tse.erpnext_tse.doctype.tse_transaction.tse_transaction.refresh_tse_transaction_status",
					args: { name: frm.doc.name },
					freeze: true,
					freeze_message: __("Refreshing TSE transaction status..."),
				})
				.then(() => frm.reload_doc());
		});

		if (frm.doc.transaction_status === "ACTIVE") {
			frm.add_custom_button(__("Resolve ACTIVE"), () => {
				frappe.confirm(
					__(
						"This will re-check the Fiskaly transaction and cancel it only if it is still ACTIVE and not linked to a submitted POS Invoice. Continue?"
					),
					() => {
						frappe
							.call({
								method: "erpnext_tse.erpnext_tse.doctype.tse_transaction.tse_transaction.resolve_active_tse_transaction",
								args: { name: frm.doc.name },
								freeze: true,
								freeze_message: __("Resolving ACTIVE TSE transaction..."),
							})
							.then(() => frm.reload_doc());
					}
				);
			});
		}
	},
});
