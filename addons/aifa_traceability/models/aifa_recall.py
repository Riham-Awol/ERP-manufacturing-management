# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AifaRecall(models.Model):
    """Recall simulation or live recall (FRS-4.5).

    The same record serves the drill and the real event on purpose: a drill
    that uses a different procedure from the real thing proves nothing. What
    distinguishes them is the ``is_drill`` flag and whether notifications go out.
    """

    _name = "aifa.recall"
    _description = "Recall / Traceability Exercise"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date desc, id desc"

    name = fields.Char(required=True, copy=False, readonly=True, default="New", index=True)
    date = fields.Datetime(required=True, default=fields.Datetime.now, tracking=True)
    is_drill = fields.Boolean(
        string="Mock Recall (drill)", default=True, tracking=True,
        help="A drill runs the identical trace but sends no customer notification.",
    )
    reason = fields.Selection(
        [("moisture", "Out-of-spec moisture / water activity"),
         ("foreign", "Foreign body"),
         ("allergen", "Allergen or labelling error"),
         ("microbio", "Microbiological result"),
         ("complaint", "Consumer complaint"),
         ("drill", "Scheduled traceability exercise")],
        required=True, default="drill", tracking=True,
    )
    description = fields.Text(required=True, default="Scheduled quarterly traceability exercise.")
    initiated_by_id = fields.Many2one("res.users", required=True,
                                      default=lambda self: self.env.user)

    # ----- the starting point: exactly one of these -----
    intake_batch_id = fields.Many2one("aifa.intake.batch", string="Suspect Intake Lot")
    dehydration_run_id = fields.Many2one("aifa.dehydration.run", string="Suspect Drying Run")
    lot_id = fields.Many2one("stock.lot", string="Suspect Lot")

    # ----- results -----
    affected_lot_ids = fields.Many2many("stock.lot", string="Affected Lots", readonly=True)
    affected_lot_count = fields.Integer(compute="_compute_counts", store=True)
    line_ids = fields.One2many("aifa.recall.line", "recall_id", string="Distribution Reached",
                               readonly=True)
    customer_count = fields.Integer(compute="_compute_counts", store=True)
    total_units = fields.Float(compute="_compute_counts", store=True, digits=(12, 3))
    trace_seconds = fields.Float(
        string="Trace Duration (s)", readonly=True, digits=(6, 2),
        help="How long the system took to resolve the trace. Audits ask for this; the "
             "target in the FRS is under four hours, the system does it in seconds.",
    )
    state = fields.Selection(
        [("draft", "Draft"), ("traced", "Traced"),
         ("notified", "Customers Notified"), ("closed", "Closed")],
        default="draft", tracking=True,
    )
    conclusion = fields.Text()

    @api.depends("affected_lot_ids", "line_ids.quantity")
    def _compute_counts(self):
        for recall in self:
            recall.affected_lot_count = len(recall.affected_lot_ids)
            recall.customer_count = len(recall.line_ids.mapped("partner_id"))
            recall.total_units = sum(recall.line_ids.mapped("quantity"))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = self.env["ir.sequence"].next_by_code("aifa.recall") or "New"
        return super().create(vals_list)

    def action_run_trace(self):
        """Resolve every finished lot and delivery that descends from the suspect."""
        for recall in self:
            start = fields.Datetime.now()
            seeds = recall._resolve_seed_lots()
            if not seeds:
                raise UserError(
                    _("Nothing to trace: the suspect intake lot, drying run or stock lot "
                      "has no stock lot attached yet.")
                )
            family = seeds
            for lot in seeds:
                family |= lot._collect_descendants()
            recall.line_ids.unlink()
            lines = []
            for lot in family:
                for move_line in lot.aifa_downstream_moves():
                    lines.append((0, 0, {
                        "lot_id": lot.id,
                        "partner_id": (move_line.picking_id.partner_id.id
                                       or move_line.move_id.partner_id.id or False),
                        "picking_id": move_line.picking_id.id,
                        "product_id": move_line.product_id.id,
                        "quantity": move_line.quantity,
                        "date": move_line.date,
                    }))
            recall.write({
                "affected_lot_ids": [(6, 0, family.ids)],
                "line_ids": lines,
                "state": "traced",
                "trace_seconds": (fields.Datetime.now() - start).total_seconds(),
            })
            recall.message_post(
                body=_("Trace complete in %(s).2f s: %(lots)s lot(s) reaching "
                       "%(cust)s customer destination(s).")
                % {"s": recall.trace_seconds, "lots": len(family),
                   "cust": recall.customer_count}
            )
        return True

    def _resolve_seed_lots(self):
        self.ensure_one()
        lots = self.env["stock.lot"]
        if self.lot_id:
            lots |= self.lot_id
        if self.intake_batch_id.lot_id:
            lots |= self.intake_batch_id.lot_id
        if self.dehydration_run_id.wip_lot_code:
            lots |= self.env["stock.lot"].search(
                [("name", "=", self.dehydration_run_id.wip_lot_code)]
            )
        return lots

    def action_quarantine_affected(self):
        for recall in self:
            if recall.state == "draft":
                raise UserError(_("Run the trace before quarantining."))
            recall.affected_lot_ids.write({"aifa_quality_state": "quarantine"})
            recall.message_post(
                body=_("%s affected lot(s) placed on quarantine hold.")
                % len(recall.affected_lot_ids)
            )

    def action_notify_customers(self):
        for recall in self:
            if recall.is_drill:
                raise UserError(
                    _("%s is a drill. Untick 'Mock Recall' only when this is a real event: "
                      "notifying a supermarket chain in error is its own incident.")
                    % recall.name
                )
            partners = recall.line_ids.mapped("partner_id")
            for partner in partners:
                recall.message_post(
                    body=_("Recall notice prepared for %s.") % partner.display_name,
                    partner_ids=[partner.id],
                    subtype_xmlid="mail.mt_comment",
                )
            recall.state = "notified"

    def action_close(self):
        for recall in self:
            if not recall.conclusion:
                raise UserError(
                    _("Record the conclusion of %s. For a drill this is where the "
                      "effectiveness percentage and the lessons learned belong.")
                    % recall.name
                )
            recall.state = "closed"


class AifaRecallLine(models.Model):
    _name = "aifa.recall.line"
    _description = "Recall Distribution Line"
    _order = "recall_id, date desc"

    recall_id = fields.Many2one("aifa.recall", required=True, ondelete="cascade")
    lot_id = fields.Many2one("stock.lot", required=True)
    product_id = fields.Many2one("product.product")
    partner_id = fields.Many2one("res.partner", string="Customer / Destination")
    picking_id = fields.Many2one("stock.picking", string="Delivery")
    quantity = fields.Float(digits=(12, 3))
    date = fields.Datetime()
    recovered = fields.Boolean(string="Stock Recovered")
    recovery_note = fields.Char()
