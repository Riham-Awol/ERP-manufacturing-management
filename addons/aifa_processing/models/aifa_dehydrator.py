# -*- coding: utf-8 -*-
from odoo import _, api, fields, models


class AifaDehydrator(models.Model):
    """A physical drying chamber.

    Modelled separately from ``mrp.workcenter`` because the plant thinks in
    chambers and trolleys, not in work centres, and because the chamber carries
    agro-specific capacity (trays, kg of wet load) and energy characteristics
    that MRP has no field for.  A chamber can still be linked to a work centre
    so that standard MRP capacity planning keeps working.
    """

    _name = "aifa.dehydrator"
    _description = "Dehydration Chamber"
    _inherit = ["mail.thread"]
    _order = "sequence, code"

    name = fields.Char(required=True, tracking=True)
    code = fields.Char(required=True, size=10, help="e.g. TD-01 for Tunnel Dehydrator 1.")
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    dryer_type = fields.Selection(
        [("tunnel", "Tunnel Dehydrator"),
         ("cabinet", "Tray Cabinet Dehydrator"),
         ("solar", "Hybrid Solar Dryer"),
         ("freeze", "Freeze Dryer")],
        default="cabinet", required=True, tracking=True,
    )
    workcenter_id = fields.Many2one(
        "mrp.workcenter", string="Linked Work Centre",
        help="Optional link so standard MRP capacity planning sees the chamber.",
    )
    location_id = fields.Many2one(
        "stock.location", string="WIP Location", domain="[('usage', '=', 'internal')]",
    )

    tray_capacity = fields.Integer(string="Trays", default=80, required=True)
    kg_per_tray = fields.Float(string="Wet kg per Tray", default=4.0, digits=(8, 3))
    max_wet_load_kg = fields.Float(
        compute="_compute_capacity", store=True, string="Max Wet Load (kg)", digits=(12, 3),
    )
    rated_power_kw = fields.Float(string="Rated Power (kW)", default=18.0)
    energy_tariff = fields.Monetary(
        string="Energy Tariff / kWh", currency_field="currency_id", default=2.12,
        help="Default tariff used to value a run's energy when no meter reading is entered.",
    )
    currency_id = fields.Many2one(
        "res.currency", default=lambda self: self.env.company.currency_id, readonly=True,
    )
    temp_min = fields.Float(string="Min Setpoint (C)", default=45.0)
    temp_max = fields.Float(string="Max Setpoint (C)", default=70.0)
    has_datalogger = fields.Boolean(
        string="Thermal Data Logger Fitted",
        help="When fitted, the temperature profile is uploaded automatically to each run.",
    )

    state = fields.Selection(
        [("idle", "Idle"), ("loading", "Loading"), ("running", "Running"),
         ("unloading", "Unloading"), ("cleaning", "Cleaning / CIP"),
         ("maintenance", "Under Maintenance")],
        default="idle", tracking=True, copy=False,
    )
    current_run_id = fields.Many2one("aifa.dehydration.run", readonly=True, copy=False)
    last_cip_date = fields.Datetime(string="Last Sanitation", readonly=True)
    run_ids = fields.One2many("aifa.dehydration.run", "dehydrator_id", string="Runs")
    run_count = fields.Integer(compute="_compute_run_stats")
    avg_yield_pct = fields.Float(compute="_compute_run_stats", digits=(5, 2),
                                 string="Average Yield (%)")
    total_kwh = fields.Float(compute="_compute_run_stats", string="Energy Used (kWh)")
    note = fields.Text()

    _sql_constraints = [("code_uniq", "unique(code)", "The chamber code must be unique.")]

    @api.depends("tray_capacity", "kg_per_tray")
    def _compute_capacity(self):
        for dryer in self:
            dryer.max_wet_load_kg = dryer.tray_capacity * dryer.kg_per_tray

    def _compute_run_stats(self):
        for dryer in self:
            done = dryer.run_ids.filtered(lambda r: r.state == "done")
            dryer.run_count = len(dryer.run_ids)
            dryer.avg_yield_pct = (
                sum(done.mapped("actual_yield_pct")) / len(done) if done else 0.0
            )
            dryer.total_kwh = sum(dryer.run_ids.mapped("energy_kwh"))

    def action_set_maintenance(self):
        self.write({"state": "maintenance"})

    def action_set_idle(self):
        self.write({"state": "idle", "current_run_id": False})

    def action_log_cip(self):
        """Record a clean-in-place event; QA module hooks a signed log onto this."""
        self.write({"last_cip_date": fields.Datetime.now(), "state": "idle"})
        for dryer in self:
            dryer.message_post(body=_("Sanitation (CIP) completed by %s.") % self.env.user.name)

    def action_view_runs(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Runs of %s") % self.code,
            "res_model": "aifa.dehydration.run",
            "view_mode": "tree,form",
            "domain": [("dehydrator_id", "=", self.id)],
            "context": {"default_dehydrator_id": self.id},
        }

    @api.depends("code", "name")
    def _compute_display_name(self):
        for dryer in self:
            dryer.display_name = "[%s] %s" % (dryer.code or "", dryer.name or "")
