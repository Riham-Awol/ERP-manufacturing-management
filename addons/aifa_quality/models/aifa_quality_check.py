# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError
from .aifa_control_point import CHECK_STAGES


class AifaQualityCheck(models.Model):
    """A single measurement taken against a control point on a specific lot.

    The check is polymorphic on purpose: the same record type covers a Brix
    reading at the gate, a water-activity result after drying and a seal
    integrity test on the packing line, because they all share the same
    life cycle - measure, score against a limit, and either pass or quarantine.
    """

    _name = "aifa.quality.check"
    _description = "Quality Check"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date desc, id desc"

    name = fields.Char(required=True, copy=False, readonly=True, default="New", index=True)
    control_point_id = fields.Many2one("aifa.control.point", required=True, index=True,
                                       tracking=True)
    stage = fields.Selection(related="control_point_id.stage", store=True, readonly=True)
    point_type = fields.Selection(related="control_point_id.point_type", store=True,
                                  readonly=True)
    is_blocking = fields.Boolean(related="control_point_id.is_blocking", readonly=True)
    date = fields.Datetime(required=True, default=fields.Datetime.now, index=True, tracking=True)
    inspector_id = fields.Many2one("res.users", required=True,
                                   default=lambda self: self.env.user, tracking=True)
    crop_id = fields.Many2one("aifa.crop", index=True)

    # ----- what is being checked: exactly one of these is normally set -----
    intake_batch_id = fields.Many2one("aifa.intake.batch", string="Intake Batch", index=True,
                                      ondelete="cascade")
    prep_log_id = fields.Many2one("aifa.prep.log", string="Prep Log", ondelete="cascade")
    dehydration_run_id = fields.Many2one("aifa.dehydration.run", string="Dehydration Run",
                                         index=True, ondelete="cascade")
    production_id = fields.Many2one("mrp.production", string="Manufacturing Order",
                                    ondelete="cascade")
    lot_id = fields.Many2one("stock.lot", string="Stock Lot", index=True, ondelete="cascade")
    dehydrator_id = fields.Many2one("aifa.dehydrator", string="Chamber")
    subject_label = fields.Char(compute="_compute_subject", store=True, string="Subject")

    # ----- the measurement -----
    result_type = fields.Selection(related="control_point_id.result_type", readonly=True)
    value_numeric = fields.Float(string="Measured Value", digits=(10, 3), tracking=True)
    value_bool = fields.Boolean(string="Answer")
    value_option_id = fields.Many2one("aifa.control.option", string="Option")
    value_text = fields.Text(string="Observation")
    uom_label = fields.Char(related="control_point_id.uom_label", readonly=True)
    limit_min = fields.Float(compute="_compute_limits", store=True, digits=(10, 3))
    limit_max = fields.Float(compute="_compute_limits", store=True, digits=(10, 3))
    sample_ref = fields.Char(string="Sample / Instrument Ref")

    result = fields.Selection(
        [("pending", "Pending"), ("pass", "Pass"), ("fail", "Fail"), ("waived", "Waived")],
        default="pending", compute="_compute_result", store=True, readonly=False,
        tracking=True, index=True,
    )
    deviation = fields.Float(compute="_compute_result", store=True, digits=(10, 3),
                             help="How far the measurement sits outside the limit band.")
    state = fields.Selection(
        [("draft", "Draft"), ("done", "Recorded"), ("cancel", "Cancelled")],
        default="draft", tracking=True, copy=False,
    )
    ncr_id = fields.Many2one("aifa.ncr", string="Non-Conformance", readonly=True, copy=False)
    note = fields.Text()
    corrective_action = fields.Text(related="control_point_id.corrective_action", readonly=True)

    @api.depends("intake_batch_id", "dehydration_run_id", "production_id", "lot_id",
                 "prep_log_id", "dehydrator_id")
    def _compute_subject(self):
        for check in self:
            subject = (
                check.intake_batch_id.lot_number
                or (check.dehydration_run_id.wip_lot_code or check.dehydration_run_id.name)
                or check.lot_id.name
                or check.production_id.name
                or check.prep_log_id.name
                or check.dehydrator_id.display_name
                or ""
            )
            check.subject_label = subject

    @api.depends("control_point_id", "crop_id")
    def _compute_limits(self):
        for check in self:
            if check.control_point_id:
                check.limit_min, check.limit_max = check.control_point_id.resolve_limits(
                    check.crop_id
                )
            else:
                check.limit_min = check.limit_max = 0.0

    @api.depends("value_numeric", "value_bool", "value_option_id", "limit_min", "limit_max",
                 "control_point_id", "result_type")
    def _compute_result(self):
        for check in self:
            point = check.control_point_id
            if not point or check.result == "waived":
                check.deviation = 0.0
                continue
            deviation = 0.0
            if point.result_type == "numeric":
                value = check.value_numeric
                below = check.limit_min and value < check.limit_min
                above = check.limit_max and value > check.limit_max
                if below:
                    deviation = value - check.limit_min
                elif above:
                    deviation = value - check.limit_max
                result = "fail" if (below or above) else "pass"
            elif point.result_type == "boolean":
                result = "pass" if check.value_bool == point.expected_bool else "fail"
            elif point.result_type == "option":
                if not check.value_option_id:
                    result = "pending"
                else:
                    result = "pass" if check.value_option_id.is_conforming else "fail"
            else:
                result = "pass"
            check.result = result
            check.deviation = deviation

    @api.onchange("intake_batch_id", "dehydration_run_id", "prep_log_id")
    def _onchange_subject_crop(self):
        crop = (self.intake_batch_id.crop_id or self.dehydration_run_id.crop_id
                or self.prep_log_id.crop_id)
        if crop:
            self.crop_id = crop

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = self.env["ir.sequence"].next_by_code("aifa.quality.check") or "New"
        return super().create(vals_list)

    # ------------------------------------------------------------------ workflow
    def action_record(self):
        """Commit the check and apply its consequence to the subject."""
        for check in self:
            if check.state != "draft":
                raise UserError(_("%s has already been recorded.") % check.name)
            if check.result == "pending":
                raise UserError(_("Enter a measurement on %s before recording it.") % check.name)
            check.state = "done"
            if check.result == "fail":
                check._apply_failure()
            else:
                check.message_post(body=_("Check passed: %s") % check._format_value())

    def action_waive(self):
        """QA manager accepts an out-of-limit result with a written justification."""
        for check in self:
            if not check.note:
                raise UserError(
                    _("A waiver on %s must carry a written justification in the notes.")
                    % check.name
                )
            check.write({"result": "waived", "state": "done"})
            check.message_post(
                body=_("<b>Concession granted</b> by %(user)s. Justification: %(note)s")
                % {"user": self.env.user.name, "note": check.note},
                subtype_xmlid="mail.mt_comment",
            )

    def action_cancel(self):
        self.write({"state": "cancel"})

    def _format_value(self):
        self.ensure_one()
        if self.result_type == "numeric":
            return "%s %s (limits %s - %s)" % (
                self.value_numeric, self.uom_label or "",
                self.limit_min or "-", self.limit_max or "-",
            )
        if self.result_type == "boolean":
            return _("Yes") if self.value_bool else _("No")
        if self.result_type == "option":
            return self.value_option_id.display_name
        return self.value_text or ""

    def _apply_failure(self):
        """Quarantine the subject and open a non-conformance report."""
        self.ensure_one()
        self.message_post(
            body=_("<b>Check failed:</b> %(val)s. Standing corrective action: %(act)s")
            % {"val": self._format_value(),
               "act": self.control_point_id.corrective_action or _("see the HACCP plan")},
            subtype_xmlid="mail.mt_comment",
        )
        if self.control_point_id.is_blocking:
            self._quarantine_subject()
        if not self.ncr_id:
            self.ncr_id = self.env["aifa.ncr"].create(self._prepare_ncr_values())

    def _quarantine_subject(self):
        self.ensure_one()
        if self.dehydration_run_id:
            self.dehydration_run_id.write({
                "qa_blocked": True,
                "state": "quarantine",
                "qa_note": _("Quarantined by %s: %s") % (self.name, self._format_value()),
            })
        if self.intake_batch_id and self.intake_batch_id.state in ("received", "accepted"):
            self.intake_batch_id.write({
                "qa_note": _("Quarantined by %s: %s") % (self.name, self._format_value()),
            })
        if self.lot_id:
            self.lot_id.aifa_quality_state = "quarantine"

    def _prepare_ncr_values(self):
        self.ensure_one()
        return {
            "control_point_id": self.control_point_id.id,
            "crop_id": self.crop_id.id,
            "subject_label": self.subject_label,
            "intake_batch_id": self.intake_batch_id.id,
            "dehydration_run_id": self.dehydration_run_id.id,
            "lot_id": self.lot_id.id,
            "description": _("%(point)s failed on %(subject)s: %(value)s.")
                           % {"point": self.control_point_id.display_name,
                              "subject": self.subject_label or "-",
                              "value": self._format_value()},
            "severity": "critical" if self.point_type == "ccp" else "major",
        }


class StockLot(models.Model):
    """Give every lot a quality state so warehouse and sales can see it."""

    _inherit = "stock.lot"

    aifa_quality_state = fields.Selection(
        [("pending", "Pending QA"), ("released", "Released"),
         ("quarantine", "Quarantined"), ("rejected", "Rejected")],
        default="pending", tracking=True, index=True, string="Quality Status",
    )
    aifa_check_ids = fields.One2many("aifa.quality.check", "lot_id", string="Quality Checks")
    aifa_origin_intake_ids = fields.Many2many(
        "aifa.intake.batch", "aifa_lot_intake_rel", "lot_id", "intake_id",
        string="Origin Intake Lots",
        help="Farm-gate lots this lot descends from. Populated by the traceability "
             "rebuild in aifa_traceability and consumed by the audit dossier.",
    )
    aifa_origin_run_ids = fields.Many2many(
        "aifa.dehydration.run", "aifa_lot_run_rel", "lot_id", "run_id",
        string="Origin Dehydration Runs",
    )
    aifa_check_count = fields.Integer(compute="_compute_aifa_check_count")
    aifa_fail_count = fields.Integer(compute="_compute_aifa_check_count")

    @api.depends("aifa_check_ids.result")
    def _compute_aifa_check_count(self):
        for lot in self:
            lot.aifa_check_count = len(lot.aifa_check_ids)
            lot.aifa_fail_count = len(
                lot.aifa_check_ids.filtered(lambda c: c.result == "fail")
            )

    def action_release_quality(self):
        for lot in self:
            failing = lot.aifa_check_ids.filtered(
                lambda c: c.result == "fail" and c.state == "done"
            )
            if failing:
                raise UserError(
                    _("Lot %(lot)s still carries %(n)s failed check(s). Waive them "
                      "explicitly or record a disposition before releasing.")
                    % {"lot": lot.name, "n": len(failing)}
                )
            lot.aifa_quality_state = "released"

    def action_quarantine_quality(self):
        self.write({"aifa_quality_state": "quarantine"})

    def action_view_aifa_checks(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Quality Checks"),
            "res_model": "aifa.quality.check",
            "view_mode": "tree,form",
            "domain": [("lot_id", "=", self.id)],
            "context": {"default_lot_id": self.id},
        }

    def action_print_audit_dossier(self):
        return self.env.ref("aifa_quality.action_report_audit_dossier").report_action(self)
