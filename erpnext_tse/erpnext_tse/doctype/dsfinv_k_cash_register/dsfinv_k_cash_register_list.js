// Copyright (c) 2025, RocketQuackIT and contributors
// For license information, please see license.txt

(() => {
	const DOCTYPE = "DSFinV-K Cash Register";

	const INDICATORS = {
		ACTIVE: { color: "green" },
		ERROR: { color: "red" },
		ORPHANED: { color: "gray" },
		DRAFT: { color: "gray" },
	};

	function indicatorFor(doc) {
		const status = doc.status || "DRAFT";
		const conf = INDICATORS[status] || { color: "gray" };
		return [__(status), conf.color, `status,=,${status}`];
	}

	frappe.listview_settings[DOCTYPE] = {
		add_fields: ["status"],
		get_indicator: indicatorFor,
	};
})();
