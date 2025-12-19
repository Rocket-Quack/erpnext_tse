// Copyright (c) 2025, RocketQuackIT and contributors
// For license information, please see license.txt

(() => {
  const DOCTYPE = "TSE Security Device";
  const SETTINGS_DOCTYPE = "TSE Settings";
  const SETTINGS_FLAG_FIELD = "recovery_sync_enabled";

  const RECOVERY_BTN_LABEL = __("Recovery Sync");
  const RECOVERY_SUCCESS_MSG = __("Recovery sync queued.");
  const RECOVERY_FAILED_MSG = __("Could not start recovery sync.");
  const RECOVERY_FREEZE_MSG = __("Starting recovery sync...");
  const RECOVERY_EVENT = "tse_recovery_done";

  function toInt(val) {
    if (val === true) return 1;
    if (val === false) return 0;
    const n = parseInt(val, 10);
    return Number.isFinite(n) ? n : 0;
  }

  async function getRecoveryEnabled() {
    try {
      const v = await frappe.db.get_single_value(SETTINGS_DOCTYPE, SETTINGS_FLAG_FIELD);
      return toInt(v) === 1;
    } catch (e) {
      return false;
    }
  }

  function ensurePage(listview) {
    return listview && listview.page;
  }

  let subscribed = false;

  function ensureRealtimeSubscription() {
    if (subscribed || !frappe.realtime) return;
    frappe.realtime.on(RECOVERY_EVENT, (data) => {
      const message = (data && data.message) || __("Recovery sync finished.");
      frappe.show_alert({ message, indicator: "green" }, 7);
    });
    subscribed = true;
  }

  async function updateRecoveryButton(listview) {
    if (!ensurePage(listview)) return;
    ensureRealtimeSubscription();

    // idempotent: always reset first (safe across refreshes)
    if (listview.page.remove_inner_button) {
      listview.page.remove_inner_button(RECOVERY_BTN_LABEL);
    }

    const enabled = await getRecoveryEnabled();
    if (!enabled) return;

    listview.page.add_inner_button(RECOVERY_BTN_LABEL, () => {
      triggerRecoverySync();
    });
  }

  async function triggerRecoverySync() {
    try {
      const r = await frappe.call({
        method:
          "erpnext_tse.erpnext_tse.doctype.tse_security_device.recovery.enqueue_recovery_sync",
        freeze: true,
        freeze_message: RECOVERY_FREEZE_MSG,
      });

      const payload = r.message || {};
      const jobId = payload.job_id || payload.name || payload.id;
      const message = jobId
        ? __("Recovery sync queued (Job ID: {0})", [jobId])
        : RECOVERY_SUCCESS_MSG;

      frappe.msgprint({
        message,
        indicator: "green",
      });
    } catch (err) {
      const msg = err?.message || err || RECOVERY_FAILED_MSG;
      frappe.msgprint({
        title: __("Recovery Sync"),
        message: msg,
        indicator: "red",
      });
    }
  }

  const INDICATORS = {
    INITIALIZED: { color: "green" },
    UNINITIALIZED: { color: "orange" },
    CREATED: { color: "blue" },
    DISABLED: { color: "red" },
    ORPHANED: { color: "gray" },
    ERROR: { color: "red" },
    DRAFT: { color: "gray" },
  };

  function indicatorFor(doc) {
    const status = doc.tss_status || "DRAFT";
    const conf = INDICATORS[status] || { color: "gray" };
    return [__(status), conf.color, `tss_status,=,${status}`];
  }

  frappe.listview_settings[DOCTYPE] = {
    add_fields: ["tss_status"],

    get_indicator: indicatorFor,

    onload(listview) {
      setTimeout(() => updateRecoveryButton(listview), 0);
    },

    refresh(listview) {
      setTimeout(() => updateRecoveryButton(listview), 0);
    },
  };
})();
