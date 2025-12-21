# Copyright (c) 2025, RocketQuackIT and contributors
# For license information, please see LICENSE

import frappe


def set_pos_profile_on_client(doc, method=None):
    """
    Wenn im TSE Client ein POS Profile gesetzt ist, schreibe den Link zurück in das POS Profile.
    Dadurch bleibt die Beziehung konsistent, auch wenn der POS Profile-Eintrag zuerst gesetzt wird.
    """
    if not getattr(doc, "pos_profile", None):
        return
    frappe.db.set_value("POS Profile", doc.pos_profile, "tse_client", doc.name, update_modified=False)
