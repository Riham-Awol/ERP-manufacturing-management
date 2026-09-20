# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError

GRADES = [
    ("a", "Grade A - Export / Prime Processing"),
    ("b", "Grade B - Standard Drying"),
    ("c", "Grade C - Salvage / Reject"),
]


class AifaGradePrice(models.Model):
    """Farm-gate price per crop and quality grade, with effective dating.

    Field agents must never key a free price at the depot: the price is
    resolved by the system from this matrix so that the purchase cost that
    lands in the product standard cost is auditable.
    """

    _name = "aifa.grade.price"
    _description = "Farm Gate Grade Price"
    _order = "crop_id, date_start desc, grade"

    crop_id = fields.Many2one("aifa.crop", required=True, ondelete="cascade")
    region_id = fields.Many2one(
        "aifa.region",
        help="Leave empty for a national price; a region-specific line wins over it.",
    )
    grade = fields.Selection(GRADES, required=True, default="a")
    price_per_kg = fields.Monetary(required=True, currency_field="currency_id")
    currency_id = fields.Many2one(
        "res.currency", default=lambda self: self.env.company.currency_id, required=True,
    )
    date_start = fields.Date(required=True, default=fields.Date.context_today)
    date_end = fields.Date()
    crate_deposit = fields.Monetary(
        string="Crate Deposit / Crate", currency_field="currency_id", default=0.0,
    )
    active = fields.Boolean(default=True)
    note = fields.Char()

    @api.model
    def resolve(self, crop, grade, region=None, date=None):
        """Return the applicable price record, region-specific first."""
        date = date or fields.Date.context_today(self)
        base = [
            ("crop_id", "=", crop.id), ("grade", "=", grade),
            ("date_start", "<=", date),
            "|", ("date_end", "=", False), ("date_end", ">=", date),
        ]
        if region:
            found = self.search(base + [("region_id", "=", region.id)], limit=1)
            if found:
                return found
        return self.search(base + [("region_id", "=", False)], limit=1)

    @api.model
    def price_for(self, crop, grade, region=None, date=None):
        rec = self.resolve(crop, grade, region=region, date=date)
        if not rec:
            raise UserError(
                _("No farm-gate price is configured for %(crop)s grade %(grade)s on %(date)s. "
                  "Configuration > Master Data > Grade Prices.")
                % {"crop": crop.display_name, "grade": grade.upper(),
                   "date": date or fields.Date.context_today(self)}
            )
        return rec.price_per_kg
