# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

CHECK_STAGES = [
    ("intake", "Raw Intake (gate reception)"),
    ("prep", "Preparation"),
    ("dry", "Dehydration"),
    ("condition", "Conditioning / Release"),
    ("pack", "Packing"),
    ("dispatch", "Dispatch"),
    ("environment", "Environment / Facility"),
]

RESULT_TYPES = [
    ("numeric", "Numeric Measurement"),
    ("boolean", "Pass / Fail"),
    ("option", "Option Chosen"),
    ("text", "Observation"),
]


class AifaControlPoint(models.Model):
    """A HACCP critical control point or operational prerequisite programme.

    Keeping limits on the control point rather than hard-coding them means the
    QA manager can retune a limit after a validation study without a developer,
    and every historical check still shows the limit that applied at the time.
    """

    _name = "aifa.control.point"
    _description = "Quality Control Point"
    _order = "sequence, code"

    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True, help="e.g. CCP-2 or OPRP-04.")
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    stage = fields.Selection(CHECK_STAGES, required=True, default="intake", index=True)
    point_type = fields.Selection(
        [("ccp", "CCP - Critical Control Point"),
         ("oprp", "OPRP - Operational Prerequisite"),
         ("qa", "Quality Attribute (non-safety)")],
        default="ccp", required=True,
    )
    hazard = fields.Selection(
        [("biological", "Biological"), ("chemical", "Chemical"),
         ("physical", "Physical"), ("allergen", "Allergen"), ("quality", "Quality")],
        default="biological",
    )
    crop_ids = fields.Many2many(
        "aifa.crop", string="Applies To Crops",
        help="Leave empty to apply to every crop.",
    )
    result_type = fields.Selection(RESULT_TYPES, required=True, default="numeric")
    uom_label = fields.Char(string="Unit", help="Free text unit label, e.g. %, aw, ppm, deg C.")
    limit_min = fields.Float(digits=(10, 3))
    limit_max = fields.Float(digits=(10, 3))
    use_crop_moisture_limit = fields.Boolean(
        string="Use Crop Moisture Limit",
        help="Take the maximum from the crop record instead of the fixed limit above, so a "
             "single control point covers crops with different specifications.",
    )
    use_crop_aw_limit = fields.Boolean(string="Use Crop Water Activity Limit")
    option_ids = fields.Many2many("aifa.control.option", string="Allowed Options")
    expected_bool = fields.Boolean(
        string="Expected Answer", default=True,
        help="For a pass/fail point, the answer that counts as conforming.",
    )

    is_blocking = fields.Boolean(
        string="Blocks Release", default=True,
        help="A failure on a blocking point quarantines the lot; nothing downstream may "
             "consume it until the QA manager records a disposition.",
    )
    frequency = fields.Selection(
        [("every", "Every Batch / Lot"), ("shift", "Once per Shift"),
         ("daily", "Daily"), ("weekly", "Weekly"), ("sample", "Statistical Sample")],
        default="every", required=True,
    )
    sample_size = fields.Integer(default=1)
    method = fields.Text(
        string="Measurement Method",
        help="Instrument, calibration requirement and how the sample is drawn.",
    )
    corrective_action = fields.Text(
        help="Standing instruction when the limit is breached. Printed on the check form "
             "so the operator does not have to find the manual.",
    )
    responsible_group_id = fields.Many2one("res.groups", string="Responsible Role")
    legal_reference = fields.Char(
        help="EFDA directive, ISO 22000 clause or Codex standard this point derives from.",
    )
    check_count = fields.Integer(compute="_compute_check_count")

    _sql_constraints = [("code_uniq", "unique(code)", "Control point code must be unique.")]

    def _compute_check_count(self):
        data = self.env["aifa.quality.check"]._read_group(
            [("control_point_id", "in", self.ids)], ["control_point_id"], ["__count"]
        )
        mapped = {point.id: count for point, count in data}
        for point in self:
            point.check_count = mapped.get(point.id, 0)

    @api.constrains("limit_min", "limit_max", "result_type")
    def _check_limits(self):
        for point in self:
            if point.result_type == "numeric" and point.limit_min and point.limit_max \
                    and point.limit_min > point.limit_max:
                raise ValidationError(
                    _("On %s the minimum limit is above the maximum limit.") % point.code
                )

    def resolve_limits(self, crop=None):
        """Return the (min, max) pair applying to ``crop``."""
        self.ensure_one()
        limit_min, limit_max = self.limit_min, self.limit_max
        if crop:
            if self.use_crop_moisture_limit and crop.target_moisture_pct:
                limit_max = crop.target_moisture_pct
            if self.use_crop_aw_limit and crop.target_water_activity:
                limit_max = crop.target_water_activity
        return limit_min, limit_max

    @api.depends("code", "name")
    def _compute_display_name(self):
        for point in self:
            point.display_name = "[%s] %s" % (point.code or "", point.name or "")


class AifaControlOption(models.Model):
    _name = "aifa.control.option"
    _description = "Quality Control Option"
    _order = "sequence, name"

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    is_conforming = fields.Boolean(default=True)
