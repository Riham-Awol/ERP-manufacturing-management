# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AifaNcr(models.Model):
    """Non-conformance report with disposition and CAPA (FRS-4.3).

    An NCR is deliberately not closable without a root cause and a disposition:
    the whole point of the digital quarantine is that product cannot quietly
    rejoin the good stock while the paperwork is "still being typed up".
    """

    _name = "aifa.ncr"
    _description = "Non-Conformance Report"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date desc, id desc"

    name = fields.Char(required=True, copy=False, readonly=True, default="New", index=True)
    date = fields.Datetime(required=True, default=fields.Datetime.now, tracking=True)
    raised_by_id = fields.Many2one("res.users", required=True,
                                   default=lambda self: self.env.user, tracking=True)
    control_point_id = fields.Many2one("aifa.control.point")
    crop_id = fields.Many2one("aifa.crop")
    subject_label = fields.Char(string="Affected Lot / Batch")
    intake_batch_id = fields.Many2one("aifa.intake.batch", ondelete="set null")
    dehydration_run_id = fields.Many2one("aifa.dehydration.run", ondelete="set null")
    lot_id = fields.Many2one("stock.lot", ondelete="set null")
    check_ids = fields.One2many("aifa.quality.check", "ncr_id", string="Triggering Checks")

    severity = fields.Selection(
        [("critical", "Critical - food safety"),
         ("major", "Major - specification"),
         ("minor", "Minor - cosmetic")],
        default="major", required=True, tracking=True,
    )
    quantity_affected_kg = fields.Float(digits=(12, 3))
    description = fields.Text(required=True)
    root_cause = fields.Text(tracking=True)
    root_cause_category = fields.Selection(
        [("equipment", "Equipment / Calibration"),
         ("method", "Method / Recipe"),
         ("material", "Incoming Material"),
         ("people", "Training / Human Error"),
         ("environment", "Environment / Utilities"),
         ("measurement", "Measurement System")],
        string="Root Cause Category", tracking=True,
    )
    disposition = fields.Selection(
        [("redry", "Re-dry"),
         ("rework", "Rework / Re-sort"),
         ("downgrade", "Downgrade to Foodservice / B-grade"),
         ("release", "Release under Concession"),
         ("dispose", "Destroy / Bio-waste Disposal"),
         ("return", "Return to Supplier")],
        tracking=True,
    )
    disposition_note = fields.Text()
    approved_by_id = fields.Many2one("res.users", string="Approved By", readonly=True,
                                     tracking=True)
    approved_date = fields.Datetime(readonly=True)

    corrective_action = fields.Text(help="What fixes this occurrence.")
    preventive_action = fields.Text(help="What stops it recurring.")
    capa_owner_id = fields.Many2one("res.users", string="CAPA Owner")
    capa_due_date = fields.Date()
    capa_done = fields.Boolean(string="CAPA Verified Effective", tracking=True)

    state = fields.Selection(
        [("open", "Open"), ("investigating", "Under Investigation"),
         ("disposed", "Disposition Agreed"), ("closed", "Closed"), ("cancel", "Cancelled")],
        default="open", tracking=True, index=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = self.env["ir.sequence"].next_by_code("aifa.ncr") or "New"
        return super().create(vals_list)

    def action_investigate(self):
        self.write({"state": "investigating"})

    def action_agree_disposition(self):
        for ncr in self:
            if not ncr.disposition:
                raise UserError(_("Choose a disposition for %s.") % ncr.name)
            if not ncr.root_cause:
                raise UserError(
                    _("Record the root cause of %s before agreeing a disposition. "
                      "A disposition without a root cause is how the same batch fails "
                      "again next month.") % ncr.name
                )
            ncr.write({
                "state": "disposed",
                "approved_by_id": self.env.user.id,
                "approved_date": fields.Datetime.now(),
            })
            ncr._apply_disposition()

    def action_close(self):
        for ncr in self:
            if ncr.state != "disposed":
                raise UserError(_("Agree the disposition on %s before closing it.") % ncr.name)
            if ncr.severity == "critical" and not ncr.preventive_action:
                raise UserError(
                    _("A critical NCR cannot be closed without a preventive action.")
                )
            ncr.state = "closed"

    def action_cancel(self):
        self.write({"state": "cancel"})

    def _apply_disposition(self):
        """Push the agreed disposition back onto the affected object."""
        for ncr in self:
            run = ncr.dehydration_run_id
            if ncr.disposition == "redry" and run:
                run.action_redry()
            elif ncr.disposition == "release" and run:
                run.write({"qa_blocked": False, "state": "unloaded"})
                run.message_post(
                    body=_("Released under concession %s, approved by %s.")
                    % (ncr.name, self.env.user.name)
                )
            elif ncr.disposition in ("dispose", "return"):
                if run:
                    run.write({"state": "cancel", "qa_blocked": True})
                if ncr.lot_id:
                    ncr.lot_id.aifa_quality_state = "rejected"
                if ncr.intake_batch_id and ncr.intake_batch_id.state == "received":
                    ncr.intake_batch_id.write({
                        "qa_note": ncr.disposition_note or ncr.description,
                    })
            elif ncr.disposition == "downgrade" and ncr.lot_id:
                ncr.lot_id.aifa_quality_state = "released"
                ncr.lot_id.message_post(
                    body=_("Downgraded under %s: sell as foodservice / B-grade only.") % ncr.name
                )
            ncr.message_post(
                body=_("Disposition <b>%s</b> applied. %s")
                % (dict(self._fields["disposition"].selection).get(ncr.disposition),
                   ncr.disposition_note or "")
            )
