# Copyright (c) 2025, RocketQuackIT and contributors
# For license information, please see LICENSE

import frappe
from frappe import _
from frappe.model.document import Document
from datetime import datetime
from typing import Any

from erpnext_tse.erpnext_tse.tss_providers import get_tse_provider

class TSETransaction(Document):
    def before_cancel(self):
        frappe.throw(_("TSE Transactions cannot be cancelled."))

    def before_delete(self):
        frappe.throw(_("TSE Transactions cannot be deleted."))

    # ---------- Basis / Validierung ----------

    def validate(self):
        """
        Nur erlauben, wenn TSE-Funktionalität aktiviert ist
        """
        self.ensure_tse_enabled()
            
		# Sicherstellen, dass nur INITIALIZED-TSE verknüpft werden
        if self.tse_security_device:
            tss = frappe.get_doc("TSE Security Device", self.tse_security_device)
            if tss.tss_status != "INITIALIZED":
                frappe.throw(
                    _("Only TSE Security Devices with status 'INITIALIZED' "
                      "can be used for Transaction. Current status: {0}")
                    .format(tss.tss_status)
                )

        # Sicherstellen, dass verknüpfter Client auf REGISTERED steht
        if self.tse_client:
            client = frappe.get_doc("TSE Client", self.tse_client)
            if client.client_status != "REGISTERED":
                frappe.throw(
                    _("Only Client with status 'REGISTERED' "
                      "can be used for Transaction. Current status: {0}")
                    .format(client.client_status)
                )
            

    def ensure_tse_enabled(self):
        settings = frappe.get_single("TSE Settings")
        if not getattr(settings, "enabled", None):
            frappe.throw(
                _("TSE functionality is not enabled in TSE Settings. "
                  "Please enable it before creating a TSE Security Device.")
            )

# ---------------------------------------------------------------------------
# Hilfsfunktionen zur Schema Erstellung
# ---------------------------------------------------------------------------

def _build_receipt_schema_from_pos_invoice(pos_inv) -> dict[str, Any]:
    """
    Schema-Body aus einer POS Invoice erzeugen

    WICHTIG: Das ist nur ein Gerüst 
    #TODO MApping für korrekten Aufbau
    """

    # Placeholder: alles als NORMAL / NON_CASH
    total = float(pos_inv.grand_total or 0)

    receipt = {
        "receipt_type": "RECEIPT",
        "amounts_per_vat_rate": [
            {
                "vat_rate": "NORMAL",
                "amount": f"{total:.2f}",
            }
        ],
        "amounts_per_payment_type": [
            {
                "payment_type": "NON_CASH",
                "amount": f"{total:.2f}",
            }
        ],
    }

    return {
        "standard_v1": {
            "receipt": receipt,
        }
    }


# ---------------------------------------------------------------------------
# Aus POS Invoice wird eine TSE Transaction generiert
# ---------------------------------------------------------------------------

def create_tse_transaction_for_pos_invoice(doc, method: str | None = None):
    """
    DocEvent-Hook für POS Invoice (before_submit)

    Erwartet, dass die POS Invoice ein Feld `tse_client` (Link auf "TSE Client")
    hat. Von dort wird der verknüpfte TSE Client sowie dessen Security Device geladen
    """

    # 1. POS Invoice aus dict laden
    if isinstance(doc, dict):
        doc = frappe.get_doc(doc)

    # 2. Check ob wirklich POS Invoice 
    if doc.doctype != "POS Invoice":
        return

    # 3. POS Profile holen
    if not getattr(doc, "pos_profile", None):
        frappe.throw(_("POS Invoice is missing a POS Profile."))

    pos_profile = frappe.get_doc("POS Profile", doc.pos_profile)

    # 4. TSE Client aus POS Profile
    if not getattr(pos_profile, "tse_client", None):
        frappe.throw(
            _("POS Profile {0} has no TSE Client set.").format(pos_profile.name)
        )

    tse_client = frappe.get_doc("TSE Client", pos_profile.tse_client)

    # 5. TSE Security Device aus TSE Client
    if not getattr(tse_client, "tse_security_device", None):
        frappe.throw(
            _("TSE Client {0} is missing a linked TSE Security Device.").format(
                tse_client.name
            )
        )

    tse_device = frappe.get_doc("TSE Security Device", tse_client.tse_security_device)

    # 6. Setzen der benötigten IDS in welcher TSS und mit welchem CLient die SPeicherung erfolgt
    tss_id = tse_device.tss_id 
    client_id = tse_client.client_id

    if not tss_id or not client_id:
        frappe.throw(
            _("TSE Device or TSE Client is missing provider IDs (tss_id / client_id).")
        )

    if not tss_id or not client_id:
        frappe.throw(
            _(
                "TSE Device or TSE Client is missing provider IDs "
                "(tss_id / client_id)."
            )
        )

    # 7. Transaction-Typ bestimmen SALE / REFUND aus dem POS Invoice DocType
    tx_type = "SALE"
    if getattr(doc, "is_return", 0):
        tx_type = "REFUND"

    # 8. Provider holen
    settings = frappe.get_single("TSE Settings")
    provider = get_tse_provider(settings)

    # 9. Schema aus der POS Invoice bauen
    schema = _build_receipt_schema_from_pos_invoice(doc)

    # 10. Revision wird auf eins gesetzt ist somit die erste 
    #    Beim Anlegen Fachlich gesehen immer die erste
    tx_revision = 1

    # 11. Transaktion starten (start_transaction) und Transaction Details zwischen Speichern
    response = provider.start_transaction(
        tss_id=tss_id,
        client_id=client_id,
        tx_revision=1,
    )

    # 12. Anlegen des Docs mit Zwischenstand
    tse_tx = frappe.get_doc({
        "doctype": "TSE Transaction",
        "tse_security_device": tse_device.name,
        "tse_client": tse_client.name,
        "company": doc.company,
        "pos_invoice": doc.name,
        "transaction_type": tx_type,
        "transaction_id": response.get("_id"),
        "transaction_revision": tx_revision, # Sollte beim anlegen zuerst 1 sein
        "transaction_status": response.get("state"), # Sollte ACTIVE sein
        "start_time": datetime.fromtimestamp(response.get("time_start")),
    })

    # 13. Zwischenstand speichern falls etwas schief läuft

    tse_tx.flags.ignore_permissions = True
    tse_tx.insert()
    tse_tx.flags.ignore_permissions = True
    tse_tx.save()

    # 14. TSE Transaktion wird in der POS Invoice verlinkt
    doc.db_set("tse_transaction", tse_tx.name)

    # 15. Transaktion update (update_transaction)
    #    Transaktion kann beednet werden im Restaurant Umfeld müsste noch die Update Funktion kommen
    #TODO
    
    # 16. Transaktion finish (finish_transaction)
    response = provider.finish_transaction(
        tss_id=tss_id,
        client_id=client_id,
        tx_id = tse_tx.transaction_id,
        tx_revision=tx_revision+1, #TODO Revisions Nummer noch korrekt erfassen und hochzählen
        schema=schema,
    )

    # 17. Vorhandene TSE Transaction wieder laden
    tse_tx = frappe.get_doc("TSE Transaction", tse_tx.name)

    # 18. TSE Transactions Daten in Doc nachtragen und speichern
    tse_tx.transaction_status = response.get("state")
    tse_tx.end_time = datetime.fromtimestamp(response.get("time_end"))
    tse_tx.qr_code_data = response.get("qr_code_data")
    tse_tx.transaction_revision = response.get("revision")
    tse_tx.signature_counter = response.get("signature", {}).get("counter")
    tse_tx.transaction_number = response.get("number")
    tse_tx.full_schema_req = frappe.as_json({
            "schema": schema,
            "client_id": client_id,
            "state": "FINISHED",
        }, indent=2)
    tse_tx.full_schema_res = frappe.as_json(response, indent=2)

    # 19. VAT-Childs aus Schema
    receipt = schema.get("standard_v1", {}).get("receipt", {})

    for vat_row in receipt.get("amounts_per_vat_rate", []):
        vat_code = vat_row.get("vat_rate")
        amount = vat_row.get("amount")

        vat_rate_name = frappe.db.get_value(
            "TSE VAT Rate",
            {"vat_rate_code": vat_code},
            "name",
        )
        if not vat_rate_name:
            vat_rate_doc = frappe.get_doc({
                "doctype": "TSE VAT Rate",
                "vat_rate_code": vat_code,
                "description": vat_code,
            }).insert(ignore_permissions=True)
            vat_rate_name = vat_rate_doc.name

        tse_tx.append("vat_rate", {
            "vat_rate": vat_rate_name,
            "amount": amount,
        })

    # 20. Payment-Childs aus Schema
    for pay_row in receipt.get("amounts_per_payment_type", []):
        pay_code = pay_row.get("payment_type")
        amount = pay_row.get("amount")

        payment_type_name = frappe.db.get_value(
            "TSE Payment Type",
            {"payment_code": pay_code},
            "name",
        )
        if not payment_type_name:
            payment_type_doc = frappe.get_doc({
                "doctype": "TSE Payment Type",
                "payment_code": pay_code,
                "description": pay_code,
            }).insert(ignore_permissions=True)
            payment_type_name = payment_type_doc.name

        tse_tx.append("payment_types", {
            "payment_type": payment_type_name,
            "amount": amount,
        })

    # 21. TSE Transaction Updaten mit Daten und dann Submit
    tse_tx.flags.ignore_permissions = True
    tse_tx.save()
    tse_tx.flags.ignore_permissions = True
    tse_tx.submit()