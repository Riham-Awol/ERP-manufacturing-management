# -*- coding: utf-8 -*-
import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class StockLot(models.Model):
    """Materialised genealogy on the lot.

    Odoo can already answer "where did this lot go" by walking ``stock.move.line``
    at query time, but an EFDA inspector asking for the farm of origin of a
    pouch would trigger a recursive walk across three manufacturing stages.
    Storing the resolved ancestors turns a 48-hour paper exercise into a page
    that renders immediately, which is the whole point of FRS-4.5.
    """

    _inherit = "stock.lot"

    aifa_parent_lot_ids = fields.Many2many(
        "stock.lot", "aifa_lot_genealogy_rel", "child_id", "parent_id",
        string="Consumed Lots (ancestors)",
    )
    aifa_child_lot_ids = fields.Many2many(
        "stock.lot", "aifa_lot_genealogy_rel", "parent_id", "child_id",
        string="Produced Lots (descendants)",
    )
    aifa_trace_rebuilt_on = fields.Datetime(string="Genealogy Rebuilt On", readonly=True)
    aifa_origin_region_ids = fields.Many2many(
        "aifa.region", string="Origin Regions", compute="_compute_origin_summary", store=True,
    )
    aifa_origin_summary = fields.Char(compute="_compute_origin_summary", store=True)

    @api.depends("aifa_origin_intake_ids")
    def _compute_origin_summary(self):
        for lot in self:
            regions = lot.aifa_origin_intake_ids.mapped("region_id")
            lot.aifa_origin_region_ids = regions
            farmers = lot.aifa_origin_intake_ids.mapped("farmer_id")
            if not farmers:
                lot.aifa_origin_summary = ""
            else:
                lot.aifa_origin_summary = _("%(n)s outgrower(s) across %(r)s") % {
                    "n": len(farmers),
                    "r": ", ".join(regions.mapped("name")) or _("unknown region"),
                }

    # ------------------------------------------------------------------ rebuild
    def _direct_parent_lots(self):
        """Lots consumed by the manufacturing order(s) that produced ``self``."""
        self.ensure_one()
        produced_moves = self.env["stock.move.line"].search([
            ("lot_id", "=", self.id),
            ("state", "=", "done"),
            ("move_id.production_id", "!=", False),
        ])
        productions = produced_moves.mapped("move_id.production_id")
        if not productions:
            return self.env["stock.lot"]
        consumed = self.env["stock.move.line"].search([
            ("move_id", "in", productions.mapped("move_raw_ids").ids),
            ("state", "=", "done"),
            ("lot_id", "!=", False),
        ])
        return consumed.mapped("lot_id")

    def action_rebuild_genealogy(self, max_depth=8):
        """Resolve ancestors up to the farm gate and cache the result."""
        for lot in self:
            ancestors = self.env["stock.lot"]
            frontier = lot._direct_parent_lots()
            depth = 0
            while frontier and depth < max_depth:
                new = frontier - ancestors - lot
                if not new:
                    break
                ancestors |= new
                next_frontier = self.env["stock.lot"]
                for parent in new:
                    next_frontier |= parent._direct_parent_lots()
                frontier = next_frontier
                depth += 1
            if depth >= max_depth:
                _logger.warning(
                    "Genealogy rebuild for lot %s stopped at depth %s; the chain is "
                    "deeper than expected or contains a cycle.", lot.name, max_depth
                )
            lot.aifa_parent_lot_ids = ancestors
            intakes = self.env["aifa.intake.batch"].search([
                ("lot_id", "in", (ancestors | lot).ids)
            ])
            lot.aifa_origin_intake_ids = intakes
            runs = self.env["aifa.dehydration.run"].search([
                ("intake_batch_ids", "in", intakes.ids)
            ])
            if not runs and lot.product_id:
                runs = self.env["aifa.dehydration.run"].search([
                    ("wip_lot_code", "in", (ancestors | lot).mapped("name"))
                ])
            lot.aifa_origin_run_ids = runs
            lot.aifa_trace_rebuilt_on = fields.Datetime.now()
        return True

    @api.model
    def cron_rebuild_genealogy(self, limit=500):
        """Nightly catch-up for lots produced since the last rebuild."""
        stale = self.search([
            ("aifa_trace_rebuilt_on", "=", False),
            ("product_id.tracking", "=", "lot"),
        ], limit=limit)
        stale.action_rebuild_genealogy()
        _logger.info("Aifa traceability: rebuilt genealogy for %s lot(s).", len(stale))
        return True

    # ------------------------------------------------------------------ downstream
    def aifa_downstream_moves(self):
        """Every line that put this lot, or a descendant, beyond Aifa's own walls.

        A plain ``usage = customer`` filter is not enough here: consigned stock
        sits in an *internal* location that happens to be a supermarket shelf.
        Missing it would make a recall report look clean while the product is
        still on sale, which is the precise failure a recall exists to prevent.
        """
        self.ensure_one()
        family = self | self._collect_descendants()
        domain = [("lot_id", "in", family.ids), ("state", "=", "done")]
        external = [("location_dest_id.usage", "in", ("customer", "supplier"))]
        consignment_root = self.env.ref(
            "aifa_consignment.stock_location_consignment_root", raise_if_not_found=False
        )
        if consignment_root:
            external = ["|"] + external + [
                ("location_dest_id", "child_of", consignment_root.id)
            ]
        return self.env["stock.move.line"].search(domain + external)

    def _collect_descendants(self, max_depth=8):
        self.ensure_one()
        found = self.env["stock.lot"]
        frontier = self.aifa_child_lot_ids
        depth = 0
        while frontier and depth < max_depth:
            new = frontier - found - self
            if not new:
                break
            found |= new
            frontier = new.mapped("aifa_child_lot_ids")
            depth += 1
        return found

    def action_open_genealogy(self):
        self.ensure_one()
        self.action_rebuild_genealogy()
        return {
            "type": "ir.actions.act_window",
            "name": _("Genealogy of %s") % self.name,
            "res_model": "stock.lot",
            "res_id": self.id,
            "view_mode": "form",
        }

    def aifa_public_payload(self):
        """Consumer-facing provenance data. Deliberately omits personal data."""
        self.ensure_one()
        intakes = self.aifa_origin_intake_ids
        runs = self.aifa_origin_run_ids
        return {
            "lot": self.name,
            "product": self.product_id.display_name,
            "released": self.aifa_quality_state == "released",
            "quality_state": self.aifa_quality_state,
            "expiry": self.expiration_date.strftime("%d %B %Y") if self.expiration_date else "",
            "regions": sorted(set(intakes.mapped("region_id.name"))),
            "cooperatives": sorted(set(c for c in intakes.mapped("cooperative_id.name") if c)),
            "outgrower_count": len(intakes.mapped("farmer_id")),
            "women_outgrower_pct": (
                len(intakes.mapped("farmer_id").filtered(lambda f: f.gender == "female"))
                / len(intakes.mapped("farmer_id")) * 100.0
                if intakes.mapped("farmer_id") else 0.0
            ),
            "harvest_dates": sorted(set(str(d) for d in intakes.mapped("intake_date") if d)),
            "fresh_fruit_kg": sum(intakes.mapped("accepted_weight_kg")),
            "drying_runs": [{
                "chamber": run.dehydrator_id.name,
                "date": run.load_datetime and run.load_datetime.strftime("%Y-%m-%d"),
                "avg_temp_c": run.avg_temp_c,
                "hours": round(run.duration_hours, 1),
                "moisture_pct": run.moisture_out_pct,
                "water_activity": run.water_activity,
            } for run in runs],
            # Release checks are recorded against the dried bulk lot, not the
            # finished pouch, so a consumer scanning a pouch would otherwise see
            # an empty quality section. Walk the ancestors as well.
            "checks": [{
                "point": check.control_point_id.name,
                "result": check.result,
                "value": check.value_numeric,
                "unit": check.uom_label,
            } for check in (self | self.aifa_parent_lot_ids).mapped(
                "aifa_check_ids").filtered(lambda c: c.state == "done")],
        }
