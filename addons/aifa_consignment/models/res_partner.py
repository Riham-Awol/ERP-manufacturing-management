# -*- coding: utf-8 -*-
from odoo import _, api, fields, models


class ResPartner(models.Model):
    """Retail channel attributes for supermarket, café and hotel accounts."""

    _inherit = "res.partner"

    aifa_channel = fields.Selection(
        [("supermarket", "Supermarket Chain"),
         ("boutique", "Specialty / Health Boutique"),
         ("cafe", "Café & Coffee Chain"),
         ("hotel", "Hotel & Hospitality"),
         ("ecommerce", "E-commerce / Delivery Platform"),
         ("institutional", "Institutional / Foodservice"),
         ("export", "Export Buyer"),
         ("outgrower", "Outgrower / Supplier")],
        string="Aifa Channel", index=True,
    )
    aifa_is_consignment = fields.Boolean(
        string="Consignment Partner",
        help="Stock delivered to this partner stays on Aifa's balance sheet until a "
             "shelf count confirms it was sold.",
    )
    aifa_consignment_location_id = fields.Many2one(
        "stock.location", string="Consignment Location",
        help="Internal location representing this partner's shelf stock. Created "
             "automatically the first time stock is placed.",
    )
    aifa_shelf_count_days = fields.Integer(
        string="Shelf Count Every (days)", default=14,
        help="How often a merchandiser is expected to count this partner's shelf.",
    )
    aifa_consignment_ids = fields.One2many(
        "aifa.consignment", "partner_id", string="Consignment Placements",
    )
    aifa_shelf_balance_units = fields.Float(
        compute="_compute_shelf_balance", string="Units on Shelf", digits=(12, 2),
    )
    aifa_shelf_value = fields.Monetary(
        compute="_compute_shelf_balance", string="Value on Shelf", currency_field="currency_id",
    )

    @api.depends("aifa_consignment_ids.balance_units", "aifa_consignment_ids.state")
    def _compute_shelf_balance(self):
        for partner in self:
            open_placements = partner.aifa_consignment_ids.filtered(
                lambda c: c.state in ("placed", "counted")
            )
            partner.aifa_shelf_balance_units = sum(open_placements.mapped("balance_units"))
            partner.aifa_shelf_value = sum(
                p.balance_units * p.unit_price for p in open_placements
            )

    def _aifa_get_consignment_location(self):
        """Return (creating if needed) the internal location holding this partner's shelf."""
        self.ensure_one()
        if self.aifa_consignment_location_id:
            return self.aifa_consignment_location_id
        parent = self.env.ref(
            "aifa_consignment.stock_location_consignment_root", raise_if_not_found=False
        )
        if not parent:
            warehouse = self.env["stock.warehouse"].search(
                [("company_id", "=", self.env.company.id)], limit=1
            )
            parent = warehouse.view_location_id
        location = self.env["stock.location"].create({
            "name": self.name,
            "location_id": parent.id,
            "usage": "internal",
            "company_id": self.env.company.id,
        })
        self.aifa_consignment_location_id = location
        return location

    def action_view_consignments(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Consignment at %s") % self.name,
            "res_model": "aifa.consignment",
            "view_mode": "tree,form",
            "domain": [("partner_id", "=", self.id)],
            "context": {"default_partner_id": self.id},
        }
