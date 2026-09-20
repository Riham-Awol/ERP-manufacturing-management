# -*- coding: utf-8 -*-
"""JSON endpoints consumed by the offline rural-sourcing mobile client.

Design notes
------------
The mobile client keeps a local SQLite queue while the collection centre is
offline.  When connectivity returns it replays each queued document here.  Two
properties make that safe:

* **Idempotency** - every document carries a device-generated ``client_ref``
  UUID.  Replaying the same document returns the existing record instead of
  creating a duplicate, so a flaky connection that drops the response is
  harmless.
* **Server-side pricing** - the client never dictates price. It sends crop and
  grade; the server resolves the farm-gate price from the grade matrix.

Authentication uses the standard Odoo session (``auth="user"``); the mobile
client logs in once with the field agent's credentials and keeps the session
cookie. Swap to an API-key or OAuth2 bearer layer before exposing this beyond
the plant VPN.
"""

import logging

from odoo import _, fields, http
from odoo.http import request

_logger = logging.getLogger(__name__)

API_ROOT = "/aifa/api/v1"


def _error(message, code="invalid_request"):
    return {"status": "error", "error": {"code": code, "message": message}}


class AifaSourcingApi(http.Controller):

    # ------------------------------------------------------------------ reads
    @http.route(API_ROOT + "/sourcing/bootstrap", type="json", auth="user", methods=["POST"])
    def bootstrap(self, centre_code=None, **kw):
        """Everything the offline client needs cached on the device."""
        env = request.env
        centre = env["aifa.collection.centre"].search(
            [("code", "=", centre_code)], limit=1
        ) if centre_code else env["aifa.collection.centre"].browse()
        if centre_code and not centre:
            return _error(_("Unknown collection centre code %s.") % centre_code, "not_found")

        farmer_domain = [("active", "=", True)]
        if centre:
            farmer_domain.append(("centre_id", "=", centre.id))
        farmers = env["aifa.farmer"].search(farmer_domain)
        crops = env["aifa.crop"].search([("active", "=", True)])
        prices = env["aifa.grade.price"].search([
            ("date_start", "<=", fields.Date.context_today(env["aifa.grade.price"])),
        ])
        return {
            "status": "ok",
            "server_time": fields.Datetime.now().isoformat(),
            "centre": {"id": centre.id, "code": centre.code, "name": centre.name,
                       "region": centre.region_id.code} if centre else None,
            "farmers": [{
                "id": f.id, "ref": f.ref, "name": f.name,
                "phone": f.phone, "cooperative": f.cooperative_id.name,
                "crops": f.crop_ids.ids,
                "plots": [{"id": p.id, "name": p.name, "crop_id": p.crop_id.id}
                          for p in f.plot_ids],
            } for f in farmers],
            "crops": [{"id": c.id, "code": c.code, "name": c.name} for c in crops],
            "grade_prices": [{
                "crop_id": p.crop_id.id, "grade": p.grade, "region_id": p.region_id.id or None,
                "price_per_kg": p.price_per_kg, "date_start": str(p.date_start),
                "date_end": str(p.date_end) if p.date_end else None,
            } for p in prices],
        }

    @http.route(API_ROOT + "/sourcing/intake/<string:lot_number>", type="json",
                auth="user", methods=["POST"])
    def intake_read(self, lot_number, **kw):
        batch = request.env["aifa.intake.batch"].search([("lot_number", "=", lot_number)], limit=1)
        if not batch:
            return _error(_("Lot %s not found.") % lot_number, "not_found")
        return {"status": "ok", "intake": batch._api_payload()}

    # ------------------------------------------------------------------ writes
    @http.route(API_ROOT + "/sourcing/field-purchase", type="json", auth="user", methods=["POST"])
    def field_purchase_sync(self, **payload):
        """Replay one offline Field Purchase Order.

        Expected payload::

            {"client_ref": "<uuid>", "device_id": "TAB-AMC-01",
             "date": "2026-09-14", "centre_code": "AMC01",
             "gps": {"lat": 6.0371, "lng": 37.5512},
             "truck_plate": "3-A12345",
             "lines": [{"farmer_ref": "FRM/00007", "crop_code": "PINE",
                        "grade": "a", "gross_weight_kg": 412.5,
                        "crate_count": 15, "brix": 14.2,
                        "scale_serial": "SCL-AMC-02", "scale_verified": true}]}
        """
        env = request.env
        client_ref = payload.get("client_ref")
        if not client_ref:
            return _error(_("client_ref is required so the replay stays idempotent."))

        existing = env["aifa.field.purchase"].search([("client_ref", "=", client_ref)], limit=1)
        if existing:
            return {"status": "ok", "duplicate": True, "id": existing.id,
                    "name": existing.name,
                    "intakes": [b._api_payload() for b in existing.intake_ids]}

        centre = env["aifa.collection.centre"].search(
            [("code", "=", payload.get("centre_code"))], limit=1)
        if not centre:
            return _error(_("Unknown collection centre %s.") % payload.get("centre_code"),
                          "not_found")

        lines = []
        for raw in payload.get("lines", []):
            farmer = env["aifa.farmer"].search([("ref", "=", raw.get("farmer_ref"))], limit=1)
            crop = env["aifa.crop"].search([("code", "=", raw.get("crop_code"))], limit=1)
            if not farmer:
                return _error(_("Unknown outgrower %s.") % raw.get("farmer_ref"), "not_found")
            if not crop:
                return _error(_("Unknown crop %s.") % raw.get("crop_code"), "not_found")
            grade = (raw.get("grade") or "a").lower()
            price = env["aifa.grade.price"].price_for(
                crop, grade, region=centre.region_id, date=payload.get("date"))
            lines.append((0, 0, {
                "farmer_id": farmer.id,
                "crop_id": crop.id,
                "grade": grade,
                "gross_weight_kg": raw.get("gross_weight_kg", 0.0),
                "crate_count": raw.get("crate_count", 0),
                "crate_tare_kg": raw.get("crate_tare_kg", 1.8),
                "brix": raw.get("brix", 0.0),
                "scale_serial": raw.get("scale_serial"),
                "scale_verified": bool(raw.get("scale_verified")),
                "price_per_kg": price,
            }))
        if not lines:
            return _error(_("A field purchase must carry at least one weighing line."))

        gps = payload.get("gps") or {}
        order = env["aifa.field.purchase"].create({
            "client_ref": client_ref,
            "device_id": payload.get("device_id"),
            "captured_offline": True,
            "synced_at": fields.Datetime.now(),
            "date": payload.get("date") or fields.Date.context_today(env["aifa.field.purchase"]),
            "centre_id": centre.id,
            "truck_plate": payload.get("truck_plate"),
            "driver_name": payload.get("driver_name"),
            "gps_lat": gps.get("lat", 0.0),
            "gps_lng": gps.get("lng", 0.0),
            "line_ids": lines,
        })
        order.action_confirm()
        _logger.info("Aifa sync: field purchase %s replayed from device %s",
                     order.name, payload.get("device_id"))
        return {
            "status": "ok", "duplicate": False, "id": order.id, "name": order.name,
            "total_weight_kg": order.total_weight_kg, "amount_total": order.amount_total,
            "intakes": [b._api_payload() for b in order.intake_ids],
        }

    @http.route(API_ROOT + "/sourcing/intake", type="json", auth="user", methods=["POST"])
    def intake_sync(self, **payload):
        """Replay a single standalone weighing (walk-in delivery at the plant gate)."""
        env = request.env
        client_ref = payload.get("client_ref")
        if not client_ref:
            return _error(_("client_ref is required."))
        existing = env["aifa.intake.batch"].search([("client_ref", "=", client_ref)], limit=1)
        if existing:
            return {"status": "ok", "duplicate": True, "intake": existing._api_payload()}

        farmer = env["aifa.farmer"].search([("ref", "=", payload.get("farmer_ref"))], limit=1)
        crop = env["aifa.crop"].search([("code", "=", payload.get("crop_code"))], limit=1)
        centre = env["aifa.collection.centre"].search(
            [("code", "=", payload.get("centre_code"))], limit=1)
        if not (farmer and crop and centre):
            return _error(_("farmer_ref, crop_code and centre_code must all resolve."), "not_found")
        grade = (payload.get("grade") or "a").lower()
        batch = env["aifa.intake.batch"].create({
            "client_ref": client_ref,
            "farmer_id": farmer.id,
            "crop_id": crop.id,
            "centre_id": centre.id,
            "field_grade": grade,
            "gross_weight_kg": payload.get("gross_weight_kg", 0.0),
            "crate_count": payload.get("crate_count", 0),
            "brix": payload.get("brix", 0.0),
            "scale_serial": payload.get("scale_serial"),
            "gps_lat": (payload.get("gps") or {}).get("lat", 0.0),
            "gps_lng": (payload.get("gps") or {}).get("lng", 0.0),
            "price_per_kg": env["aifa.grade.price"].price_for(
                crop, grade, region=centre.region_id),
            "state": "weighed",
        })
        return {"status": "ok", "duplicate": False, "intake": batch._api_payload()}
