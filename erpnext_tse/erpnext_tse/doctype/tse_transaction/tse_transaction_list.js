// Copyright (c) 2025, RocketQuackIT and contributors
// For license information, please see LICENSE

// LIST VIEW SETTINGS
frappe.listview_settings['TSE Transaction'] = {
    add_fields: ['transaction_status'],

    get_indicator(doc) {
        if (doc.transaction_status === 'FINISHED') {
            return [__('FINISHED'), 'green', 'transaction_status,=,FINISHED'];
        }
        if (doc.transaction_status === 'ACTIVE') {
            return [__('ACTIVE'), 'blue', 'transaction_status,=,ACTIVE'];
        }
        if (doc.transaction_status === 'CANCELLED') {
            return [__('CANCELLED'), 'red', 'transaction_status,=,CANCELLED'];
        }
    }
};