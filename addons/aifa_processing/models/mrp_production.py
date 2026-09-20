# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from .aifa_stage import PROCESS_STAGES


class MrpProduction(models.Model):
    """Carry the agro-processing context onto the manufacturing order."""

    _inherit = "mrp.production"

    aifa_stage = fields.Selection(
        PROCESS_STAGES, string="Processing Stage", index=True,
        compute="_compute_aifa_stage", store=True, readonly=False,
    )
    aifa_crop_id = fields.Many2one(
        "aifa.crop", string="Crop", compute="_compute_aifa_stage", store=True, readonly=False,
    )
    aifa_prep_log_ids = fields.One2many("aifa.prep.log", "production_id", string="Prep Logs")
    aifa_run_ids = fields.One2many("aifa.dehydration.run", "production_id",
                                   string="Dehydration Runs")
    aifa_prep_log_count = fields.Integer(compute="_compute_aifa_counts")
    aifa_run_count = fields.Integer(compute="_compute_aifa_counts")
    aifa_input_kg = fields.Float(compute="_compute_aifa_yield", digits=(12, 3),
                                 string="Stage Input (kg)")
    aifa_output_kg = fields.Float(compute="_compute_aifa_yield", digits=(12, 3),
                                  string="Stage Output (kg)")
    aifa_yield_pct = fields.Float(compute="_compute_aifa_yield", digits=(5, 2),
                                  string="Stage Yield (%)")
    aifa_energy_kwh = fields.Float(compute="_compute_aifa_yield", digits=(10, 2),
                                   string="Drying Energy (kWh)")

    @api.depends("bom_id", "bom_id.aifa_stage", "bom_id.aifa_crop_id")
    def _compute_aifa_stage(self):
        for production in self:
            if production.bom_id.aifa_stage:
                production.aifa_stage = production.bom_id.aifa_stage
                production.aifa_crop_id = production.bom_id.aifa_crop_id
            else:
                production.aifa_stage = production.aifa_stage or False
                production.aifa_crop_id = production.aifa_crop_id or False

    @api.depends("aifa_prep_log_ids", "aifa_run_ids")
    def _compute_aifa_counts(self):
        for production in self:
            production.aifa_prep_log_count = len(production.aifa_prep_log_ids)
            production.aifa_run_count = len(production.aifa_run_ids)

    @api.depends("aifa_stage", "aifa_prep_log_ids.raw_input_kg",
                 "aifa_prep_log_ids.prepped_output_kg",
                 "aifa_run_ids.wet_weight_kg", "aifa_run_ids.dry_weight_kg",
                 "aifa_run_ids.energy_kwh")
    def _compute_aifa_yield(self):
        for production in self:
            if production.aifa_stage == "prep":
                logs = production.aifa_prep_log_ids.filtered(lambda l: l.state == "done")
                production.aifa_input_kg = sum(logs.mapped("raw_input_kg"))
                production.aifa_output_kg = sum(logs.mapped("prepped_output_kg"))
                production.aifa_energy_kwh = 0.0
            elif production.aifa_stage in ("dry", "condition"):
                runs = production.aifa_run_ids.filtered(
                    lambda r: r.state in ("unloaded", "released", "quarantine")
                )
                production.aifa_input_kg = sum(runs.mapped("wet_weight_kg"))
                production.aifa_output_kg = sum(runs.mapped("dry_weight_kg"))
                production.aifa_energy_kwh = sum(runs.mapped("energy_kwh"))
            else:
                production.aifa_input_kg = 0.0
                production.aifa_output_kg = 0.0
                production.aifa_energy_kwh = 0.0
            production.aifa_yield_pct = (
                production.aifa_output_kg / production.aifa_input_kg * 100.0
                if production.aifa_input_kg else 0.0
            )

    def action_view_aifa_prep_logs(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Prep Logs"),
            "res_model": "aifa.prep.log",
            "view_mode": "tree,form",
            "domain": [("production_id", "=", self.id)],
            "context": {"default_production_id": self.id,
                        "default_crop_id": self.aifa_crop_id.id},
        }

    def action_view_aifa_runs(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Dehydration Runs"),
            "res_model": "aifa.dehydration.run",
            "view_mode": "tree,form",
            "domain": [("production_id", "=", self.id)],
            "context": {"default_production_id": self.id,
                        "default_crop_id": self.aifa_crop_id.id},
        }
