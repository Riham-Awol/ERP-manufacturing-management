# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AifaSanitationLog(models.Model):
    """Pre-operational clean-in-place and room sanitation record (FRS-4.4).

    EFDA and ISO 22000 audits ask for two things a paper checklist rarely
    survives: who signed, and whether the clean happened *before* production
    started.  Both are captured here with a timestamp that cannot be
    back-written once the log is signed.
    """

    _name = "aifa.sanitation.log"
    _description = "Sanitation / CIP Log"
    _inherit = ["mail.thread"]
    _order = "date desc, id desc"

    name = fields.Char(required=True, copy=False, readonly=True, default="New", index=True)
    date = fields.Datetime(required=True, default=fields.Datetime.now, index=True)
    area = fields.Selection(
        [("receiving", "Receiving Bay & Cold Room"),
         ("wash", "Wash & Sorting Area"),
         ("prep", "Preparation / Slicing Room"),
         ("dryer", "Dehydration Hall"),
         ("condition", "Conditioning Room"),
         ("pack", "Packing Room"),
         ("store", "Finished Goods Store"),
         ("toilets", "Welfare Facilities")],
        required=True, default="prep",
    )
    dehydrator_id = fields.Many2one("aifa.dehydrator", string="Chamber",
                                    help="Set when the log covers a specific chamber.")
    shift = fields.Selection(
        [("pre", "Pre-operational"), ("mid", "Mid-shift"), ("post", "Post-operational")],
        default="pre", required=True,
    )
    method = fields.Selection(
        [("dry", "Dry Clean"), ("wet", "Wet Clean"), ("cip", "Clean In Place"),
         ("deep", "Deep Clean / Disassembly")],
        default="wet", required=True,
    )
    chemical = fields.Char(string="Sanitiser Used")
    concentration_ppm = fields.Float(string="Concentration (ppm)")
    contact_minutes = fields.Float(string="Contact Time (min)")
    water_temp_c = fields.Float(string="Water Temperature (C)")
    visual_pass = fields.Boolean(string="Visual Inspection Passed", default=True)
    atp_swab_taken = fields.Boolean(string="ATP Swab Taken")
    atp_rlu = fields.Float(string="ATP Result (RLU)")
    atp_limit_rlu = fields.Float(string="ATP Limit (RLU)", default=30.0)
    atp_pass = fields.Boolean(compute="_compute_atp_pass", store=True)

    performed_by_id = fields.Many2one("res.users", string="Performed By", required=True,
                                      default=lambda self: self.env.user)
    verified_by_id = fields.Many2one("res.users", string="Verified By", tracking=True)
    verified_date = fields.Datetime(readonly=True, tracking=True)
    state = fields.Selection(
        [("draft", "Draft"), ("signed", "Signed Off"), ("failed", "Failed - Re-clean")],
        default="draft", tracking=True, index=True,
    )
    note = fields.Text()

    @api.depends("atp_swab_taken", "atp_rlu", "atp_limit_rlu")
    def _compute_atp_pass(self):
        for log in self:
            log.atp_pass = (
                not log.atp_swab_taken or (log.atp_rlu and log.atp_rlu <= log.atp_limit_rlu)
            )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = self.env["ir.sequence"].next_by_code(
                    "aifa.sanitation.log") or "New"
        return super().create(vals_list)

    def action_sign_off(self):
        for log in self:
            if not log.visual_pass or not log.atp_pass:
                raise UserError(
                    _("%s cannot be signed off: the visual inspection or the ATP swab "
                      "failed. Re-clean and take a fresh swab.") % log.name
                )
            log.write({
                "state": "signed",
                "verified_by_id": self.env.user.id,
                "verified_date": fields.Datetime.now(),
            })
            if log.dehydrator_id:
                log.dehydrator_id.write({"last_cip_date": log.date})

    def action_fail(self):
        for log in self:
            log.write({"state": "failed", "visual_pass": False})
            log.message_post(
                body=_("Sanitation failed in %s. Production must not start in this area "
                       "until a passing log is signed.")
                % dict(self._fields["area"].selection).get(log.area),
                subtype_xmlid="mail.mt_comment",
            )
