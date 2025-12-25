// Copyright (c) 2025, RocketQuackIT and contributors
// For license information, please see LICENSE

// Client-side logic for the TSE Settings doctype
frappe.ui.form.on("TSE Settings", {
	// Runs every time the form is refreshed (opened, saved, etc.)
	refresh(frm) {
		const debug = !!frm.doc.enable_debug_logging;

		if (debug) {
			console.log(
				"[TSE Settings] refresh",
				"is_new =",
				frm.is_new(),
				"enabled =",
				frm.doc.enabled,
				"provider =",
				frm.doc.tse_provider
			);
		}

		// Only show the button when the document is saved AND TSE is enabled
		if (!frm.is_new() && frm.doc.enabled) {
			frm.add_custom_button(__("Test Auth"), () => {
				if (debug) {
					console.log("[TSE Settings] Test Auth button clicked");
				}

				frappe.call({
					method: "erpnext_tse.erpnext_tse.doctype.tse_settings.tse_settings.test_tse_auth",
					freeze: true,
					freeze_message: __("Testing connection to TSE provider..."),
					callback(r) {
						const data = r.message || {};

						if (debug) {
							console.log("[TSE Settings] test_tse_auth raw response:", r);
						}

						// Fehlerfall: Server gibt success = false zurück
						if (!data.success) {
							if (debug) {
								console.warn("[TSE Settings] Auth test failed:", data);
							}

							frappe.msgprint({
								title: __("TSE Auth Failed"),
								message:
									data.error_message ||
									data.last_auth_message ||
									__("Authentication failed. Please check your settings."),
								indicator: "red",
							});

							// Status-/Token-Felder wurden serverseitig schon aktualisiert
							frm.reload_doc();
							return;
						}

						// Erfolgsfall
						frappe.msgprint({
							title: __("TSE Auth Result"),
							message: `
                                <p><b>Status:</b> ${data.status || "-"}</p>
                                <p><b>Environment:</b> ${data.environment || "-"}</p>
                                <p><b>Organization ID:</b> ${data.organization_id || "-"}</p>
                                <p><b>Access Token Expires At:</b> ${
									data.access_token_expires_at || "-"
								}</p>
                            `,
							indicator: "green",
						});

						// Reload the document so that updated fields (token/status)
						// from the server become visible in the form
						frm.reload_doc();
					},
				});
			});
		}
	},

	// Triggered when the "enabled" checkbox is toggled
	enabled(frm) {
		const debug = !!frm.doc.enable_debug_logging;

		if (debug) {
			console.log("[TSE Settings] enabled changed:", frm.doc.enabled);
		}

		if (frm.doc.enabled) {
			frappe.msgprint({
				title: __("TSE aktiviert"),
				message: __(
					"Die TSE-Integration wurde aktiviert. Zum Übernehmen bitte speichern."
				),
				indicator: "green",
			});
		} else {
			frappe.msgprint({
				title: __("TSE deaktiviert"),
				message: __(
					"Die TSE-Integration wurde deaktiviert. Zum Übernehmen bitte speichern."
				),
				indicator: "orange",
			});
		}
		// The button will appear / disappear after the user saves and the form reloads
	},
});
