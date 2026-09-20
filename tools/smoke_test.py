# -*- coding: utf-8 -*-
"""Read-only health check for an Aifa deployment.

    odoo shell -d <db> --addons-path=<core>,<repo>/addons < tools/smoke_test.py

Checks nothing but facts already in the database, makes no writes, and prints a
PASS/FAIL line per check. Use it after installing on a new host, after an
upgrade, and before a client demo.

Checks marked [seeded] only apply once tools/seed_demo.py has been run; they
report SKIP rather than FAIL on a freshly installed database.
"""

RESULTS = []

MODULES = [
    "aifa_base", "aifa_sourcing", "aifa_processing", "aifa_quality",
    "aifa_traceability", "aifa_consignment", "aifa_impact",
]

GROUPS = [
    "group_aifa_field_agent", "group_aifa_receiving", "group_aifa_operator",
    "group_aifa_packaging_lead", "group_aifa_qa_manager", "group_aifa_warehouse",
    "group_aifa_route_sales", "group_aifa_finance", "group_aifa_manager",
]


def check(name, ok, detail=""):
    RESULTS.append((name, "PASS" if ok else "FAIL", detail))


def skip(name, detail=""):
    RESULTS.append((name, "SKIP", detail))


def run(env):
    # ---------------------------------------------------------------- install
    installed = env["ir.module.module"].search([
        ("name", "in", MODULES), ("state", "=", "installed"),
    ]).mapped("name")
    missing = sorted(set(MODULES) - set(installed))
    check("All seven modules installed", not missing,
          "missing: %s" % ", ".join(missing) if missing else "%s/7" % len(installed))

    found_groups = [g for g in GROUPS
                    if env.ref("aifa_base.%s" % g, raise_if_not_found=False)]
    check("Nine security personas present", len(found_groups) == 9,
          "%s/9" % len(found_groups))

    # ---------------------------------------------------------------- master data
    crops = env["aifa.crop"].search([])
    check("Crop master populated", len(crops) >= 3, "%s crop(s)" % len(crops))

    bad_yields = crops.filtered(
        lambda c: not (0 < c.prep_yield_pct <= 100 and 0 < c.dry_yield_pct <= 100)
    )
    check("Crop yield standards are sane", not bad_yields,
          "bad: %s" % ", ".join(bad_yields.mapped("name")) if bad_yields else "")

    tomato = crops.filtered(lambda c: c.code == "TOMA")
    if tomato:
        # The whole point of the per-crop factors: tomato must not be sharing
        # pineapple's ratio. Anything under ~12:1 means it was reset to a
        # generic value and the raw material budget for that line is wrong.
        check("Tomato ratio is crop-specific (>12:1)", tomato.overall_ratio > 12,
              "%.1f : 1" % tomato.overall_ratio)
    else:
        skip("Tomato ratio is crop-specific", "no TOMA crop configured")

    points = env["aifa.control.point"].search([])
    blocking = points.filtered("is_blocking")
    check("HACCP control points loaded", len(points) >= 5,
          "%s point(s), %s blocking" % (len(points), len(blocking)))

    ccps = points.filtered(lambda p: p.point_type == "ccp")
    check("Every CCP blocks release",
          all(p.is_blocking for p in ccps),
          "%s CCP(s)" % len(ccps))

    # ---------------------------------------------------------------- sequences
    seq_codes = ["aifa.intake.batch", "aifa.dehydration.run", "aifa.quality.check",
                 "aifa.ncr", "aifa.consignment", "aifa.recall"]
    missing_seq = [c for c in seq_codes
                   if not env["ir.sequence"].search([("code", "=", c)], limit=1)]
    check("Lot and document sequences present", not missing_seq,
          "missing: %s" % ", ".join(missing_seq) if missing_seq else "")

    # ---------------------------------------------------------------- company
    company = env.company
    is_etb = company.currency_id.name == "ETB"
    check("Company currency is ETB", is_etb,
          "" if is_etb else
          "currency is %s. Odoo refuses a currency change once journal items "
          "exist, so recreate the database with Ethiopia as the country."
          % company.currency_id.name)

    # ---------------------------------------------------------------- seeded data
    batches = env["aifa.intake.batch"].search([("state", "=", "done")])
    if not batches:
        for name in ("Farm-gate lots created", "Genealogy resolves to the farm gate",
                     "Recall trace reaches distribution", "KPI snapshots built"):
            skip(name, "run tools/seed_demo.py first")
    else:
        check("Farm-gate lots created", all(b.lot_id for b in batches),
              "%s batch(es) stocked" % len(batches))

        fg_lots = env["stock.lot"].search([("aifa_origin_intake_ids", "!=", False)])
        check("Genealogy resolves to the farm gate", bool(fg_lots),
              "%s lot(s) with resolved origin" % len(fg_lots))

        recalls = env["aifa.recall"].search([("state", "!=", "draft")])
        if recalls:
            reached = any(r.line_ids for r in recalls)
            check("Recall trace reaches distribution", reached,
                  "%s line(s) across %s recall(s)"
                  % (sum(len(r.line_ids) for r in recalls), len(recalls)))
        else:
            skip("Recall trace reaches distribution", "no recall run yet")

        kpis = env["aifa.daily.kpi"].search([])
        check("KPI snapshots built", bool(kpis), "%s snapshot(s)" % len(kpis))

        blocked = env["aifa.dehydration.run"].search([("qa_blocked", "=", True)])
        if blocked:
            check("Quarantine gate is holding stock", True,
                  "%s run(s) blocked from packing" % len(blocked))
        else:
            skip("Quarantine gate is holding stock",
                 "no failing run in this dataset")

    # ---------------------------------------------------------------- report
    width = max(len(n) for n, _s, _d in RESULTS) + 2
    print("\n" + "=" * (width + 30))
    print("Aifa deployment smoke test")
    print("=" * (width + 30))
    for name, status, detail in RESULTS:
        print("  %-6s %-*s %s" % (status, width, name, detail))
    failed = [r for r in RESULTS if r[1] == "FAIL"]
    skipped = [r for r in RESULTS if r[1] == "SKIP"]
    print("-" * (width + 30))
    print("  %s passed, %s failed, %s skipped"
          % (len(RESULTS) - len(failed) - len(skipped), len(failed), len(skipped)))
    if failed:
        print("\n  Deployment is NOT healthy. Failing checks above.")
    else:
        print("\n  Deployment looks healthy.")
    print()
    return not failed


if "env" in dir():
    run(env)           # noqa: F821  (provided by `odoo-bin shell`)
    env.cr.rollback()  # noqa: F821  (read-only by construction)
