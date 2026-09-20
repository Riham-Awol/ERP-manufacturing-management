# -*- coding: utf-8 -*-
import logging
from datetime import timedelta

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class AifaDailyKpi(models.Model):
    """One snapshot per day per crop, computed by a nightly job.

    Materialising the KPIs rather than computing them live is a deliberate
    trade-off: the executive dashboard must open instantly on a tablet over a
    congested link, and a day that has closed does not change. The snapshot can
    always be recomputed on demand from the button on the form.
    """

    _name = "aifa.daily.kpi"
    _description = "Aifa Daily Plant KPI"
    _order = "date desc, crop_id"
    _rec_name = "display_label"

    date = fields.Date(required=True, index=True)
    crop_id = fields.Many2one("aifa.crop", index=True)
    display_label = fields.Char(compute="_compute_display_label", store=True)
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company)

    # ---- volumes ----
    intake_kg = fields.Float(digits=(12, 2), string="Raw Intake (kg)")
    intake_rejected_kg = fields.Float(digits=(12, 2), string="Rejected at Gate (kg)")
    prepped_kg = fields.Float(digits=(12, 2), string="Prepped (kg)")
    prep_scrap_kg = fields.Float(digits=(12, 2), string="Prep Scrap (kg)")
    dried_kg = fields.Float(digits=(12, 2), string="Dried Output (kg)")

    # ---- yields ----
    prep_yield_pct = fields.Float(digits=(5, 2))
    dry_yield_pct = fields.Float(digits=(5, 2))
    prep_yield_std_pct = fields.Float(digits=(5, 2))
    dry_yield_std_pct = fields.Float(digits=(5, 2))
    yield_gap_value = fields.Monetary(
        currency_field="currency_id", string="Yield Gap Value",
        help="Value of the raw fruit represented by the gap between actual and "
             "standard yield. This is the number the plant manager is paid to shrink.",
    )
    currency_id = fields.Many2one(
        "res.currency", default=lambda self: self.env.company.currency_id, readonly=True,
    )

    # ---- operations ----
    runs_completed = fields.Integer()
    runs_quarantined = fields.Integer()
    energy_kwh = fields.Float(digits=(10, 2))
    energy_per_kg = fields.Float(digits=(8, 3), string="kWh per kg Dried")
    chamber_utilisation_pct = fields.Float(digits=(5, 2))

    # ---- quality ----
    checks_total = fields.Integer()
    checks_failed = fields.Integer()
    first_pass_rate = fields.Float(digits=(5, 2), string="First-Pass Rate (%)")

    # ---- commercial ----
    intake_cost = fields.Monetary(currency_field="currency_id", string="Raw Fruit Cost")
    cost_per_kg_dried = fields.Monetary(currency_field="currency_id")

    _sql_constraints = [
        ("date_crop_uniq", "unique(date, crop_id, company_id)",
         "A KPI snapshot already exists for that day and crop."),
    ]

    @api.depends("date", "crop_id")
    def _compute_display_label(self):
        for kpi in self:
            kpi.display_label = "%s - %s" % (kpi.date or "", kpi.crop_id.name or _("All crops"))

    # ------------------------------------------------------------------ builder
    @api.model
    def _build_for_date(self, date, crop):
        """Compute (and upsert) the snapshot for one day and crop."""
        env = self.env
        intakes = env["aifa.intake.batch"].search([
            ("intake_date", "=", date), ("crop_id", "=", crop.id),
            ("state", "in", ("accepted", "done")),
        ])
        prep_logs = env["aifa.prep.log"].search([
            ("date", "=", date), ("crop_id", "=", crop.id), ("state", "=", "done"),
        ])
        day_start = fields.Datetime.to_datetime(date)
        runs = env["aifa.dehydration.run"].search([
            ("unload_datetime", ">=", day_start),
            ("unload_datetime", "<", day_start + timedelta(days=1)),
            ("crop_id", "=", crop.id),
            ("state", "in", ("unloaded", "released", "quarantine")),
        ])
        checks = env["aifa.quality.check"].search([
            ("date", ">=", day_start),
            ("date", "<", day_start + timedelta(days=1)),
            ("crop_id", "=", crop.id), ("state", "=", "done"),
        ])

        intake_kg = sum(intakes.mapped("accepted_weight_kg"))
        prepped_kg = sum(prep_logs.mapped("prepped_output_kg"))
        prep_input_kg = sum(prep_logs.mapped("raw_input_kg"))
        dried_kg = sum(runs.mapped("dry_weight_kg"))
        wet_in_kg = sum(runs.mapped("wet_weight_kg"))
        energy_kwh = sum(runs.mapped("energy_kwh"))
        intake_cost = sum(intakes.mapped("amount_total"))

        prep_yield = (prepped_kg / prep_input_kg * 100.0) if prep_input_kg else 0.0
        dry_yield = (dried_kg / wet_in_kg * 100.0) if wet_in_kg else 0.0

        gap_kg = 0.0
        if prep_input_kg and crop.prep_yield_pct:
            gap_kg += max((crop.prep_yield_pct - prep_yield) / 100.0 * prep_input_kg, 0.0)
        if wet_in_kg and crop.dry_yield_pct:
            lost_dried = max((crop.dry_yield_pct - dry_yield) / 100.0 * wet_in_kg, 0.0)
            gap_kg += lost_dried * (100.0 / crop.dry_yield_pct) if crop.dry_yield_pct else 0.0
        avg_price = (intake_cost / intake_kg) if intake_kg else 0.0

        capacity = sum(env["aifa.dehydrator"].search([]).mapped("max_wet_load_kg")) or 0.0

        values = {
            "date": date,
            "crop_id": crop.id,
            "intake_kg": intake_kg,
            "intake_rejected_kg": sum(intakes.mapped("rejected_weight_kg")),
            "prepped_kg": prepped_kg,
            "prep_scrap_kg": sum(prep_logs.mapped("scrap_total_kg")),
            "dried_kg": dried_kg,
            "prep_yield_pct": prep_yield,
            "dry_yield_pct": dry_yield,
            "prep_yield_std_pct": crop.prep_yield_pct,
            "dry_yield_std_pct": crop.dry_yield_pct,
            "yield_gap_value": gap_kg * avg_price,
            "runs_completed": len(runs.filtered(lambda r: r.state == "released")),
            "runs_quarantined": len(runs.filtered(lambda r: r.state == "quarantine")),
            "energy_kwh": energy_kwh,
            "energy_per_kg": (energy_kwh / dried_kg) if dried_kg else 0.0,
            "chamber_utilisation_pct": (wet_in_kg / capacity * 100.0) if capacity else 0.0,
            "checks_total": len(checks),
            "checks_failed": len(checks.filtered(lambda c: c.result == "fail")),
            "first_pass_rate": (
                len(checks.filtered(lambda c: c.result == "pass")) / len(checks) * 100.0
                if checks else 0.0
            ),
            "intake_cost": intake_cost,
            "cost_per_kg_dried": (intake_cost / dried_kg) if dried_kg else 0.0,
        }
        existing = self.search([
            ("date", "=", date), ("crop_id", "=", crop.id),
            ("company_id", "=", self.env.company.id),
        ], limit=1)
        if existing:
            existing.write(values)
            return existing
        return self.create(values)

    @api.model
    def cron_build_snapshots(self, days_back=2):
        """Rebuild the last few days, so late data entry is still picked up."""
        today = fields.Date.context_today(self)
        crops = self.env["aifa.crop"].search([])
        built = 0
        for offset in range(days_back + 1):
            date = today - timedelta(days=offset)
            for crop in crops:
                self._build_for_date(date, crop)
                built += 1
        _logger.info("Aifa KPI: refreshed %s daily snapshot(s).", built)
        return True

    def action_recompute(self):
        for kpi in self:
            self._build_for_date(kpi.date, kpi.crop_id)
        return True

    @api.model
    def action_rebuild_range(self, days=30):
        self.cron_build_snapshots(days_back=days)
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("KPI snapshots rebuilt"),
                "message": _("Refreshed the last %s day(s).") % days,
                "type": "success",
            },
        }
