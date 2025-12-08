# Copyright (c) 2025, RocketQuackIT and contributors
# For license information, please see LICENSE

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

def after_install():
    create_default_vat_rates()
    create_default_payment_types()
    create_custom_fields_for_erpnext()


def after_migrate():
    # Defaults werden bei Bedarf bei Migrate wieder ausgeführt
    create_default_vat_rates()
    create_default_payment_types()
    create_custom_fields_for_erpnext()


def create_default_vat_rates():
    default_rates = [
        {"vat_rate_code": "NORMAL", "description": "Regelsteuersatz"},
        {"vat_rate_code": "REDUCED_1", "description": "Ermäßigter Steuersatz"},
        {"vat_rate_code": "SPECIAL_RATE_1", "description": "Spezial Steuersatz 1"},
        {"vat_rate_code": "SPECIAL_RATE_2", "description": "Spezial Steuersatz 2"},
        {"vat_rate_code": "NULL", "description": "0 % / steuerfrei"},
    ]

    for rate in default_rates:
        if not frappe.db.exists("TSE VAT Rate", {"vat_rate_code": rate["vat_rate_code"]}):
            frappe.get_doc({
                "doctype": "TSE VAT Rate",
                "vat_rate_code": rate["vat_rate_code"],
                "description": rate["description"],
            }).insert(ignore_permissions=True)


def create_default_payment_types():
    default_payment_types = [
        {"payment_code": "CASH", "description": "Barzahlung"},
        {"payment_code": "NON_CASH", "description": "Unbare Zahlung"},
    ]

    for pt in default_payment_types:
        if not frappe.db.exists("TSE Payment Type", {"payment_code": pt["payment_code"]}):
            frappe.get_doc({
                "doctype": "TSE Payment Type",
                "payment_code": pt["payment_code"],
                "description": pt["description"],
                "is_active": 1,
            }).insert(ignore_permissions=True)


def create_custom_fields_for_erpnext():
    """
    POS Profile bekommt ein neues Feld im Standard DocType wo der TSE CLient festgelegt wird
    """

    custom_fields = {
        "POS Profile": [
            dict(
                fieldname="tse_client",
                label="TSE Client",
                fieldtype="Link",
                options="TSE Client",
                insert_after="customer",
                reqd=1,
            ),
        ],
    }

    # create_custom_fields um nichts doppelt anzulegen
    create_custom_fields(custom_fields, ignore_validate=True)