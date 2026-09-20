# -*- coding: utf-8 -*-
from odoo import api, fields, models


class AifaRegion(models.Model):
    """Rural sourcing region (Gamo/Arba Minch, Sidama, Afar, Rift Valley...).

    Regions drive the geography segment of the raw-intake lot number and are
    the reporting dimension used by the P4G / CARE impact dashboards.
    """

    _name = "aifa.region"
    _description = "Aifa Sourcing Region"
    _order = "sequence, name"

    name = fields.Char(required=True, translate=True)
    code = fields.Char(
        required=True,
        size=4,
        help="Short uppercase code embedded in raw intake lot numbers, e.g. GMA for Gamo.",
    )
    sequence = fields.Integer(default=10)
    country_id = fields.Many2one(
        "res.country",
        default=lambda self: self.env.ref("base.et", raise_if_not_found=False),
    )
    state_id = fields.Many2one("res.country.state", domain="[('country_id', '=', country_id)]")
    gps_lat = fields.Float(string="Latitude", digits=(10, 6))
    gps_lng = fields.Float(string="Longitude", digits=(10, 6))
    notes = fields.Text()
    active = fields.Boolean(default=True)

    collection_centre_ids = fields.One2many(
        "aifa.collection.centre", "region_id", string="Collection Centres"
    )
    collection_centre_count = fields.Integer(compute="_compute_collection_centre_count")

    _sql_constraints = [
        ("code_uniq", "unique(code)", "The region code must be unique."),
    ]

    @api.depends("collection_centre_ids")
    def _compute_collection_centre_count(self):
        for region in self:
            region.collection_centre_count = len(region.collection_centre_ids)

    @api.onchange("code")
    def _onchange_code(self):
        if self.code:
            self.code = self.code.strip().upper()


class AifaCollectionCentre(models.Model):
    """Rural aggregation depot where field agents weigh and buy fresh fruit."""

    _name = "aifa.collection.centre"
    _description = "Aifa Rural Collection Centre"
    _order = "region_id, name"

    name = fields.Char(required=True)
    code = fields.Char(required=True, size=6)
    region_id = fields.Many2one("aifa.region", required=True, ondelete="restrict")
    agent_ids = fields.Many2many("res.users", string="Field Agents")
    warehouse_id = fields.Many2one(
        "stock.warehouse",
        string="Depot Warehouse",
        help="Optional Odoo warehouse representing the physical depot stock.",
    )
    gps_lat = fields.Float(string="Latitude", digits=(10, 6))
    gps_lng = fields.Float(string="Longitude", digits=(10, 6))
    has_cold_room = fields.Boolean(string="Cold Room Available")
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ("code_uniq", "unique(code)", "The collection centre code must be unique."),
    ]

    @api.depends("name", "region_id.code")
    def _compute_display_name(self):
        for centre in self:
            centre.display_name = "%s / %s" % (centre.region_id.code or "-", centre.name or "")
