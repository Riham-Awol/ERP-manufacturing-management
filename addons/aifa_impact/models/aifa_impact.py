# -*- coding: utf-8 -*-
from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AifaImpactAssumption(models.Model):
    """The counterfactual behind the post-harvest-loss claim.

    A donor auditor's first question about "X tonnes of loss averted" is *"against
    what baseline?"*. Storing the assumed loss rate per crop and region, with an
    effective date and a cited source, is the difference between a defensible
    figure and a marketing number.
    """

    _name = "aifa.impact.assumption"
    _description = "Impact Reporting Assumption"
    _order = "crop_id, date_start desc"

    crop_id = fields.Many2one("aifa.crop", required=True)
    region_id = fields.Many2one("aifa.region", help="Leave empty for a national assumption.")
    loss_rate_pct = fields.Float(
        string="Counterfactual Loss Rate (%)", required=True, default=33.0, digits=(5, 2),
        help="Share of this crop that would have spoiled between the farm gate and a "
             "market in the absence of the Aifa offtake.",
    )
    farm_income_uplift = fields.Monetary(
        string="Assumed Annual Income Uplift", currency_field="currency_id",
        help="Used only in the narrative report, never in the kg figures.",
    )
    currency_id = fields.Many2one(
        "res.currency", default=lambda self: self.env.company.currency_id, required=True,
    )
    date_start = fields.Date(required=True, default=fields.Date.context_today)
    date_end = fields.Date()
    source = fields.Char(
        required=True, default="FAO / Ethiopian ATI post-harvest loss estimates for "
                               "perishable horticulture",
        help="Citation for the assumed rate. Required: an uncited assumption is an opinion.",
    )
    note = fields.Text()

    @api.model
    def rate_for(self, crop, region=None, date=None):
        date = date or fields.Date.context_today(self)
        base = [("crop_id", "=", crop.id), ("date_start", "<=", date),
                "|", ("date_end", "=", False), ("date_end", ">=", date)]
        if region:
            found = self.search(base + [("region_id", "=", region.id)], limit=1)
            if found:
                return found.loss_rate_pct
        found = self.search(base + [("region_id", "=", False)], limit=1)
        return found.loss_rate_pct if found else 33.0


class AifaImpactReport(models.Model):
    """A period impact statement for P4G / CARE and ESG reporting (FRS-8.2, FRS-8.3)."""

    _name = "aifa.impact.report"
    _description = "ESG Impact Report"
    _inherit = ["mail.thread"]
    _order = "period_end desc"

    name = fields.Char(required=True, default="New")
    period_start = fields.Date(required=True)
    period_end = fields.Date(required=True, default=fields.Date.context_today)
    donor = fields.Selection(
        [("p4g", "P4G"), ("care", "CARE International"), ("internal", "Internal / Board"),
         ("other", "Other")],
        default="p4g", required=True,
    )
    prepared_by_id = fields.Many2one("res.users", default=lambda self: self.env.user)

    # ---- sourcing volume ----
    fruit_sourced_kg = fields.Float(readonly=True, digits=(14, 2))
    fruit_rejected_kg = fields.Float(readonly=True, digits=(14, 2))
    loss_averted_kg = fields.Float(
        readonly=True, digits=(14, 2),
        help="Accepted fresh fruit multiplied by the counterfactual loss rate for its "
             "crop and region.",
    )
    loss_averted_note = fields.Text(readonly=True)

    # ---- livelihoods ----
    active_outgrowers = fields.Integer(readonly=True)
    women_outgrowers = fields.Integer(readonly=True)
    women_outgrower_pct = fields.Float(readonly=True, digits=(5, 2))
    cooperatives_engaged = fields.Integer(readonly=True)
    payouts_total = fields.Monetary(readonly=True, currency_field="currency_id")
    payout_per_outgrower = fields.Monetary(readonly=True, currency_field="currency_id")
    currency_id = fields.Many2one(
        "res.currency", default=lambda self: self.env.company.currency_id, readonly=True,
    )

    # ---- circularity ----
    scrap_total_kg = fields.Float(readonly=True, digits=(14, 2))
    scrap_valorised_kg = fields.Float(
        readonly=True, digits=(14, 2),
        help="Prep scrap sent to compost, animal feed or a secondary product rather "
             "than to landfill.",
    )
    scrap_valorised_pct = fields.Float(readonly=True, digits=(5, 2))

    # ---- production ----
    dried_output_kg = fields.Float(readonly=True, digits=(14, 2))
    energy_kwh = fields.Float(readonly=True, digits=(14, 2))
    energy_per_kg = fields.Float(readonly=True, digits=(8, 3))
    solar_share_pct = fields.Float(readonly=True, digits=(5, 2))

    state = fields.Selection(
        [("draft", "Draft"), ("computed", "Computed"), ("submitted", "Submitted")],
        default="draft", tracking=True,
    )
    narrative = fields.Html()

    @api.onchange("period_end", "donor")
    def _onchange_period(self):
        if self.period_end and not self.period_start:
            self.period_start = self.period_end - relativedelta(months=3)

    def action_compute(self):
        for report in self:
            if report.period_start > report.period_end:
                raise UserError(_("The period start is after the period end."))
            env = self.env
            domain = [("intake_date", ">=", report.period_start),
                      ("intake_date", "<=", report.period_end),
                      ("state", "in", ("accepted", "done"))]
            intakes = env["aifa.intake.batch"].search(domain)
            assumptions = env["aifa.impact.assumption"]

            averted = 0.0
            breakdown = []
            for crop in intakes.mapped("crop_id"):
                for region in intakes.filtered(lambda b: b.crop_id == crop).mapped("region_id"):
                    subset = intakes.filtered(
                        lambda b: b.crop_id == crop and b.region_id == region
                    )
                    kg = sum(subset.mapped("accepted_weight_kg"))
                    rate = assumptions.rate_for(crop, region, report.period_end)
                    averted += kg * rate / 100.0
                    breakdown.append(
                        "%s / %s: %.0f kg sourced x %.1f%% assumed loss = %.0f kg averted"
                        % (crop.name, region.name or "-", kg, rate, kg * rate / 100.0)
                    )

            farmers = intakes.mapped("farmer_id")
            women = farmers.filtered(lambda f: f.gender == "female")
            payouts = env["aifa.farmer.payout"].search([
                ("date", ">=", report.period_start), ("date", "<=", report.period_end),
                ("state", "=", "paid"),
            ])
            prep_logs = env["aifa.prep.log"].search([
                ("date", ">=", report.period_start), ("date", "<=", report.period_end),
                ("state", "=", "done"),
            ])
            scrap = prep_logs.mapped("scrap_line_ids")
            valorised = scrap.filtered(lambda s: s.destination != "waste")
            runs = env["aifa.dehydration.run"].search([
                ("load_datetime", ">=", fields.Datetime.to_datetime(report.period_start)),
                ("load_datetime", "<=", fields.Datetime.to_datetime(report.period_end)),
                ("state", "in", ("released", "unloaded", "quarantine")),
            ])
            solar_runs = runs.filtered(lambda r: r.dehydrator_id.dryer_type == "solar")
            dried = sum(runs.mapped("dry_weight_kg"))
            energy = sum(runs.mapped("energy_kwh"))

            report.write({
                "name": report.name if report.name != "New" else _("Impact %(start)s - %(end)s")
                        % {"start": report.period_start, "end": report.period_end},
                "fruit_sourced_kg": sum(intakes.mapped("accepted_weight_kg")),
                "fruit_rejected_kg": sum(intakes.mapped("rejected_weight_kg")),
                "loss_averted_kg": averted,
                "loss_averted_note": "\n".join(breakdown),
                "active_outgrowers": len(farmers),
                "women_outgrowers": len(women),
                "women_outgrower_pct": (len(women) / len(farmers) * 100.0) if farmers else 0.0,
                "cooperatives_engaged": len(intakes.mapped("cooperative_id")),
                "payouts_total": sum(payouts.mapped("net_amount")),
                "payout_per_outgrower": (
                    sum(payouts.mapped("net_amount")) / len(farmers) if farmers else 0.0
                ),
                "scrap_total_kg": sum(scrap.mapped("weight_kg")),
                "scrap_valorised_kg": sum(valorised.mapped("weight_kg")),
                "scrap_valorised_pct": (
                    sum(valorised.mapped("weight_kg")) / sum(scrap.mapped("weight_kg")) * 100.0
                    if scrap else 0.0
                ),
                "dried_output_kg": dried,
                "energy_kwh": energy,
                "energy_per_kg": (energy / dried) if dried else 0.0,
                "solar_share_pct": (
                    sum(solar_runs.mapped("dry_weight_kg")) / dried * 100.0 if dried else 0.0
                ),
                "state": "computed",
            })
        return True

    def action_submit(self):
        for report in self:
            if report.state != "computed":
                raise UserError(_("Compute %s before submitting it.") % report.name)
            report.state = "submitted"
