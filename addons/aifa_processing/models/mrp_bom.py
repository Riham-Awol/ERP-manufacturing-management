# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from .aifa_stage import PROCESS_STAGES


class MrpBom(models.Model):
    """Tag each BOM with its processing stage (FRS-2.1).

    Aifa's product chain is deliberately three separate BOMs rather than one
    exploded multi-level BOM, because each stage is physically buffered: prepped
    fruit waits for a free chamber, dried bulk waits for conditioning and a
    moisture result.  Stock must exist between them, so each stage gets its own
    manufacturing order and its own lot.
    """

    _inherit = "mrp.bom"

    aifa_stage = fields.Selection(
        PROCESS_STAGES, string="Processing Stage", index=True,
        help="Tags the BOM as preparation, dehydration or packing.",
    )
    aifa_crop_id = fields.Many2one("aifa.crop", string="Crop")
    aifa_expected_yield_pct = fields.Float(
        string="Expected Stage Yield (%)", compute="_compute_expected_yield", store=True,
        digits=(5, 2),
        help="Derived from the crop standards, for quick comparison against the "
             "quantities actually written on the BOM lines.",
    )
    aifa_version = fields.Char(string="Recipe Version", default="1.0", tracking=True)
    aifa_change_note = fields.Text(
        string="Engineering Change Note",
        help="FRS-2.5: why this version differs from the previous one (seasonal sugar "
             "content, new cultivar, packaging change).",
    )
    aifa_approved_by = fields.Many2one("res.users", string="Approved By", tracking=True)
    aifa_approved_date = fields.Date(tracking=True)

    @api.depends("aifa_stage", "aifa_crop_id.prep_yield_pct", "aifa_crop_id.dry_yield_pct")
    def _compute_expected_yield(self):
        for bom in self:
            crop = bom.aifa_crop_id
            if not crop:
                bom.aifa_expected_yield_pct = 0.0
            elif bom.aifa_stage == "prep":
                bom.aifa_expected_yield_pct = crop.prep_yield_pct
            elif bom.aifa_stage == "dry":
                bom.aifa_expected_yield_pct = crop.dry_yield_pct
            else:
                bom.aifa_expected_yield_pct = 100.0

    def action_approve_recipe(self):
        """Engineering change sign-off (FRS-2.5)."""
        self.write({
            "aifa_approved_by": self.env.user.id,
            "aifa_approved_date": fields.Date.context_today(self),
        })
        for bom in self:
            bom.message_post(
                body=_("Recipe version %s approved by %s.")
                % (bom.aifa_version, self.env.user.name)
            )

    @api.constrains("aifa_stage", "type")
    def _check_stage_type(self):
        for bom in self:
            if bom.aifa_stage and bom.type == "phantom":
                raise ValidationError(
                    _("A staged Aifa BOM cannot be a kit: each stage must produce real "
                      "stock and a real lot so the genealogy is preserved.")
                )


class MrpBomLine(models.Model):
    _inherit = "mrp.bom.line"

    aifa_is_primary = fields.Boolean(
        string="Primary Ingredient",
        help="Marks the fruit component as opposed to packaging, so yield reporting "
             "measures fruit against fruit.",
    )
