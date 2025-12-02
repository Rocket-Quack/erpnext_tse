// Copyright (c) 2025, RocketQuackIT and contributors
// For license information, please see license.txt

frappe.ui.form.on('TSE Settings', {
    enabled: function(frm) {
        if (frm.doc.enabled) {
            frappe.msgprint({
                title: __('TSE aktiviert'),
                message: __('Die TSE-Integration wurde aktiviert. Zum übernehmen Bitte Speichern'),
                indicator: 'green'
            });
        } else {
            frappe.msgprint({
                title: __('TSE deaktiviert'),
                message: __('Die TSE-Integration wurde deaktiviert. Zum übernehmen Bitte Speichern'),
                indicator: 'orange'
            });
        }
    }
});