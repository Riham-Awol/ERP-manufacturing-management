# -*- coding: utf-8 -*-
import base64
import csv
import io

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AifaFarmerPayout(models.Model):
    """Payout run settling accepted intake batches to outgrowers (FRS-1.6).

    A payout groups every accepted, not-yet-paid intake batch for a farmer over
    a period, nets off input advances and unreturned crate deposits, and can be
    exported as a bulk mobile-money file for Telebirr / CBE Birr.
    """

    _name = "aifa.farmer.payout"
    _description = "Outgrower Payout"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date desc, id desc"

    name = fields.Char(required=True, copy=False, readonly=True, default="New", index=True)
    farmer_id = fields.Many2one("aifa.farmer", required=True, tracking=True)
    partner_id = fields.Many2one(related="farmer_id.partner_id", store=True, readonly=True)
    date = fields.Date(required=True, default=fields.Date.context_today, tracking=True)
    period_start = fields.Date(required=True)
    period_end = fields.Date(required=True, default=fields.Date.context_today)
    intake_ids = fields.One2many("aifa.intake.batch", "payout_id", string="Intake Batches")

    gross_amount = fields.Monetary(compute="_compute_amounts", store=True,
                                   currency_field="currency_id")
    total_kg = fields.Float(compute="_compute_amounts", store=True, digits=(12, 3))
    advance_deduction = fields.Monetary(currency_field="currency_id", tracking=True)
    crate_deduction = fields.Monetary(currency_field="currency_id", tracking=True)
    other_deduction = fields.Monetary(currency_field="currency_id")
    other_deduction_note = fields.Char()
    net_amount = fields.Monetary(compute="_compute_amounts", store=True,
                                 currency_field="currency_id", tracking=True)
    currency_id = fields.Many2one(
        "res.currency", default=lambda self: self.env.company.currency_id, readonly=True,
    )
    payout_method = fields.Selection(related="farmer_id.payout_method", readonly=False, store=True)
    wallet_number = fields.Char(related="farmer_id.wallet_number", readonly=True)
    transaction_ref = fields.Char(string="Payment Reference", copy=False, tracking=True)
    state = fields.Selection(
        [("draft", "Draft"), ("approved", "Approved"),
         ("paid", "Paid"), ("cancel", "Cancelled")],
        default="draft", tracking=True, copy=False,
    )
    note = fields.Text()

    @api.depends("intake_ids.amount_total", "intake_ids.accepted_weight_kg",
                 "advance_deduction", "crate_deduction", "other_deduction")
    def _compute_amounts(self):
        for payout in self:
            payout.gross_amount = sum(payout.intake_ids.mapped("amount_total"))
            payout.total_kg = sum(payout.intake_ids.mapped("accepted_weight_kg"))
            payout.net_amount = payout.gross_amount - (
                payout.advance_deduction + payout.crate_deduction + payout.other_deduction
            )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = self.env["ir.sequence"].next_by_code("aifa.farmer.payout") or "New"
        return super().create(vals_list)

    def action_collect_intakes(self):
        """Pull every unpaid accepted intake of the farmer in the period."""
        for payout in self:
            batches = self.env["aifa.intake.batch"].search([
                ("farmer_id", "=", payout.farmer_id.id),
                ("state", "in", ("accepted", "done")),
                ("payout_id", "=", False),
                ("intake_date", ">=", payout.period_start),
                ("intake_date", "<=", payout.period_end),
            ])
            if not batches:
                raise UserError(
                    _("No unpaid accepted intake found for %s in that period.")
                    % payout.farmer_id.name
                )
            batches.write({"payout_id": payout.id})
            if not payout.advance_deduction:
                payout.advance_deduction = min(
                    payout.farmer_id.advance_balance, payout.gross_amount
                )
        return True

    def action_approve(self):
        for payout in self:
            if payout.state != "draft":
                raise UserError(_("Only a draft payout can be approved."))
            if not payout.intake_ids:
                raise UserError(_("Attach at least one intake batch before approving."))
            if payout.net_amount < 0:
                raise UserError(
                    _("Deductions exceed the gross amount on %s; split the advance recovery "
                      "across several payouts.") % payout.name
                )
            payout.state = "approved"

    def action_mark_paid(self):
        for payout in self:
            if payout.state != "approved":
                raise UserError(_("Approve the payout before marking it paid."))
            if not payout.transaction_ref:
                raise UserError(_("Record the mobile-money or bank reference on %s.") % payout.name)
            payout.state = "paid"
            farmer = payout.farmer_id
            farmer.advance_balance = max(farmer.advance_balance - payout.advance_deduction, 0.0)
            payout.message_post(
                body=_("Paid %(amt)s via %(method)s, reference %(ref)s.")
                % {"amt": payout.net_amount, "method": payout.payout_method,
                   "ref": payout.transaction_ref}
            )

    def action_cancel(self):
        for payout in self:
            if payout.state == "paid":
                raise UserError(_("A paid payout cannot be cancelled; register a refund instead."))
            payout.intake_ids.write({"payout_id": False})
            payout.state = "cancel"

    def action_export_wallet_file(self):
        """Produce a bulk mobile-money CSV for the approved payouts in ``self``."""
        approved = self.filtered(lambda p: p.state == "approved")
        if not approved:
            raise UserError(_("Select at least one approved payout to export."))
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["payout_ref", "farmer_ref", "farmer_name", "method",
                         "wallet_number", "amount", "currency", "narrative"])
        for payout in approved:
            writer.writerow([
                payout.name, payout.farmer_id.ref, payout.farmer_id.name,
                payout.payout_method, payout.wallet_number or "",
                "%.2f" % payout.net_amount, payout.currency_id.name,
                "Aifa Foods fruit purchase %s" % payout.name,
            ])
        attachment = self.env["ir.attachment"].create({
            "name": "aifa_payouts_%s.csv" % fields.Date.today(),
            "type": "binary",
            "datas": base64.b64encode(buf.getvalue().encode("utf-8")),
            "mimetype": "text/csv",
        })
        return {
            "type": "ir.actions.act_url",
            "url": "/web/content/%s?download=true" % attachment.id,
            "target": "self",
        }
