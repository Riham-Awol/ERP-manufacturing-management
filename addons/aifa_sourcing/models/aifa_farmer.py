# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class AifaCooperative(models.Model):
    _name = "aifa.cooperative"
    _description = "Outgrower Cooperative / Farmer Group"
    _inherit = ["mail.thread"]
    _order = "name"

    name = fields.Char(required=True, tracking=True)
    code = fields.Char(required=True, size=8)
    region_id = fields.Many2one("aifa.region", required=True)
    centre_id = fields.Many2one(
        "aifa.collection.centre", string="Primary Collection Centre",
        domain="[('region_id', '=', region_id)]",
    )
    chairperson = fields.Char()
    phone = fields.Char()
    partner_id = fields.Many2one(
        "res.partner", string="Payment Counterparty",
        help="Used when payouts are settled to the cooperative rather than to each farmer.",
    )
    farmer_ids = fields.One2many("aifa.farmer", "cooperative_id", string="Members")
    farmer_count = fields.Integer(compute="_compute_farmer_count")
    female_member_ratio = fields.Float(
        compute="_compute_farmer_count", string="Female Members (%)", digits=(5, 2),
    )
    active = fields.Boolean(default=True)

    _sql_constraints = [("code_uniq", "unique(code)", "Cooperative code must be unique.")]

    @api.depends("farmer_ids", "farmer_ids.gender")
    def _compute_farmer_count(self):
        for coop in self:
            farmers = coop.farmer_ids
            coop.farmer_count = len(farmers)
            female = len(farmers.filtered(lambda f: f.gender == "female"))
            coop.female_member_ratio = (female / len(farmers) * 100.0) if farmers else 0.0


class AifaFarmer(models.Model):
    """Smallholder outgrower supplying fresh fruit at the farm gate.

    A farmer is backed by a ``res.partner`` so that payouts, purchase orders
    and accounting all reuse standard Odoo plumbing, while the agronomic and
    impact-reporting attributes live here.
    """

    _name = "aifa.farmer"
    _description = "Aifa Outgrower"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "name"

    name = fields.Char(required=True, tracking=True)
    ref = fields.Char(string="Outgrower Ref", copy=False, readonly=True, index=True)
    partner_id = fields.Many2one(
        "res.partner", string="Partner", required=True, ondelete="restrict", copy=False,
        help="Accounting counterparty automatically created from the outgrower record.",
    )
    cooperative_id = fields.Many2one("aifa.cooperative", tracking=True)
    region_id = fields.Many2one("aifa.region", required=True, tracking=True)
    centre_id = fields.Many2one(
        "aifa.collection.centre", string="Collection Centre",
        domain="[('region_id', '=', region_id)]",
    )
    kebele = fields.Char(string="Kebele / Woreda")
    national_id = fields.Char(string="National / Kebele ID", groups="aifa_base.group_aifa_manager")
    phone = fields.Char()
    gender = fields.Selection(
        [("female", "Female"), ("male", "Male"), ("other", "Other")],
        default="female", tracking=True,
        help="Tracked for the P4G / CARE gender-disaggregated impact reporting.",
    )
    household_size = fields.Integer()
    date_registered = fields.Date(default=fields.Date.context_today)
    payout_method = fields.Selection(
        [("telebirr", "Telebirr"), ("cbebirr", "CBE Birr"), ("bank", "Bank Transfer"),
         ("cash", "Cash at Depot"), ("coop", "Via Cooperative")],
        default="telebirr", required=True,
    )
    wallet_number = fields.Char(string="Mobile Wallet / Account")
    crop_ids = fields.Many2many("aifa.crop", string="Crops Supplied")
    plot_ids = fields.One2many("aifa.farmer.plot", "farmer_id", string="Plots")
    total_hectares = fields.Float(compute="_compute_plot_totals", store=True, digits=(8, 3))
    plot_count = fields.Integer(compute="_compute_plot_totals", store=True)
    certification = fields.Selection(
        [("none", "None"), ("organic_conv", "Organic (in conversion)"),
         ("organic", "Certified Organic"), ("globalgap", "GlobalG.A.P.")],
        default="none",
    )
    advance_balance = fields.Monetary(
        string="Outstanding Advance", currency_field="currency_id", readonly=True,
        help="Input advances (seedlings, crates, fertiliser) still to be recovered from payouts.",
    )
    crate_balance = fields.Integer(
        string="Crates On Loan", readonly=True,
        help="Reusable plastic crates issued to the farmer and not yet returned.",
    )
    currency_id = fields.Many2one(
        "res.currency", default=lambda self: self.env.company.currency_id, readonly=True,
    )
    intake_ids = fields.One2many("aifa.intake.batch", "farmer_id", string="Intakes")
    intake_count = fields.Integer(compute="_compute_intake_stats")
    supplied_kg_ytd = fields.Float(compute="_compute_intake_stats", string="Supplied YTD (kg)")
    paid_ytd = fields.Monetary(compute="_compute_intake_stats", string="Paid YTD",
                               currency_field="currency_id")
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ("ref_uniq", "unique(ref)", "The outgrower reference must be unique."),
    ]

    @api.depends("plot_ids", "plot_ids.hectares")
    def _compute_plot_totals(self):
        for farmer in self:
            farmer.plot_count = len(farmer.plot_ids)
            farmer.total_hectares = sum(farmer.plot_ids.mapped("hectares"))

    def _compute_intake_stats(self):
        year_start = fields.Date.today().replace(month=1, day=1)
        for farmer in self:
            intakes = farmer.intake_ids
            farmer.intake_count = len(intakes)
            ytd = intakes.filtered(
                lambda b: b.intake_date and b.intake_date >= year_start
                and b.state not in ("draft", "cancel")
            )
            farmer.supplied_kg_ytd = sum(ytd.mapped("accepted_weight_kg"))
            farmer.paid_ytd = sum(ytd.mapped("amount_total"))

    @api.constrains("payout_method", "wallet_number")
    def _check_wallet(self):
        for farmer in self:
            if farmer.payout_method in ("telebirr", "cbebirr", "bank") and not farmer.wallet_number:
                raise ValidationError(
                    _("Outgrower %s uses %s payouts, so a wallet / account number is required.")
                    % (farmer.name, farmer.payout_method)
                )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("ref"):
                vals["ref"] = self.env["ir.sequence"].next_by_code("aifa.farmer") or "/"
            if not vals.get("partner_id"):
                vals["partner_id"] = self.env["res.partner"].create({
                    "name": vals.get("name"),
                    "supplier_rank": 1,
                    "phone": vals.get("phone"),
                    "company_type": "person",
                }).id
        return super().create(vals_list)

    def action_view_intakes(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Intakes of %s") % self.name,
            "res_model": "aifa.intake.batch",
            "view_mode": "tree,form",
            "domain": [("farmer_id", "=", self.id)],
            "context": {"default_farmer_id": self.id},
        }


class AifaFarmerPlot(models.Model):
    _name = "aifa.farmer.plot"
    _description = "Outgrower Plot"
    _order = "farmer_id, name"

    name = fields.Char(required=True, default="Plot 1")
    farmer_id = fields.Many2one("aifa.farmer", required=True, ondelete="cascade")
    crop_id = fields.Many2one("aifa.crop", required=True)
    variety_id = fields.Many2one(
        "aifa.crop.variety", domain="[('crop_id', '=', crop_id)]",
    )
    hectares = fields.Float(digits=(8, 3), required=True, default=0.25)
    tree_count = fields.Integer(string="Trees / Plants")
    gps_lat = fields.Float(string="Latitude", digits=(10, 6))
    gps_lng = fields.Float(string="Longitude", digits=(10, 6))
    soil_type = fields.Selection(
        [("loam", "Loam"), ("clay", "Clay"), ("sandy", "Sandy"),
         ("volcanic", "Volcanic"), ("other", "Other")],
        default="loam",
    )
    irrigated = fields.Boolean()
    expected_yield_kg = fields.Float(
        string="Expected Season Yield (kg)",
        help="Agronomist estimate used by the harvest-volume forecast.",
    )
    planting_year = fields.Integer()
    active = fields.Boolean(default=True)

    @api.depends("name", "farmer_id.name")
    def _compute_display_name(self):
        for plot in self:
            plot.display_name = "%s - %s" % (plot.farmer_id.name or "", plot.name or "")
