// Copyright (c) 2025, RocketQuackIT and contributors
// For license information, please see license.txt

frappe.ui.form.on('TSE Client', {
    setup(frm) {
        // Nur INITIALIZED TSE Security Devices anzeigen
        frm.set_query('tse_security_device', () => {
            const filters = {
                tss_status: 'INITIALIZED',
            };

            // Zusätzlich nach Company filtern, falls gesetzt
            if (frm.doc.company) {
                filters.company = frm.doc.company;
            }

            return { filters };
        });
    },
});