# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class AifaCrop(models.Model):
    """Commodity master (Pineapple, Mango, Tomato...).

    Holds the reference mass-balance factors for the two lossy stages of
    dehydration.  These are *standards*; the processing module compares every
    actual production run against them and raises a variance when the run
    drifts outside the tolerance band.

    Reference figures shipped as demo data are industry baselines
    (FAO 'Fruit and vegetable processing', Ch. dried fruit) and MUST be
    re-calibrated during Phase 1 discovery against Aifa's own trial batches.
    """

    _name = "aifa.crop"
    _description = "Aifa Crop / Commodity"
    _order = "sequence, name"

    name = fields.Char(required=True, translate=True)
    code = fields.Char(
        required=True,
        size=6,
        help="Short uppercase code embedded in lot numbers, e.g. PINE, MANG, TOMA.",
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    color = fields.Integer()

    raw_product_id = fields.Many2one(
        "product.product",
        string="Raw Fruit Product",
        domain="[('type', '=', 'product')]",
        help="Storable product used to receive fresh fruit from outgrowers.",
    )
    prepped_product_id = fields.Many2one(
        "product.product",
        string="Prepped (Stage 1) Product",
        help="Semi-finished washed/peeled/sliced output of the preparation stage.",
    )
    dried_product_id = fields.Many2one(
        "product.product",
        string="Dried Bulk (Stage 2) Product",
        help="Bulk dried output of the dehydration stage, before packing.",
    )

    # --- Mass balance standards -------------------------------------------------
    prep_yield_pct = fields.Float(
        string="Prep Yield (%)",
        default=55.0,
        digits=(5, 2),
        help="Standard kg of prepped fruit obtained from 100 kg of accepted raw fruit, "
             "after washing, sorting, peeling, coring and slicing.",
    )
    dry_yield_pct = fields.Float(
        string="Drying Yield (%)",
        default=20.0,
        digits=(5, 2),
        help="Standard kg of dried fruit obtained from 100 kg of prepped fruit.",
    )
    yield_tolerance_pct = fields.Float(
        string="Variance Tolerance (+/- %)",
        default=3.0,
        digits=(5, 2),
        help="Absolute percentage points of drift tolerated before a run is flagged.",
    )
    overall_ratio = fields.Float(
        string="Fresh : Dried Ratio",
        compute="_compute_overall_ratio",
        store=True,
        digits=(6, 2),
        help="How many kg of fresh fruit at the farm gate are needed for 1 kg of dried product.",
    )

    # --- Quality standards ------------------------------------------------------
    target_moisture_pct = fields.Float(
        string="Max Residual Moisture (%)", default=12.0, digits=(5, 2)
    )
    target_water_activity = fields.Float(
        string="Max Water Activity (aw)", default=0.60, digits=(3, 2)
    )
    min_brix = fields.Float(string="Min Intake Brix", default=12.0, digits=(5, 2))
    drying_temp_min = fields.Float(string="Min Drying Temp (C)", default=55.0)
    drying_temp_max = fields.Float(string="Max Drying Temp (C)", default=65.0)
    drying_hours_min = fields.Float(string="Min Drying Time (h)", default=12.0)
    drying_hours_max = fields.Float(string="Max Drying Time (h)", default=18.0)
    slice_thickness_mm = fields.Float(string="Target Slice Thickness (mm)", default=8.0)
    shelf_life_days = fields.Integer(string="Finished Shelf Life (days)", default=365)

    variety_ids = fields.One2many("aifa.crop.variety", "crop_id", string="Cultivars")
    notes = fields.Text(string="Processing Notes")

    _sql_constraints = [
        ("code_uniq", "unique(code)", "The crop code must be unique."),
    ]

    @api.depends("prep_yield_pct", "dry_yield_pct")
    def _compute_overall_ratio(self):
        for crop in self:
            overall = (crop.prep_yield_pct / 100.0) * (crop.dry_yield_pct / 100.0)
            crop.overall_ratio = (1.0 / overall) if overall > 0 else 0.0

    @api.constrains("prep_yield_pct", "dry_yield_pct", "target_water_activity")
    def _check_percentages(self):
        for crop in self:
            if not 0 < crop.prep_yield_pct <= 100:
                raise ValidationError(_("Prep yield must be greater than 0 and at most 100%%."))
            if not 0 < crop.dry_yield_pct <= 100:
                raise ValidationError(_("Drying yield must be greater than 0 and at most 100%%."))
            if not 0 < crop.target_water_activity <= 1:
                raise ValidationError(_("Water activity must be between 0 and 1."))

    @api.onchange("code")
    def _onchange_code(self):
        if self.code:
            self.code = self.code.strip().upper()

    def expected_dried_kg(self, raw_kg):
        """Return the standard dried kg expected from ``raw_kg`` of fresh fruit."""
        self.ensure_one()
        return raw_kg * (self.prep_yield_pct / 100.0) * (self.dry_yield_pct / 100.0)


class AifaCropVariety(models.Model):
    """Cultivar of a crop; cultivars differ materially in yield and Brix."""

    _name = "aifa.crop.variety"
    _description = "Aifa Crop Cultivar"
    _order = "crop_id, name"

    name = fields.Char(required=True)
    crop_id = fields.Many2one("aifa.crop", required=True, ondelete="cascade")
    region_ids = fields.Many2many("aifa.region", string="Typical Sourcing Regions")
    harvest_month_start = fields.Selection(
        selection="_month_selection", string="Harvest Window Start"
    )
    harvest_month_end = fields.Selection(
        selection="_month_selection", string="Harvest Window End"
    )
    prep_yield_pct = fields.Float(string="Prep Yield (%)", digits=(5, 2))
    dry_yield_pct = fields.Float(string="Drying Yield (%)", digits=(5, 2))
    typical_brix = fields.Float(string="Typical Brix", digits=(5, 2))
    notes = fields.Text()
    active = fields.Boolean(default=True)

    @api.model
    def _month_selection(self):
        return [
            ("1", _("January")), ("2", _("February")), ("3", _("March")),
            ("4", _("April")), ("5", _("May")), ("6", _("June")),
            ("7", _("July")), ("8", _("August")), ("9", _("September")),
            ("10", _("October")), ("11", _("November")), ("12", _("December")),
        ]
