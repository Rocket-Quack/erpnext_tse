// Copyright (c) 2025, RocketQuackIT and contributors
// For license information, please see license.txt

// LIST VIEW SETTINGS
frappe.listview_settings['TSE Security Device'] = {
    add_fields: ['tss_status'],

    get_indicator(doc) {
        if (doc.tss_status === 'INITIALIZED') {
            return [__('INITIALIZED'), 'green', 'tss_status,=,INITIALIZED'];
        }
        if (doc.tss_status === 'UNINITIALIZED') {
            return [__('UNINITIALIZED'), 'orange', 'tss_status,=,UNINITIALIZED'];
        }
        if (doc.tss_status === 'CREATED') {
            return [__('CREATED'), 'blue', 'tss_status,=,CREATED'];
        }
        if (doc.tss_status === 'DISABLED') {
            return [__('DISABLED'), 'red', 'tss_status,=,DISABLED'];
        }
        if (doc.tss_status === 'ERROR') {
            return [__('ERROR'), 'red', 'ERROR'];
        }
        return [__(doc.tss_status || 'DRAFT'), 'gray', 'tss_status,=,' + (doc.tss_status || 'DRAFT')];
    }
};