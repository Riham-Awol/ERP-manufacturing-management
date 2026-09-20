# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class AifaDehydrationRun(models.Model):
    """One chamber load, from tray-in to tray-out (FRS-3.3, FRS-3.4, FRS-3.6).

    The run is where the money is made or lost: it converts prepped WIP into
    dried bulk, and every percentage point of drying-yield drift is raw fruit
    that was paid for and never sold.  A run therefore records four things the
    clipboard could not:

    1. the exact wet load in and dry load out, per chamber;
    2. the temperature/time profile actually achieved, not the one intended;
    3. residual moisture and water activity, which gate the release to packing;
    4. the kWh consumed, so drying energy lands in product cost per kg.
    """

    _name = "aifa.dehydration.run"
    _description = "Dehydration Run"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "load_datetime desc, id desc"

    name = fields.Char(required=True, copy=False, readonly=True, default="New", index=True)
    wip_lot_code = fields.Char(
        string="WIP Lot", copy=False, readonly=True, index=True,
        help="Barcode applied to the dried bulk totes leaving the chamber (FRS-3.4).",
    )
    dehydrator_id = fields.Many2one("aifa.dehydrator", required=True, tracking=True, index=True)
    crop_id = fields.Many2one("aifa.crop", required=True, tracking=True, index=True)
    production_id = fields.Many2one(
        "mrp.production", string="Manufacturing Order",
        domain="[('aifa_stage', '=', 'dry')]", index=True,
    )
    prep_log_ids = fields.Many2many(
        "aifa.prep.log", string="Source Prep Logs",
        domain="[('state', '=', 'done'), ('crop_id', '=', crop_id)]",
    )
    intake_batch_ids = fields.Many2many(
        "aifa.intake.batch", string="Upstream Intake Lots",
        compute="_compute_intake_batches", store=True,
        help="Derived from the prep logs so the genealogy survives the drying stage.",
    )
    operator_id = fields.Many2one("res.users", string="Operator",
                                  default=lambda self: self.env.user, tracking=True)
    shift = fields.Selection(
        [("a", "Shift A"), ("b", "Shift B"), ("c", "Night Shift")], default="a",
    )

    # ---------- loading ----------
    load_datetime = fields.Datetime(string="Loaded At", default=fields.Datetime.now,
                                    required=True, tracking=True)
    tray_count = fields.Integer(string="Trays Loaded")
    wet_weight_kg = fields.Float(string="Wet Load In (kg)", required=True, digits=(12, 3),
                                 tracking=True)
    load_fill_pct = fields.Float(compute="_compute_load_fill", digits=(5, 2),
                                 string="Chamber Fill (%)")

    # ---------- profile ----------
    target_temp_c = fields.Float(string="Target Temp (C)", digits=(5, 1))
    avg_temp_c = fields.Float(string="Achieved Avg Temp (C)", digits=(5, 1))
    max_temp_c = fields.Float(string="Peak Temp (C)", digits=(5, 1))
    ambient_rh_pct = fields.Float(string="Ambient RH (%)", digits=(5, 1))
    temp_excursion = fields.Boolean(
        string="Temperature Excursion", compute="_compute_excursion", store=True,
        help="True when the achieved profile fell outside the crop's validated band.",
    )
    profile_note = fields.Text(string="Profile / Data Logger Notes")

    # ---------- unloading ----------
    unload_datetime = fields.Datetime(string="Unloaded At", tracking=True)
    duration_hours = fields.Float(compute="_compute_duration", store=True, digits=(6, 2))
    dry_weight_kg = fields.Float(string="Dry Load Out (kg)", digits=(12, 3), tracking=True)
    moisture_out_pct = fields.Float(string="Residual Moisture (%)", digits=(5, 2), tracking=True)
    water_activity = fields.Float(string="Water Activity (aw)", digits=(4, 3), tracking=True)
    moisture_sample_count = fields.Integer(string="Moisture Samples", default=3)

    # ---------- yield ----------
    actual_yield_pct = fields.Float(compute="_compute_yield", store=True, digits=(5, 2),
                                    string="Actual Drying Yield (%)", tracking=True)
    standard_yield_pct = fields.Float(related="crop_id.dry_yield_pct", readonly=True,
                                      string="Standard Drying Yield (%)")
    yield_variance_pct = fields.Float(compute="_compute_yield", store=True, digits=(5, 2),
                                      string="Variance (pp)")
    variance_flag = fields.Selection(
        [("ok", "Within Tolerance"), ("low", "Below Tolerance"), ("high", "Above Tolerance")],
        compute="_compute_yield", store=True, default="ok", tracking=True,
    )
    water_removed_kg = fields.Float(compute="_compute_yield", store=True, digits=(12, 3))

    # ---------- energy & cost ----------
    energy_kwh = fields.Float(string="Energy Consumed (kWh)", digits=(10, 2))
    energy_source = fields.Selection(
        [("grid", "Grid"), ("generator", "Diesel Generator"),
         ("solar", "Solar / Hybrid"), ("mixed", "Mixed")],
        default="grid",
    )
    energy_cost = fields.Monetary(compute="_compute_energy_cost", store=True,
                                  currency_field="currency_id")
    energy_per_kg_dried = fields.Float(compute="_compute_energy_cost", store=True,
                                       digits=(8, 3), string="kWh / kg Dried")
    labour_hours = fields.Float(digits=(6, 2))
    currency_id = fields.Many2one(
        "res.currency", default=lambda self: self.env.company.currency_id, readonly=True,
    )

    state = fields.Selection(
        [("draft", "Draft"),
         ("loading", "Loading"),
         ("running", "Drying"),
         ("unloaded", "Unloaded"),
         ("released", "Released to Packing"),
         ("quarantine", "Quarantined"),
         ("cancel", "Cancelled")],
        default="draft", tracking=True, copy=False, index=True,
    )
    qa_blocked = fields.Boolean(
        string="Blocked by QA", readonly=True, copy=False,
        help="Set by the moisture / water-activity gate; packing cannot draw on a blocked run.",
    )
    qa_note = fields.Text()
    note = fields.Text()

    _sql_constraints = [
        ("wip_lot_uniq", "unique(wip_lot_code)", "The WIP lot code must be unique."),
    ]

    # ------------------------------------------------------------------ compute
    @api.depends("prep_log_ids.intake_batch_ids")
    def _compute_intake_batches(self):
        for run in self:
            run.intake_batch_ids = run.prep_log_ids.mapped("intake_batch_ids")

    @api.depends("wet_weight_kg", "dehydrator_id.max_wet_load_kg")
    def _compute_load_fill(self):
        for run in self:
            capacity = run.dehydrator_id.max_wet_load_kg
            run.load_fill_pct = (run.wet_weight_kg / capacity * 100.0) if capacity else 0.0

    @api.depends("load_datetime", "unload_datetime")
    def _compute_duration(self):
        for run in self:
            if run.load_datetime and run.unload_datetime:
                delta = run.unload_datetime - run.load_datetime
                run.duration_hours = delta.total_seconds() / 3600.0
            else:
                run.duration_hours = 0.0

    @api.depends("avg_temp_c", "max_temp_c", "duration_hours",
                 "crop_id.drying_temp_min", "crop_id.drying_temp_max",
                 "crop_id.drying_hours_min", "crop_id.drying_hours_max")
    def _compute_excursion(self):
        for run in self:
            crop = run.crop_id
            excursion = False
            if run.avg_temp_c and crop:
                if crop.drying_temp_min and run.avg_temp_c < crop.drying_temp_min:
                    excursion = True
                if crop.drying_temp_max and run.avg_temp_c > crop.drying_temp_max:
                    excursion = True
            if run.max_temp_c and crop.drying_temp_max and run.max_temp_c > crop.drying_temp_max + 5:
                excursion = True
            if run.duration_hours and crop.drying_hours_max and \
                    run.duration_hours > crop.drying_hours_max + 2:
                excursion = True
            run.temp_excursion = excursion

    @api.depends("wet_weight_kg", "dry_weight_kg",
                 "crop_id.dry_yield_pct", "crop_id.yield_tolerance_pct")
    def _compute_yield(self):
        for run in self:
            run.water_removed_kg = max(run.wet_weight_kg - run.dry_weight_kg, 0.0)
            run.actual_yield_pct = (
                run.dry_weight_kg / run.wet_weight_kg * 100.0 if run.wet_weight_kg else 0.0
            )
            standard = run.crop_id.dry_yield_pct
            tolerance = run.crop_id.yield_tolerance_pct or 0.0
            run.yield_variance_pct = (
                run.actual_yield_pct - standard if (standard and run.dry_weight_kg) else 0.0
            )
            if not (standard and run.dry_weight_kg):
                run.variance_flag = "ok"
            elif run.yield_variance_pct < -tolerance:
                run.variance_flag = "low"
            elif run.yield_variance_pct > tolerance:
                run.variance_flag = "high"
            else:
                run.variance_flag = "ok"

    @api.depends("energy_kwh", "dehydrator_id.energy_tariff", "dry_weight_kg")
    def _compute_energy_cost(self):
        for run in self:
            run.energy_cost = run.energy_kwh * (run.dehydrator_id.energy_tariff or 0.0)
            run.energy_per_kg_dried = (
                run.energy_kwh / run.dry_weight_kg if run.dry_weight_kg else 0.0
            )

    # ------------------------------------------------------------------ checks
    @api.constrains("wet_weight_kg", "dry_weight_kg")
    def _check_weights(self):
        for run in self:
            if run.wet_weight_kg <= 0:
                raise ValidationError(_("The wet load must be greater than zero."))
            if run.dry_weight_kg and run.dry_weight_kg > run.wet_weight_kg:
                raise ValidationError(
                    _("Drying cannot add mass: %(dry)s kg out of a %(wet)s kg load on %(name)s.")
                    % {"dry": run.dry_weight_kg, "wet": run.wet_weight_kg, "name": run.name}
                )

    @api.constrains("wet_weight_kg", "dehydrator_id")
    def _check_capacity(self):
        for run in self:
            capacity = run.dehydrator_id.max_wet_load_kg
            if capacity and run.wet_weight_kg > capacity * 1.05:
                raise ValidationError(
                    _("%(wet)s kg exceeds the rated capacity of %(dryer)s (%(cap)s kg). "
                      "Overloading a chamber is the single most common cause of "
                      "under-dried centre trays.")
                    % {"wet": run.wet_weight_kg, "dryer": run.dehydrator_id.display_name,
                       "cap": capacity}
                )

    @api.onchange("crop_id")
    def _onchange_crop(self):
        if self.crop_id:
            self.target_temp_c = self.crop_id.drying_temp_max

    @api.onchange("prep_log_ids")
    def _onchange_prep_logs(self):
        if self.prep_log_ids and not self.wet_weight_kg:
            self.wet_weight_kg = sum(self.prep_log_ids.mapped("prepped_output_kg"))

    # ------------------------------------------------------------------ CRUD
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = self.env["ir.sequence"].next_by_code(
                    "aifa.dehydration.run") or "New"
        return super().create(vals_list)

    # ------------------------------------------------------------------ workflow
    def action_start(self):
        for run in self:
            if run.state not in ("draft", "loading"):
                raise UserError(_("%s is not in a state that can be started.") % run.name)
            if run.dehydrator_id.state in ("running", "maintenance"):
                raise UserError(
                    _("%s is currently %s; pick another chamber.")
                    % (run.dehydrator_id.display_name, run.dehydrator_id.state)
                )
            if not run.dehydrator_id.last_cip_date:
                run.message_post(
                    body=_("<b>Warning:</b> no sanitation (CIP) record exists for %s. "
                           "Log the pre-operational clean before the next run.")
                    % run.dehydrator_id.display_name
                )
            run.write({
                "state": "running",
                "load_datetime": run.load_datetime or fields.Datetime.now(),
            })
            run.dehydrator_id.write({"state": "running", "current_run_id": run.id})

    def action_unload(self):
        for run in self:
            if run.state != "running":
                raise UserError(_("Only a running chamber can be unloaded."))
            if run.dry_weight_kg <= 0:
                raise UserError(
                    _("Weigh the dried output before unloading %s.") % run.name
                )
            run.write({
                "state": "unloaded",
                "unload_datetime": run.unload_datetime or fields.Datetime.now(),
                "wip_lot_code": run.wip_lot_code or run._build_wip_lot(),
            })
            run.dehydrator_id.write({"state": "unloading", "current_run_id": False})
            run._evaluate_moisture_gate()
            run._raise_variance_activity()

    def action_release(self):
        """Release the dried bulk to packing once the moisture gate has passed."""
        for run in self:
            if run.state not in ("unloaded", "quarantine"):
                raise UserError(_("Only an unloaded run can be released."))
            run._evaluate_moisture_gate()
            if run.qa_blocked:
                raise UserError(
                    _("%(name)s is blocked by the moisture / water-activity gate "
                      "(moisture %(m).2f%%, aw %(a).3f). Re-dry the load or have the QA "
                      "manager authorise a downgrade before releasing it to packing.")
                    % {"name": run.name, "m": run.moisture_out_pct, "a": run.water_activity}
                )
            run.state = "released"
            run.dehydrator_id.action_set_idle()
            run.message_post(
                body=_("Released %(kg)s kg of dried %(crop)s to packing under WIP lot <b>%(lot)s</b>.")
                % {"kg": round(run.dry_weight_kg, 2), "crop": run.crop_id.display_name,
                   "lot": run.wip_lot_code}
            )

    def action_quarantine(self):
        for run in self:
            run.write({"state": "quarantine", "qa_blocked": True})
            run.dehydrator_id.action_set_idle()

    def action_redry(self):
        """Send an under-dried load back into a chamber as a fresh run."""
        new_runs = self.env["aifa.dehydration.run"]
        for run in self:
            if run.state not in ("unloaded", "quarantine"):
                raise UserError(_("Only an unloaded or quarantined run can be re-dried."))
            new_runs |= run.copy({
                "dehydrator_id": run.dehydrator_id.id,
                "wet_weight_kg": run.dry_weight_kg,
                "dry_weight_kg": 0.0,
                "moisture_out_pct": 0.0,
                "water_activity": 0.0,
                "load_datetime": fields.Datetime.now(),
                "unload_datetime": False,
                "state": "draft",
                "qa_blocked": False,
                "note": _("Re-dry of %s (residual moisture %.2f%%).")
                        % (run.name, run.moisture_out_pct),
            })
            run.message_post(body=_("Sent for re-drying as a new run."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Re-dry Runs"),
            "res_model": "aifa.dehydration.run",
            "view_mode": "tree,form",
            "domain": [("id", "in", new_runs.ids)],
        }

    def action_cancel(self):
        for run in self:
            if run.state == "released":
                raise UserError(_("A released run cannot be cancelled."))
            run.state = "cancel"
            if run.dehydrator_id.current_run_id == run:
                run.dehydrator_id.action_set_idle()

    def action_draft(self):
        self.filtered(lambda r: r.state == "cancel").write({"state": "draft"})

    # ------------------------------------------------------------------ helpers
    def _build_wip_lot(self):
        self.ensure_one()
        serial = (self.name or "").rsplit("/", 1)[-1]
        return "LOT-DRY-%s-%s-%s" % (
            self.crop_id.code,
            (self.load_datetime or fields.Datetime.now()).strftime("%Y%m%d"),
            serial,
        )

    def _evaluate_moisture_gate(self):
        """FRS-4.2: block packing release when moisture or aw is out of spec."""
        for run in self:
            crop = run.crop_id
            reasons = []
            if not run.moisture_out_pct:
                reasons.append(_("residual moisture has not been measured"))
            elif crop.target_moisture_pct and run.moisture_out_pct > crop.target_moisture_pct:
                reasons.append(
                    _("moisture %(got).2f%% exceeds the %(max).2f%% limit")
                    % {"got": run.moisture_out_pct, "max": crop.target_moisture_pct}
                )
            if not run.water_activity:
                reasons.append(_("water activity has not been measured"))
            elif crop.target_water_activity and run.water_activity > crop.target_water_activity:
                reasons.append(
                    _("water activity %(got).3f exceeds the %(max).3f limit")
                    % {"got": run.water_activity, "max": crop.target_water_activity}
                )
            run.qa_blocked = bool(reasons)
            if reasons:
                run.qa_note = _("Blocked: %s.") % "; ".join(reasons)
                if run.state == "unloaded":
                    run.state = "quarantine"
                run.message_post(
                    body=_("<b>Moisture / water activity gate failed.</b> %s") % run.qa_note
                )

    def _raise_variance_activity(self):
        for run in self.filtered(lambda r: r.variance_flag != "ok"):
            run.activity_schedule(
                "mail.mail_activity_data_todo",
                summary=_("Drying yield variance on %s") % run.name,
                note=_("Chamber %(dryer)s returned %(act).2f%% against a standard of "
                       "%(std).2f%% (%(var)+.2f pp) on %(kg)s kg of wet load. "
                       "Check tray loading density, airflow baffles and the "
                       "incoming moisture of the prepped fruit.")
                     % {"dryer": run.dehydrator_id.display_name,
                        "act": run.actual_yield_pct, "std": run.standard_yield_pct,
                        "var": run.yield_variance_pct, "kg": round(run.wet_weight_kg, 1)},
                user_id=(run.operator_id or self.env.user).id,
            )

    @api.depends("name", "wip_lot_code")
    def _compute_display_name(self):
        for run in self:
            run.display_name = run.wip_lot_code or run.name or ""
