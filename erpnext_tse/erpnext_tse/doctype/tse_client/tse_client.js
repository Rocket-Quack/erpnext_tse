// Copyright (c) 2025, RocketQuackIT and contributors
// For license information, please see license.txt

frappe.ui.form.on("TSE Client", {
	setup(frm) {
		// Nur INITIALIZED TSE Security Devices anzeigen
		frm.set_query("tse_security_device", () => {
			const filters = {
				tss_status: "INITIALIZED",
			};

			// Zusätzlich nach Company filtern, falls gesetzt
			if (frm.doc.company) {
				filters.company = frm.doc.company;
			}

			return { filters };
		});
	},

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

		const group = __("TSE Client");

		// Helper für Doc-Method-Aufrufe über den neuen, vollqualifizierten Pfad
		function run_doc_method(method_name, freeze_message) {
			return frappe
				.call({
					method: "frappe.handler.run_doc_method",
					args: {
						docs: frm.doc, // komplettes Doc JSON
						method: method_name, // z.B. "create_client_at_provider"
					},
					freeze: true,
					freeze_message: freeze_message,
				})
				.then((r) => {
					if (!r.exc) {
						frm.reload_doc();
					}
					return r;
				});
		}

		// 1) Client beim Provider anlegen → nur in Status DRAFT
		if (frm.doc.client_status === "DRAFT") {
			frm.add_custom_button(
				__("Create Client at Provider"),
				() => {
					run_doc_method(
						"create_client_at_provider",
						__("Creating Client at provider...")
					);
				},
				group
			);
		}

		// 2) Client beim Provider deregistrieren → nur in Status REGISTERED
		if (frm.doc.client_status === "REGISTERED") {
			frm.add_custom_button(
				__("Deregister Client at Provider"),
				() => {
					run_doc_method(
						"deregister_client_at_provider",
						__("Deregistering Client at provider...")
					);
				},
				group
			);
		}

		// 3) Client beim Provider wieder registrieren → nur in Status DEREGISTERED
		if (frm.doc.client_status === "DEREGISTERED") {
			frm.add_custom_button(
				__("Register Client at Provider"),
				() => {
					run_doc_method(
						"register_client_at_provider",
						__("Registering Client at provider...")
					);
				},
				group
			);
		}
	},
});
