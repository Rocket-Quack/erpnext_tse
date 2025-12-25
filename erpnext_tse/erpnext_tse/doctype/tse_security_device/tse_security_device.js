// Copyright (c) 2025, RocketQuackIT and contributors
// For license information, please see LICENSE

// FORM SCRIPT (Buttons etc.)
frappe.ui.form.on("TSE Security Device", {
	refresh(frm) {
		// Provider Events Grid read-only machen
		const grid = frm.fields_dict.provider_events && frm.fields_dict.provider_events.grid;
		if (grid) {
			grid.cannot_add_rows = true;
			grid.cannot_delete_rows = true;
			grid.only_sortable();
		}

		// bei neuen (noch nicht gespeicherten) Docs keine Buttons
		if (frm.is_new()) {
			return;
		}

		const group = __("TSE Actions");

		// Helper für Doc-Method-Aufrufe über den neuen, vollqualifizierten Pfad
		function run_doc_method(method_name, freeze_message) {
			return frappe
				.call({
					method: "frappe.handler.run_doc_method",
					args: {
						docs: frm.doc, // komplettes Doc JSON
						method: method_name, // z.B. "create_tss_at_provider"
					},
					freeze: true,
					freeze_message: freeze_message,
				})
				.then((r) => {
					const msg = r && r.message;
					if (method_name === "create_tss_at_provider" && msg && msg.admin_puk) {
						const tssId = msg.tss_id || frm.doc.tss_id || __("unknown");
						const dialog = new frappe.ui.Dialog({
							title: __("TSS created"),
							fields: [
								{
									fieldtype: "HTML",
									fieldname: "info",
									options: `
                                    <p>${__(
										"Please store the following securely. They cannot be recovered later (even via recovery)."
									)}</p>
                                    <p><b>${__("Admin PUK")}:</b> <code>${msg.admin_puk}</code></p>
                                    <p><b>${__("TSS ID")}:</b> <code>${tssId}</code></p>
                                `,
								},
								{
									fieldtype: "Check",
									fieldname: "ack",
									label: __(
										"I confirm I have stored Admin PUK and TSS ID externally"
									),
								},
							],
							primary_action_label: __("Close"),
							primary_action: () => {
								if (!dialog.get_value("ack")) {
									frappe.msgprint({
										message: __(
											"Please confirm that you have stored Admin PUK and TSS ID."
										),
										indicator: "red",
									});
									return;
								}
								dialog.hide();
							},
						});
						// disable close until checkbox ticked
						const primaryBtn = dialog.get_primary_btn();
						if (primaryBtn) primaryBtn.prop("disabled", true);
						const closeBtn = dialog.get_close_btn && dialog.get_close_btn();
						if (closeBtn) closeBtn.hide();
						dialog.fields_dict.ack.df.onchange = () => {
							const checked = dialog.get_value("ack");
							if (primaryBtn) primaryBtn.prop("disabled", !checked);
						};
						dialog.show();
					}
					if (!r.exc) {
						frm.reload_doc();
					}
					return r;
				});
		}

		// 1) TSS beim Provider anlegen → nur in Status DRAFT
		if (frm.doc.tss_status === "DRAFT") {
			frm.add_custom_button(
				__("Create TSS at Provider"),
				() => {
					run_doc_method("create_tss_at_provider", __("Creating TSS at provider..."));
				},
				group
			);
		}

		// 2) TSS deployen → nur in Status CREATED + tss_id vorhanden
		if (frm.doc.tss_status === "CREATED" && frm.doc.tss_id) {
			frm.add_custom_button(
				__("Deploy TSS at Provider"),
				() => {
					run_doc_method("deploy_tss_at_provider", __("Deploying TSS at provider..."));
				},
				group
			);
		}

		// 3) TSS initialisieren → nur in Status UNINITIALIZED + tss_id vorhanden
		if (frm.doc.tss_status === "UNINITIALIZED" && frm.doc.tss_id) {
			frm.add_custom_button(
				__("Initialize TSS at Provider"),
				() => {
					run_doc_method(
						"initialize_tss_at_provider",
						__("Initializing TSS at provider...")
					);
				},
				group
			);
		}

		// 4) TSS deaktivieren → nur in Status INITIALIZED + tss_id vorhanden
		if (["UNINITIALIZED", "INITIALIZED"].includes(frm.doc.tss_status) && frm.doc.tss_id) {
			frm.add_custom_button(
				__("Disable TSS at Provider"),
				() => {
					run_doc_method("disable_tss_at_provider", __("Disabling TSS at provider..."));
				},
				group
			);
		}
	},
});
