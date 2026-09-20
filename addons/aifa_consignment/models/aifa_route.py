# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AifaRouteTrip(models.Model):
    """A van's day: load, stops, deliveries, returns and end-of-day settlement.

    The settlement is the part that matters. Without it, van stock quietly
    becomes "shrinkage"; with it, every unit loaded is either delivered,
    returned to the warehouse or explained.
    """

    _name = "aifa.route.trip"
    _description = "Van Sales Route Trip"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date desc, id desc"

    name = fields.Char(required=True, copy=False, readonly=True, default="New", index=True)
    date = fields.Date(required=True, default=fields.Date.context_today, tracking=True)
    driver_id = fields.Many2one("res.users", string="Driver / Sales Rep", required=True,
                                default=lambda self: self.env.user, tracking=True)
    vehicle_plate = fields.Char(string="Vehicle Plate")
    zone = fields.Selection(
        [("bole", "Bole / Kazanchis"), ("piassa", "Piassa / Arat Kilo"),
         ("cmc", "CMC / Megenagna"), ("sarbet", "Sarbet / Old Airport"),
         ("gerji", "Gerji / Summit"), ("other", "Other / Regional")],
        string="Route Zone", default="bole",
    )
    stop_ids = fields.One2many("aifa.route.stop", "trip_id", string="Stops")
    stop_count = fields.Integer(compute="_compute_totals", store=True)
    delivered_units = fields.Float(compute="_compute_totals", store=True, digits=(12, 2))
    returned_units = fields.Float(compute="_compute_totals", store=True, digits=(12, 2))
    cash_collected = fields.Monetary(compute="_compute_totals", store=True,
                                     currency_field="currency_id")
    currency_id = fields.Many2one(
        "res.currency", default=lambda self: self.env.company.currency_id, readonly=True,
    )
    odometer_start = fields.Float()
    odometer_end = fields.Float()
    distance_km = fields.Float(compute="_compute_distance", store=True, digits=(8, 1))
    state = fields.Selection(
        [("planned", "Planned"), ("loaded", "Van Loaded"), ("running", "On Route"),
         ("settled", "Settled"), ("cancel", "Cancelled")],
        default="planned", tracking=True,
    )
    settlement_note = fields.Text()

    @api.depends("stop_ids.delivered_units", "stop_ids.returned_units",
                 "stop_ids.cash_collected")
    def _compute_totals(self):
        for trip in self:
            trip.stop_count = len(trip.stop_ids)
            trip.delivered_units = sum(trip.stop_ids.mapped("delivered_units"))
            trip.returned_units = sum(trip.stop_ids.mapped("returned_units"))
            trip.cash_collected = sum(trip.stop_ids.mapped("cash_collected"))

    @api.depends("odometer_start", "odometer_end")
    def _compute_distance(self):
        for trip in self:
            trip.distance_km = max(trip.odometer_end - trip.odometer_start, 0.0)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = self.env["ir.sequence"].next_by_code("aifa.route.trip") or "New"
        return super().create(vals_list)

    def action_load_van(self):
        for trip in self:
            if not trip.stop_ids:
                raise UserError(_("Plan at least one stop before loading the van."))
            trip.state = "loaded"

    def action_start(self):
        self.write({"state": "running"})

    def action_settle(self):
        for trip in self:
            unvisited = trip.stop_ids.filtered(lambda s: s.state == "planned")
            if unvisited:
                raise UserError(
                    _("%(n)s stop(s) on %(trip)s are still marked as planned. Mark each one "
                      "delivered, refused or skipped so the van stock reconciles.")
                    % {"n": len(unvisited), "trip": trip.name}
                )
            trip.state = "settled"
            trip.message_post(
                body=_("Route settled: %(d)s units delivered, %(r)s returned, "
                       "%(c)s collected over %(k)s km.")
                % {"d": trip.delivered_units, "r": trip.returned_units,
                   "c": trip.cash_collected, "k": trip.distance_km}
            )

    def action_cancel(self):
        self.write({"state": "cancel"})


class AifaRouteStop(models.Model):
    _name = "aifa.route.stop"
    _description = "Van Route Stop"
    _order = "trip_id, sequence, id"

    trip_id = fields.Many2one("aifa.route.trip", required=True, ondelete="cascade")
    sequence = fields.Integer(default=10)
    partner_id = fields.Many2one("res.partner", string="Customer", required=True)
    channel = fields.Selection(related="partner_id.aifa_channel", readonly=True)
    planned_time = fields.Float(string="Planned Time", help="Decimal hours, e.g. 9.5 for 09:30.")
    arrival_time = fields.Datetime()
    delivered_units = fields.Float(digits=(12, 2))
    returned_units = fields.Float(digits=(12, 2))
    cash_collected = fields.Monetary(currency_field="currency_id")
    currency_id = fields.Many2one(related="trip_id.currency_id", readonly=True)
    payment_method = fields.Selection(
        [("cash", "Cash"), ("telebirr", "Telebirr"), ("transfer", "Bank Transfer"),
         ("credit", "On Account (credit)"), ("consignment", "Consignment - not billed")],
        default="cash",
    )
    picking_id = fields.Many2one("stock.picking", string="Delivery")
    sale_order_id = fields.Many2one("sale.order", string="Order")
    shelf_count_id = fields.Many2one("aifa.shelf.count", string="Shelf Count")
    signature_name = fields.Char(string="Received By")
    signature = fields.Binary(string="Signature", attachment=True)
    state = fields.Selection(
        [("planned", "Planned"), ("delivered", "Delivered"),
         ("refused", "Refused"), ("skipped", "Skipped - closed")],
        default="planned", required=True,
    )
    note = fields.Char()

    def action_mark_delivered(self):
        for stop in self:
            if not stop.signature_name:
                raise UserError(
                    _("Capture who received the delivery at %s. An unsigned delivery note "
                      "is exactly the dispute the system is meant to eliminate.")
                    % stop.partner_id.name
                )
            stop.write({"state": "delivered", "arrival_time": fields.Datetime.now()})

    def action_mark_refused(self):
        self.write({"state": "refused", "arrival_time": fields.Datetime.now()})

    def action_mark_skipped(self):
        self.write({"state": "skipped"})
