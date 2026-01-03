// Copyright (c) 2025, RocketQuackIT and contributors
// For license information, please see LICENSE

// Client-side logic for the TSE Settings doctype
function toggleDisableWarning(frm) {
	const was_enabled = !!frm._tse_was_enabled;
	const show_warning = was_enabled && !frm.doc.enabled;
	frm.toggle_display("tse_disable_warning_html", show_warning);
	frm.toggle_display("tse_disable_acknowledged", show_warning);
}

function updateDisableWarningHtml(frm) {
	const message = __(
		"Warning: Disabling TSE interrupts the continuous signing of receipts. This can create gaps in the signature chain. Please confirm that you understand this."
	);
	frm.set_df_property(
		"tse_disable_warning_html",
		"options",
		`<div class="alert alert-warning">${message}</div>`
	);
}

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
                                <p><b>${__("Status")}:</b> ${data.status || "-"}</p>
                                <p><b>${__("Environment")}:</b> ${data.environment || "-"}</p>
                                <p><b>${__("Organization ID")}:</b> ${
								data.organization_id || "-"
							}</p>
                                <p><b>${__("Access Token Expires At")}:</b> ${
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
		if (frm._tse_was_enabled === undefined) {
			frm._tse_was_enabled = !!frm.doc.enabled;
		}
		updateDisableWarningHtml(frm);
		toggleDisableWarning(frm);
	},

	// Triggered when the "enabled" checkbox is toggled
	enabled(frm) {
		const debug = !!frm.doc.enable_debug_logging;

		if (debug) {
			console.log("[TSE Settings] enabled changed:", frm.doc.enabled);
		}

		const was_enabled = !!frm._tse_was_enabled;

		if (frm.doc.enabled) {
			frm.set_value("tse_disable_acknowledged", 0);
			frappe.msgprint({
				title: __("TSE Enabled"),
				message: __("TSE integration has been enabled. Please save to apply changes."),
				indicator: "green",
			});
		} else if (was_enabled) {
			frappe.msgprint({
				title: __("TSE Warning"),
				message: __(
					"Warning: Disabling TSE interrupts the continuous signing of receipts. Please confirm the warning before saving."
				),
				indicator: "orange",
			});
		} else {
			frappe.msgprint({
				title: __("TSE Disabled"),
				message: __("TSE integration has been disabled. Please save to apply changes."),
				indicator: "orange",
			});
		}
		updateDisableWarningHtml(frm);
		toggleDisableWarning(frm);
		// The button will appear / disappear after the user saves and the form reloads
	},
});
