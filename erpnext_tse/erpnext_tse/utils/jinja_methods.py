# Copyright (c) 2025, RocketQuackIT and contributors
# For license information, please see LICENSE

from __future__ import annotations

from typing import Any

import frappe
from frappe import _


def get_tse_qr_code(data: Any) -> str:
	"""Return a data-URI for a QR code SVG, or empty string if unavailable."""
	if not data:
		return ""

	try:
		from frappe.twofactor import get_qr_svg_code
	except Exception:
		frappe.log_error(_("QR code helper unavailable"), _("TSE Print Format"))
		return ""

	svg_b64 = get_qr_svg_code(str(data))
	if isinstance(svg_b64, bytes):
		svg_b64 = svg_b64.decode()

	return f"data:image/svg+xml;base64,{svg_b64}"
