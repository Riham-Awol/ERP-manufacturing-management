# -*- coding: utf-8 -*-
"""Public provenance page reached by scanning the QR on a retail pouch.

Two deliberate design decisions:

* The page is ``auth="public"`` and exposes *provenance*, never personal data.
  A consumer sees "Gamo region, Gamo Women Fruit Growers Union, 14 outgrowers,
  62% women"; they never see a farmer's name, phone number or price.
* An unknown code returns a friendly page rather than a 404, because the most
  likely cause is a smudged thermal label, not an attack. Genuinely invalid
  input still never reaches the ORM as a raw domain.
"""

from odoo import http
from odoo.http import request


class AifaTracePortal(http.Controller):

    @http.route(["/trace", "/trace/<string:lot_code>"], type="http",
                auth="public", website=False, sitemap=False)
    def trace_page(self, lot_code=None, **kw):
        values = {"lot_code": lot_code, "payload": None, "found": False}
        if lot_code:
            lot = request.env["stock.lot"].sudo().search(
                [("name", "=", lot_code.strip())], limit=1
            )
            if not lot:
                intake = request.env["aifa.intake.batch"].sudo().search(
                    [("lot_number", "=", lot_code.strip())], limit=1
                )
                lot = intake.lot_id
            if lot:
                if not lot.aifa_trace_rebuilt_on:
                    lot.action_rebuild_genealogy()
                values.update({"found": True, "payload": lot.aifa_public_payload()})
        return request.render("aifa_traceability.trace_public_page", values)

    @http.route("/aifa/api/v1/traceability/<string:lot_code>", type="json",
                auth="public", methods=["POST"])
    def trace_json(self, lot_code, **kw):
        """Machine-readable provenance, for the e-commerce partners' own pages."""
        lot = request.env["stock.lot"].sudo().search([("name", "=", lot_code)], limit=1)
        if not lot:
            return {"status": "error",
                    "error": {"code": "not_found", "message": "Unknown lot code."}}
        if not lot.aifa_trace_rebuilt_on:
            lot.action_rebuild_genealogy()
        return {"status": "ok", "traceability": lot.aifa_public_payload()}
