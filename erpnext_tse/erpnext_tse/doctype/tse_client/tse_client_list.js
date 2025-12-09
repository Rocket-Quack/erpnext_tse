// Copyright (c) 2025, RocketQuackIT and contributors
// For license information, please see license.txt

// LIST VIEW SETTINGS
frappe.listview_settings['TSE Client'] = {
    add_fields: ['client_status'],

    get_indicator(doc) {
        if (doc.client_status === 'REGISTERED') {
            return [__('REGISTERED'), 'green', 'client_status,=,REGISTERED'];
        }
        if (doc.client_status === 'DEREGISTERED') {
            return [__('DEREGISTERED'), 'red', 'client_status,=,DEREGISTERED'];
        }
        if (doc.client_status === 'ERROR') {
            return [__('ERROR'), 'red', 'ERROR'];
        }
        return [__(doc.client_status || 'DRAFT'), 'gray', 'client_status,=,' + (doc.client_status || 'DRAFT')];
    }
};