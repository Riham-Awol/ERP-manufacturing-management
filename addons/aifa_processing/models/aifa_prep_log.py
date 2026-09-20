# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from .aifa_stage import SCRAP_CAUSES


class AifaPrepLog(models.Model):
    """Stage 1 mass balance: what went into prep, what came out, where the rest went.

    This is the record that answers the single most expensive question in the
    as-is process - *"why did 100 kg of pineapple become 48 kg instead of
    55 kg?"* - because the loss is broken down by cause at the station rather
    than estimated at the end of the week.
    """

    _name = "aifa.prep.log"
    _description = "Preparation Station Log"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date desc, id desc"

    name = fields.Char(compute="_compute_name", store=True)
    date = fields.Date(required=True, default=fields.Date.context_today, index=True)
    shift = fields.Selection(
        [("a", "Shift A (06:00-14:00)"), ("b", "Shift B (14:00-22:00)"), ("c", "Shift C (night)")],
        default="a", required=True,
    )
    production_id = fields.Many2one(
        "mrp.production", string="Manufacturing Order",
        domain="[('aifa_stage', '=', 'prep')]", index=True,
    )
    crop_id = fields.Many2one("aifa.crop", required=True, index=True)
    intake_batch_ids = fields.Many2many(
        "aifa.intake.batch", string="Source Intake Lots",
        domain="[('state', '=', 'done')]",
        help="The raw lots consumed. Keeping this explicit is what preserves "
             "farm-gate genealogy through a stage that physically mixes lots.",
    )
    operator_ids = fields.Many2many("res.users", string="Operators")
    supervisor_id = fields.Many2one("res.users", string="Supervisor",
                                    default=lambda self: self.env.user)

    raw_input_kg = fields.Float(required=True, digits=(12, 3), tracking=True)
    prepped_output_kg = fields.Float(required=True, digits=(12, 3), tracking=True)
    scrap_line_ids = fields.One2many("aifa.prep.scrap", "prep_log_id", string="Scrap Breakdown")
    scrap_total_kg = fields.Float(compute="_compute_balance", store=True, digits=(12, 3))
    unaccounted_kg = fields.Float(
        compute="_compute_balance", store=True, digits=(12, 3),
        help="raw in - prepped out - declared scrap. Anything material here means the "
             "scale readings or the scrap log are wrong; it is never real.",
    )
    actual_yield_pct = fields.Float(compute="_compute_balance", store=True, digits=(5, 2),
                                    string="Actual Prep Yield (%)", tracking=True)
    standard_yield_pct = fields.Float(related="crop_id.prep_yield_pct", readonly=True,
                                      string="Standard Prep Yield (%)")
    yield_variance_pct = fields.Float(compute="_compute_balance", store=True, digits=(5, 2),
                                      string="Variance (pp)")
    variance_flag = fields.Selection(
        [("ok", "Within Tolerance"), ("low", "Below Tolerance"), ("high", "Above Tolerance")],
        compute="_compute_balance", store=True, default="ok",
    )

    slice_thickness_mm = fields.Float(digits=(4, 1))
    pretreatment = fields.Selection(
        [("none", "None"),
         ("citric", "Citric / Ascorbic Dip"),
         ("blanch", "Steam Blanch"),
         ("brine", "Light Brine (savoury)")],
        default="none",
        help="Aifa's proposition is additive-free, so anything other than 'None' "
             "must be signed off by the QA manager and declared on the pack.",
    )
    wash_chlorine_ppm = fields.Float(
        string="Wash Water Sanitiser (ppm)",
        help="Free chlorine (or equivalent) in the wash tank. CCP-1 of the HACCP plan.",
    )
    water_change_done = fields.Boolean(string="Wash Water Changed")
    note = fields.Text()
    state = fields.Selection(
        [("draft", "Draft"), ("done", "Confirmed"), ("cancel", "Cancelled")],
        default="draft", tracking=True, copy=False,
    )

    @api.depends("crop_id", "date", "shift")
    def _compute_name(self):
        for log in self:
            log.name = "PREP/%s/%s/%s" % (
                log.crop_id.code or "?", log.date or "", (log.shift or "").upper()
            )

    @api.depends("raw_input_kg", "prepped_output_kg", "scrap_line_ids.weight_kg",
                 "crop_id.prep_yield_pct", "crop_id.yield_tolerance_pct")
    def _compute_balance(self):
        for log in self:
            log.scrap_total_kg = sum(log.scrap_line_ids.mapped("weight_kg"))
            log.unaccounted_kg = (
                log.raw_input_kg - log.prepped_output_kg - log.scrap_total_kg
            )
            log.actual_yield_pct = (
                log.prepped_output_kg / log.raw_input_kg * 100.0 if log.raw_input_kg else 0.0
            )
            standard = log.crop_id.prep_yield_pct
            tolerance = log.crop_id.yield_tolerance_pct or 0.0
            log.yield_variance_pct = log.actual_yield_pct - standard if standard else 0.0
            if not standard or not log.raw_input_kg:
                log.variance_flag = "ok"
            elif log.yield_variance_pct < -tolerance:
                log.variance_flag = "low"
            elif log.yield_variance_pct > tolerance:
                log.variance_flag = "high"
            else:
                log.variance_flag = "ok"

    @api.constrains("raw_input_kg", "prepped_output_kg")
    def _check_balance(self):
        for log in self:
            if log.raw_input_kg <= 0:
                raise ValidationError(_("Raw input must be greater than zero."))
            if log.prepped_output_kg > log.raw_input_kg:
                raise ValidationError(
                    _("Prep cannot produce more than it consumes: %(out)s kg out of %(in)s kg in.")
                    % {"out": log.prepped_output_kg, "in": log.raw_input_kg}
                )

    @api.onchange("production_id")
    def _onchange_production(self):
        if self.production_id and self.production_id.aifa_crop_id:
            self.crop_id = self.production_id.aifa_crop_id

    def action_confirm(self):
        for log in self:
            if log.state != "draft":
                raise UserError(_("Only a draft prep log can be confirmed."))
            if abs(log.unaccounted_kg) > max(log.raw_input_kg * 0.01, 1.0):
                raise UserError(
                    _("%(name)s does not balance: %(gap)s kg is unaccounted for. "
                      "Re-weigh the scrap bins or correct the output weight before confirming "
                      "(tolerance is the greater of 1%% of input or 1 kg).")
                    % {"name": log.name, "gap": round(log.unaccounted_kg, 2)}
                )
            log.state = "done"
            log._raise_variance_activity()

    def action_cancel(self):
        self.write({"state": "cancel"})

    def action_draft(self):
        self.filtered(lambda l: l.state == "cancel").write({"state": "draft"})

    def _raise_variance_activity(self):
        """Flag an out-of-tolerance prep yield to the plant manager."""
        for log in self.filtered(lambda l: l.variance_flag != "ok"):
            manager = log.supervisor_id or self.env.user
            log.activity_schedule(
                "mail.mail_activity_data_todo",
                summary=_("Prep yield variance on %s") % log.name,
                note=_("Actual prep yield %(act).2f%% against a standard of %(std).2f%% "
                       "(%(var)+.2f pp). Check knife settings, fruit ripeness and the "
                       "scrap breakdown before the next shift.")
                     % {"act": log.actual_yield_pct, "std": log.standard_yield_pct,
                        "var": log.yield_variance_pct},
                user_id=manager.id,
            )
            log.message_post(
                body=_("<b>Yield variance: %s</b> (%.2f pp against standard)")
                % (dict(log._fields["variance_flag"].selection).get(log.variance_flag),
                   log.yield_variance_pct)
            )


class AifaPrepScrap(models.Model):
    _name = "aifa.prep.scrap"
    _description = "Preparation Scrap Line"
    _order = "prep_log_id, cause"

    prep_log_id = fields.Many2one("aifa.prep.log", required=True, ondelete="cascade")
    cause = fields.Selection(SCRAP_CAUSES, required=True, default="peel")
    weight_kg = fields.Float(required=True, digits=(12, 3))
    share_pct = fields.Float(compute="_compute_share", digits=(5, 2), string="% of Input")
    destination = fields.Selection(
        [("compost", "Compost / Biogas"),
         ("animal_feed", "Animal Feed"),
         ("byproduct", "Secondary Product (juice / vinegar)"),
         ("waste", "Waste Disposal")],
        default="compost", required=True,
        help="Tracking the destination is what makes the post-harvest-loss-averted "
             "figure in the ESG dashboard defensible.",
    )
    note = fields.Char()

    @api.depends("weight_kg", "prep_log_id.raw_input_kg")
    def _compute_share(self):
        for line in self:
            base = line.prep_log_id.raw_input_kg
            line.share_pct = (line.weight_kg / base * 100.0) if base else 0.0
