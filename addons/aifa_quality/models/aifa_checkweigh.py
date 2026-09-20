# -*- coding: utf-8 -*-
import statistics

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AifaCheckweighSession(models.Model):
    """Statistical check-weighing on the pouch line (FRS-3.5).

    Two different questions are answered here and it matters that they are kept
    apart:

    * *Is the line giving product away?* - the mean fill against the target.
    * *Is any individual pouch short?* - the tolerable negative error (TNE)
      rule, which for a 35 g or 100 g pack allows a small number of packs below
      nominal but none below twice the TNE.
    """

    _name = "aifa.checkweigh.session"
    _description = "Check-Weighing Session"
    _inherit = ["mail.thread"]
    _order = "date desc, id desc"

    name = fields.Char(compute="_compute_name", store=True)
    date = fields.Datetime(required=True, default=fields.Datetime.now, index=True)
    production_id = fields.Many2one("mrp.production", string="Packing Order",
                                    domain="[('aifa_stage', '=', 'pack')]")
    product_id = fields.Many2one("product.product", required=True,
                                 domain="[('type', '=', 'product')]")
    lot_id = fields.Many2one("stock.lot", string="Finished Lot",
                             domain="[('product_id', '=', product_id)]")
    operator_id = fields.Many2one("res.users", default=lambda self: self.env.user)
    scale_serial = fields.Char(string="Bench Scale ID")

    nominal_weight_g = fields.Float(string="Declared Weight (g)", required=True, digits=(8, 2))
    target_fill_g = fields.Float(
        string="Target Fill (g)", digits=(8, 2),
        help="The set point the line aims at, normally a little above the declared weight "
             "so that the average-content rule is met after seal trim losses.",
    )
    tne_g = fields.Float(string="Tolerable Negative Error (g)", compute="_compute_tne",
                         store=True, digits=(8, 2))
    sample_ids = fields.One2many("aifa.checkweigh.sample", "session_id", string="Samples")

    sample_count = fields.Integer(compute="_compute_stats", store=True)
    mean_g = fields.Float(compute="_compute_stats", store=True, digits=(8, 3))
    stdev_g = fields.Float(compute="_compute_stats", store=True, digits=(8, 3))
    min_g = fields.Float(compute="_compute_stats", store=True, digits=(8, 3))
    max_g = fields.Float(compute="_compute_stats", store=True, digits=(8, 3))
    giveaway_g = fields.Float(compute="_compute_stats", store=True, digits=(8, 3),
                              string="Giveaway per Pack (g)")
    giveaway_pct = fields.Float(compute="_compute_stats", store=True, digits=(5, 2))
    under_t1_count = fields.Integer(compute="_compute_stats", store=True,
                                    string="Packs below 1x TNE")
    under_t2_count = fields.Integer(compute="_compute_stats", store=True,
                                    string="Packs below 2x TNE")
    cpk = fields.Float(compute="_compute_stats", store=True, digits=(6, 3),
                       help="Process capability against the declared weight as the lower "
                            "specification limit. Below 1.33 the line needs attention.")
    verdict = fields.Selection(
        [("pending", "Pending"), ("pass", "Compliant"),
         ("adjust", "Adjust Line"), ("fail", "Non-Compliant")],
        compute="_compute_stats", store=True, default="pending", tracking=True,
    )
    note = fields.Text()
    state = fields.Selection(
        [("draft", "Draft"), ("done", "Closed")], default="draft", tracking=True,
    )

    @api.depends("product_id", "date")
    def _compute_name(self):
        for session in self:
            session.name = "CW/%s/%s" % (
                session.product_id.default_code or session.product_id.name or "?",
                fields.Datetime.to_string(session.date or fields.Datetime.now())[:16],
            )

    @api.depends("nominal_weight_g")
    def _compute_tne(self):
        """Tolerable negative error bands from the standard prepackaged-goods table."""
        for session in self:
            nominal = session.nominal_weight_g
            if nominal <= 0:
                session.tne_g = 0.0
            elif nominal <= 50:
                session.tne_g = nominal * 0.09
            elif nominal <= 100:
                session.tne_g = 4.5
            elif nominal <= 200:
                session.tne_g = nominal * 0.045
            elif nominal <= 300:
                session.tne_g = 9.0
            elif nominal <= 500:
                session.tne_g = nominal * 0.03
            else:
                session.tne_g = 15.0

    @api.depends("sample_ids.weight_g", "nominal_weight_g", "target_fill_g", "tne_g")
    def _compute_stats(self):
        for session in self:
            weights = session.sample_ids.mapped("weight_g")
            session.sample_count = len(weights)
            if not weights:
                session.mean_g = session.stdev_g = session.min_g = session.max_g = 0.0
                session.giveaway_g = session.giveaway_pct = session.cpk = 0.0
                session.under_t1_count = session.under_t2_count = 0
                session.verdict = "pending"
                continue
            session.mean_g = statistics.fmean(weights)
            session.stdev_g = statistics.stdev(weights) if len(weights) > 1 else 0.0
            session.min_g = min(weights)
            session.max_g = max(weights)
            nominal = session.nominal_weight_g
            session.giveaway_g = session.mean_g - nominal
            session.giveaway_pct = (session.giveaway_g / nominal * 100.0) if nominal else 0.0
            t1 = nominal - session.tne_g
            t2 = nominal - 2 * session.tne_g
            session.under_t1_count = len([w for w in weights if w < t1])
            session.under_t2_count = len([w for w in weights if w < t2])
            session.cpk = (
                (session.mean_g - nominal) / (3 * session.stdev_g)
                if session.stdev_g else 0.0
            )
            if session.under_t2_count or session.mean_g < nominal:
                session.verdict = "fail"
            elif session.under_t1_count > max(1, len(weights) // 20) or (
                    session.stdev_g and session.cpk < 1.0):
                session.verdict = "adjust"
            else:
                session.verdict = "pass"

    @api.onchange("product_id")
    def _onchange_product(self):
        if self.product_id and self.product_id.weight:
            self.nominal_weight_g = self.product_id.weight * 1000.0
            self.target_fill_g = self.nominal_weight_g * 1.02

    def action_close(self):
        for session in self:
            if session.sample_count < 5:
                raise UserError(
                    _("Take at least five samples before closing %s; the standard deviation "
                      "is meaningless below that.") % session.name
                )
            session.state = "done"
            if session.verdict in ("fail", "adjust"):
                session.message_post(
                    body=_("<b>Check-weigh verdict: %(v)s.</b> Mean %(mean).2f g against a "
                           "%(nom).2f g declared weight; %(u1)s pack(s) below 1x TNE and "
                           "%(u2)s below 2x TNE. Adjust the filler set point before the "
                           "next carton.")
                    % {"v": dict(session._fields["verdict"].selection).get(session.verdict),
                       "mean": session.mean_g, "nom": session.nominal_weight_g,
                       "u1": session.under_t1_count, "u2": session.under_t2_count},
                    subtype_xmlid="mail.mt_comment",
                )


class AifaCheckweighSample(models.Model):
    _name = "aifa.checkweigh.sample"
    _description = "Check-Weighing Sample"
    _order = "session_id, sequence, id"

    session_id = fields.Many2one("aifa.checkweigh.session", required=True, ondelete="cascade")
    sequence = fields.Integer(default=10)
    weight_g = fields.Float(required=True, digits=(8, 3))
    seal_ok = fields.Boolean(string="Seal Integrity OK", default=True)
    taken_at = fields.Datetime(default=fields.Datetime.now)
    deviation_g = fields.Float(compute="_compute_deviation", digits=(8, 3))

    @api.depends("weight_g", "session_id.nominal_weight_g")
    def _compute_deviation(self):
        for sample in self:
            sample.deviation_g = sample.weight_g - sample.session_id.nominal_weight_g
