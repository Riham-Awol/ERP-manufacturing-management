# -*- coding: utf-8 -*-
"""Drive one complete farm-to-shelf cycle through the Aifa modules.

Run it against a database that already has the Aifa add-ons installed with
demo data::

    python3 odoo-bin shell -d aifa_demo \
        --addons-path=<odoo>/addons,<repo>/addons \
        < tools/seed_demo.py

It is idempotent in the sense that it only acts on records still sitting in
their initial state, so re-running it after a partial failure is safe.

What it produces, in order:

1. confirms the demo field purchases, receiving the fruit and creating the
   farm-gate lots;
2. runs gate QA and puts the accepted fruit into stock;
3. records a payout for one outgrower;
4. creates the Stage-1 (prep), Stage-2 (dry) and Stage-3 (pack) manufacturing
   orders and completes them with real lots;
5. records the release quality checks on the finished lot;
6. rebuilds the genealogy and runs a mock recall;
7. places stock on a supermarket shelf, counts it and bills the sell-through;
8. builds the KPI snapshots and an ESG impact report.
"""

import logging
from datetime import timedelta

from odoo import fields
from odoo.tests.common import Form

_logger = logging.getLogger("aifa.seed")
LOG = []


def step(message):
    LOG.append(message)
    print("  * %s" % message)


def seed(env):
    print("\n=== Aifa end-to-end demo seed ===\n")
    company = env.company
    etb = env["res.currency"].with_context(active_test=False).search(
        [("name", "=", "ETB")], limit=1
    )
    if etb and company.currency_id != etb:
        # Best effort only: Odoo refuses a currency change once journal items
        # exist, which is the normal state of a database carrying demo
        # accounting data. Set the currency when creating the database
        # instead (see docs/DEMO_SCRIPT.md); the workflow below is unaffected.
        etb.active = True
        try:
            company.currency_id = etb
            step("Company currency set to ETB")
        except Exception:
            env.cr.rollback()
            step("Company currency left as %s (journal items already exist); "
                 "amounts below are in that currency" % company.currency_id.name)

    # ---------------------------------------------------------------- 1. intake
    purchases = env["aifa.field.purchase"].search([("state", "=", "draft")])
    purchases.action_confirm()
    step("Confirmed %s field purchase(s)" % len(purchases))

    batches = env["aifa.intake.batch"].search([("state", "=", "weighed")])
    batches.action_receive()
    step("Received %s intake batch(es) at the plant" % len(batches))

    for batch in batches:
        batch.gate_grade = batch.field_grade
        # A realistic gate loss on one consignment, so the numbers are not sterile.
        if batch.crop_id.code == "TOMA":
            batch.rejected_weight_kg = round(batch.net_weight_kg * 0.04, 3)
    batches.action_qa_accept()
    step("QA-accepted %s batch(es); %.1f kg stocked under farm-gate lots"
         % (len(batches), sum(batches.mapped("accepted_weight_kg"))))
    for batch in batches:
        if batch.lot_id:
            batch.lot_id.aifa_quality_state = "released"

    # ---------------------------------------------------------------- 2. payout
    farmer = batches[:1].farmer_id
    if farmer:
        payout = env["aifa.farmer.payout"].create({
            "farmer_id": farmer.id,
            "period_start": fields.Date.today() - timedelta(days=30),
            "period_end": fields.Date.today(),
        })
        payout.action_collect_intakes()
        payout.action_approve()
        payout.transaction_ref = "TB-DEMO-000431"
        payout.action_mark_paid()
        step("Paid %s %.2f %s (net of a %.2f advance recovery)"
             % (farmer.name, payout.net_amount, payout.currency_id.name,
                payout.advance_deduction))

    # ------------------------------------------------------ 3. three-stage MRP
    crop = env.ref("aifa_base.crop_pineapple")
    raw_batches = batches.filtered(lambda b: b.crop_id == crop and b.lot_id)
    if not raw_batches:
        step("No pineapple intake available; skipping the production chain")
        return _summary(env)
    raw_kg = sum(raw_batches.mapped("accepted_weight_kg"))

    prep_mo = _make_mo(env, env.ref("aifa_processing.bom_prep_pine"),
                       qty=raw_kg * crop.prep_yield_pct / 100.0)
    _assign_component_lots(prep_mo, {crop.raw_product_id: raw_batches.mapped("lot_id")})
    prep_lot = _finish_mo(env, prep_mo, "LOT-PREP-PINE-%s" % fields.Date.today().strftime("%Y%m%d"))
    step("Stage 1 prep: %.1f kg raw -> %.1f kg prepped (lot %s)"
         % (raw_kg, prep_mo.product_qty, prep_lot.name))

    prep_log = env["aifa.prep.log"].create({
        "crop_id": crop.id,
        "production_id": prep_mo.id,
        "intake_batch_ids": [(6, 0, raw_batches.ids)],
        "raw_input_kg": raw_kg,
        "prepped_output_kg": prep_mo.product_qty,
        "slice_thickness_mm": crop.slice_thickness_mm,
        "wash_chlorine_ppm": 120.0,
        "water_change_done": True,
    })
    loss = raw_kg - prep_mo.product_qty
    env["aifa.prep.scrap"].create([
        {"prep_log_id": prep_log.id, "cause": "peel", "weight_kg": round(loss * 0.62, 3),
         "destination": "compost"},
        {"prep_log_id": prep_log.id, "cause": "core", "weight_kg": round(loss * 0.30, 3),
         "destination": "byproduct"},
        {"prep_log_id": prep_log.id, "cause": "trim",
         "weight_kg": round(loss - round(loss * 0.62, 3) - round(loss * 0.30, 3), 3),
         "destination": "compost"},
    ])
    prep_log.action_confirm()
    step("Prep log balanced: %.2f%% actual yield against a %.2f%% standard"
         % (prep_log.actual_yield_pct, prep_log.standard_yield_pct))

    dryer = env.ref("aifa_processing.dryer_td01")
    dry_qty = prep_mo.product_qty * crop.dry_yield_pct / 100.0
    dry_mo = _make_mo(env, env.ref("aifa_processing.bom_dry_pine"), qty=dry_qty)
    _assign_component_lots(dry_mo, {crop.prepped_product_id: prep_lot})
    run = env["aifa.dehydration.run"].create({
        "dehydrator_id": dryer.id,
        "crop_id": crop.id,
        "production_id": dry_mo.id,
        "prep_log_ids": [(6, 0, prep_log.ids)],
        "tray_count": int(min(prep_mo.product_qty / dryer.kg_per_tray, dryer.tray_capacity)),
        "wet_weight_kg": min(prep_mo.product_qty, dryer.max_wet_load_kg),
        "target_temp_c": crop.drying_temp_max,
        "avg_temp_c": crop.drying_temp_max - 1.0,
        "max_temp_c": crop.drying_temp_max + 1.5,
        "ambient_rh_pct": 41.0,
        "energy_kwh": 368.0,
        "labour_hours": 6.0,
    })
    run.action_start()
    run.write({
        "unload_datetime": fields.Datetime.now() + timedelta(hours=16),
        "dry_weight_kg": round(run.wet_weight_kg * crop.dry_yield_pct / 100.0, 2),
        "moisture_out_pct": 13.2,
        "water_activity": 0.56,
    })
    run.action_unload()
    run.action_release()
    dry_lot = _finish_mo(env, dry_mo, run.wip_lot_code)
    step("Stage 2 dry: %.1f kg wet -> %.1f kg dried at %.1f%% yield, %.3f kWh/kg (lot %s)"
         % (run.wet_weight_kg, run.dry_weight_kg, run.actual_yield_pct,
            run.energy_per_kg_dried, dry_lot.name))

    for point_xmlid, value in (("aifa_quality.cp_moisture", run.moisture_out_pct),
                               ("aifa_quality.cp_water_activity", run.water_activity)):
        check = env["aifa.quality.check"].create({
            "control_point_id": env.ref(point_xmlid).id,
            "crop_id": crop.id,
            "dehydration_run_id": run.id,
            "lot_id": dry_lot.id,
            "value_numeric": value,
        })
        check.action_record()
    dry_lot.action_release_quality()
    step("Release checks recorded; dried lot quality state = %s" % dry_lot.aifa_quality_state)

    pack_bom = env.ref("aifa_processing.bom_pack_pine_100")
    dried_available = run.dry_weight_kg
    fill_per_batch = sum(
        line.product_qty for line in pack_bom.bom_line_ids
        if line.product_id == crop.dried_product_id
    )
    pack_batches = max(int(dried_available // fill_per_batch), 1)
    pack_mo = _make_mo(env, pack_bom, qty=pack_bom.product_qty * pack_batches)
    _stock_packaging(env, pack_mo)
    _assign_component_lots(pack_mo, {crop.dried_product_id: dry_lot})
    fg_lot = _finish_mo(env, pack_mo, "LOT-FG-PINE100-%s" % fields.Date.today().strftime("%Y%m%d"))
    fg_lot.aifa_quality_state = "released"
    step("Stage 3 pack: %.0f pouches of %s (lot %s)"
         % (pack_mo.product_qty, pack_mo.product_id.default_code, fg_lot.name))

    session = env["aifa.checkweigh.session"].create({
        "production_id": pack_mo.id,
        "product_id": pack_mo.product_id.id,
        "lot_id": fg_lot.id,
        "nominal_weight_g": 100.0,
        "target_fill_g": 102.0,
        "scale_serial": "BENCH-01",
    })
    env["aifa.checkweigh.sample"].create([
        {"session_id": session.id, "weight_g": w}
        for w in (102.4, 101.8, 103.1, 100.9, 102.0, 101.2, 102.7, 101.5, 103.0, 102.2)
    ])
    session.action_close()
    step("Check-weigh: mean %.2f g, sd %.2f g, %s"
         % (session.mean_g, session.stdev_g, session.verdict))

    # ------------------------------------------------------ 4. traceability
    fg_lot.action_rebuild_genealogy()
    step("Genealogy: %s farm-gate lot(s), %s drying run(s), origin = %s"
         % (len(fg_lot.aifa_origin_intake_ids), len(fg_lot.aifa_origin_run_ids),
            fg_lot.aifa_origin_summary or "not resolved"))

    # ------------------------------------------------------ 5. consignment
    partner = env.ref("aifa_consignment.partner_friendship")
    placed = min(pack_mo.product_qty, 120)
    placement = env["aifa.consignment"].create({
        "partner_id": partner.id,
        "product_id": pack_mo.product_id.id,
        "lot_id": fg_lot.id,
        "quantity_placed": placed,
        "unit_price": pack_mo.product_id.list_price,
    })
    placement.action_place()
    count = env["aifa.shelf.count"].create({"partner_id": partner.id})
    count.action_load_open_placements()
    for line in count.line_ids:
        line.qty_remaining = line.qty_expected * 0.45
        line.qty_returned = round(line.qty_expected * 0.02, 2)
        line.return_reason = "damaged"
    count.action_confirm()
    count.action_create_sale_order()
    step("Consignment: %.0f placed at %s, %.0f sold, order %s for %.2f %s"
         % (placed, partner.name, count.units_sold, count.sale_order_id.name,
            count.amount_billable, count.currency_id.name))

    # ------------------------------------------------------ 6. recall drill
    recall = env["aifa.recall"].create({
        "is_drill": True,
        "reason": "drill",
        "description": "Quarterly mock recall seeded from the first pineapple intake lot.",
        "intake_batch_id": raw_batches[0].id,
    })
    recall.action_run_trace()
    step("Mock recall %s: %s lot(s), %s customer destination(s), traced in %.2f s"
         % (recall.name, recall.affected_lot_count, recall.customer_count,
            recall.trace_seconds))

    # ------------------------------------------------------ 7. reporting
    env["aifa.daily.kpi"].cron_build_snapshots(days_back=7)
    step("Built %s daily KPI snapshot(s)" % env["aifa.daily.kpi"].search_count([]))

    report = env["aifa.impact.report"].create({
        "name": "Demo impact statement",
        "donor": "p4g",
        "period_start": fields.Date.today() - timedelta(days=90),
        "period_end": fields.Date.today(),
    })
    report.action_compute()
    step("Impact: %.0f kg sourced, %.0f kg post-harvest loss averted, "
         "%s outgrowers (%.0f%% women), %.0f%% of scrap valorised"
         % (report.fruit_sourced_kg, report.loss_averted_kg, report.active_outgrowers,
            report.women_outgrower_pct, report.scrap_valorised_pct))

    return _summary(env)


# --------------------------------------------------------------------- helpers
def _make_mo(env, bom, qty):
    mo = env["mrp.production"].create({
        "product_id": bom.product_tmpl_id.product_variant_id.id,
        "product_qty": qty,
        "bom_id": bom.id,
        "product_uom_id": bom.product_uom_id.id,
    })
    mo.action_confirm()
    return mo


def _stock_packaging(env, mo):
    """Make sure pouches, sachets, labels and cartons are on hand."""
    for move in mo.move_raw_ids:
        if move.product_id.categ_id.name.startswith("Packaging"):
            env["stock.quant"]._update_available_quantity(
                move.product_id, move.location_id, move.product_uom_qty * 2
            )
    mo.action_assign()


def _assign_component_lots(mo, mapping):
    """Force each raw move to consume the lot we actually want."""
    mo.action_assign()
    for move in mo.move_raw_ids:
        lots = mapping.get(move.product_id)
        if not lots:
            continue
        move.move_line_ids.unlink()
        remaining = move.product_uom_qty
        for lot in lots:
            if remaining <= 0:
                break
            available = mo.env["stock.quant"]._get_available_quantity(
                move.product_id, move.location_id, lot_id=lot
            )
            if available <= 0:
                raise AssertionError(
                    "No stock of %s under lot %s at %s; the previous stage did not post "
                    "its move." % (move.product_id.display_name, lot.name,
                                   move.location_id.complete_name)
                )
            take = min(remaining, available)
            mo.env["stock.move.line"].create({
                "move_id": move.id,
                "product_id": move.product_id.id,
                "product_uom_id": move.product_uom.id,
                "lot_id": lot.id,
                "quantity": take,
                "location_id": move.location_id.id,
                "location_dest_id": move.location_dest_id.id,
            })
            remaining -= take


def _finish_mo(env, mo, lot_name):
    """Close a manufacturing order the way the web client does.

    Two Odoo 17 details matter here and are easy to get wrong when scripting:

    * ``qty_producing`` and ``lot_producing_id`` must be set through a ``Form``
      so the onchange chain fills the finished move. Writing them directly
      leaves the finished move at zero, and ``_post_inventory`` then cancels
      the order instead of completing it.
    * a component only counts as consumed when its move carries ``picked``;
      otherwise the order stalls at "to_close" behind a consumption warning.
    """
    lot = env["stock.lot"].search([
        ("name", "=", lot_name), ("product_id", "=", mo.product_id.id)
    ], limit=1)
    if not lot:
        lot = env["stock.lot"].create({
            "name": lot_name,
            "product_id": mo.product_id.id,
            "company_id": env.company.id,
        })
    form = Form(mo)
    form.qty_producing = mo.product_qty
    form.lot_producing_id = lot
    mo = form.save()
    mo.move_raw_ids.picked = True
    result = mo.button_mark_done()
    if isinstance(result, dict) and result.get("res_model"):
        raise AssertionError(
            "%s returned the %s wizard; the seed expects a clean completion."
            % (mo.name, result["res_model"])
        )
    if mo.state != "done":
        raise AssertionError(
            "Manufacturing order %s did not complete (state=%s)" % (mo.name, mo.state)
        )
    return lot


def _summary(env):
    print("\n--- Summary ---")
    for line in LOG:
        print("  %s" % line)
    print("\nOpen the database and look at Aifa Agro > Processing > Dehydration Runs,")
    print("then Traceability > Lot Genealogy on the finished goods lot.\n")
    return True


if "env" in dir():
    seed(env)          # noqa: F821  (provided by `odoo-bin shell`)
    env.cr.commit()    # noqa: F821
