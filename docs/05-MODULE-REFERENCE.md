# Module Reference

Technical reference for the seven Aifa add-ons: models, the fields that carry
meaning, REST endpoints, and the places you are most likely to need to extend.

Target platform: **Odoo 17.0 Community**. Notes on 18.0 at the end.

---

## Dependency graph

```
aifa_base
  └── aifa_sourcing
        └── aifa_processing
              └── aifa_quality
                    ├── aifa_traceability
                    ├── aifa_consignment
                    └── aifa_impact
```

`aifa_base` is the only module flagged `application`; it owns the **Aifa Agro**
root menu and the section menus that the others hang items from.

---

## aifa_base

| Model | Purpose |
|---|---|
| `aifa.region` | Sourcing region. `code` is embedded in raw intake lot numbers |
| `aifa.collection.centre` | Rural aggregation depot, optionally mapped to a warehouse |
| `aifa.crop` | Commodity master. **This is where the process standards live** |
| `aifa.crop.variety` | Cultivar, with its own yield and Brix overrides |

### `aifa.crop` — the standards record

| Field | Meaning |
|---|---|
| `prep_yield_pct` | Standard kg prepped per 100 kg accepted raw |
| `dry_yield_pct` | Standard kg dried per 100 kg prepped |
| `yield_tolerance_pct` | Percentage points of drift tolerated before a run is flagged |
| `overall_ratio` | Computed kg fresh per 1 kg dried |
| `target_moisture_pct`, `target_water_activity` | Release limits, consumed by the quality gates |
| `drying_temp_min/max`, `drying_hours_min/max` | Validated profile band; excursions are flagged |
| `shelf_life_days` | Feeds expiry and therefore FEFO |

`crop.expected_dried_kg(raw_kg)` gives the standard dried output for a given
farm-gate weight — useful when writing planning logic.

### Security groups

`group_aifa_field_agent`, `group_aifa_receiving`, `group_aifa_operator`,
`group_aifa_packaging_lead`, `group_aifa_qa_manager`, `group_aifa_warehouse`,
`group_aifa_route_sales`, `group_aifa_finance`, `group_aifa_manager`.

Implication chains are deliberately narrow: a QA manager implies a receiving
inspector, a packaging lead implies an operator, and the executive implies
everything. QA does **not** imply finance.

---

## aifa_sourcing

| Model | Purpose |
|---|---|
| `aifa.cooperative` | Farmer group, with gender-disaggregated membership |
| `aifa.farmer` | Outgrower, backed by a `res.partner` for accounting |
| `aifa.farmer.plot` | Plot with GPS, acreage, cultivar, expected season yield |
| `aifa.grade.price` | Dated farm-gate price by crop, grade and optionally region |
| `aifa.field.purchase` / `.line` | A depot buying session |
| `aifa.intake.batch` | **One farmer + one crop + one weighing = one lot** |
| `aifa.farmer.payout` | Settlement run with deductions and wallet export |

### Intake batch state machine

```
draft → weighed → in_transit → received → accepted → done
                                    ↓
                                 rejected
```

`action_qa_accept` re-prices on re-grade, runs advisory gate checks, then creates
the `stock.lot` and a validated incoming `stock.picking`. `action_qa_reject`
requires an inspection note.

Lot number is built by `_build_lot_number()`:
`LOT-RAW-<CROP>-<REGION>-<YYYYMM>-<SEQ>`.

### Pricing resolution

`self.env["aifa.grade.price"].price_for(crop, grade, region=..., date=...)`

Region-specific lines win over national ones. A missing price raises a
`UserError` naming the crop and grade rather than silently defaulting to zero.

### REST endpoints

All `type="json"`, `auth="user"`, POST.

| Endpoint | Purpose |
|---|---|
| `/aifa/api/v1/sourcing/bootstrap` | Everything the offline client caches: farmers, crops, price matrix |
| `/aifa/api/v1/sourcing/field-purchase` | Replay an offline buying session |
| `/aifa/api/v1/sourcing/intake` | Replay a single walk-in weighing |
| `/aifa/api/v1/sourcing/intake/<lot_number>` | Read one intake batch |

**Idempotency.** Every write endpoint requires `client_ref`, a device-generated
UUID with a unique constraint. Replaying a document returns the existing record
with `"duplicate": true` rather than creating a second one, so a dropped response
on a flaky link is harmless.

**Pricing is server-side.** The client sends crop and grade, never a price.

> Authentication is the standard Odoo session. Put an API-key or OAuth2 bearer
> layer in front of this before exposing it beyond the plant VPN.

---

## aifa_processing

| Model | Purpose |
|---|---|
| `aifa.dehydrator` | Physical chamber: trays, rated wet load, power, tariff, CIP date |
| `aifa.prep.log` / `aifa.prep.scrap` | Stage-1 mass balance, scrap by cause and destination |
| `aifa.dehydration.run` | Stage-2 chamber load, from tray-in to release |

Extensions: `aifa_stage` and `aifa_crop_id` on `mrp.bom` and `mrp.production`,
`aifa_is_primary` on `mrp.bom.line`, plus stage yield roll-ups on the MO.

### Stage vocabulary

`models/aifa_stage.py` holds `PROCESS_STAGES` (`prep`, `dry`, `condition`,
`pack`) and `SCRAP_CAUSES`. Extend there so BOMs, MOs, prep logs and reports stay
in agreement.

### Prep log mass balance

```
raw_input_kg  =  prepped_output_kg  +  scrap_total_kg  +  unaccounted_kg
```

`action_confirm` refuses when `abs(unaccounted_kg)` exceeds the greater of 1% of
input or 1 kg. This is intentional friction.

### Dehydration run state machine

```
draft → running → unloaded → released
                      ↓
                 quarantine → (re-dry as a new run)
```

- `action_start` blocks on a chamber already running or under maintenance, and
  warns when no CIP has ever been logged.
- `action_unload` assigns the WIP lot code and runs `_evaluate_moisture_gate()`.
- `action_release` refuses while `qa_blocked` is set, quoting both measurements.
- `action_redry` copies the run with the dry weight as the new wet load.
- A `@api.constrains` refuses a wet load above 105% of the chamber's rating.

`_compute_excursion` flags a run whose achieved profile fell outside the crop's
validated temperature or duration band.

---

## aifa_quality

| Model | Purpose |
|---|---|
| `aifa.control.point` | A CCP or OPRP with limits, frequency, method, corrective action |
| `aifa.control.option` | Named outcomes for option-type checks |
| `aifa.quality.check` | One measurement against one control point on one subject |
| `aifa.ncr` | Non-conformance with root cause, disposition and CAPA |
| `aifa.checkweigh.session` / `.sample` | Packing line SPC |
| `aifa.sanitation.log` | CIP record with ATP swab and sign-off |

Extensions on `stock.lot`: `aifa_quality_state`, `aifa_check_ids`,
`aifa_origin_intake_ids`, `aifa_origin_run_ids`, and `aifa_dossier_checks()`.

### Shipped control points

| Code | Stage | Type | Limit |
|---|---|---|---|
| `QA-01` | Intake | Quality | Brix 10–25 |
| `OPRP-01` | Intake | OPRP | Visual decay ≤ 10%, blocking |
| `CCP-1` | Prep | CCP | Wash free chlorine 50–200 ppm, blocking |
| `OPRP-02` | Dry | OPRP | Average temperature 50–70 °C |
| `CCP-2` | Condition | CCP | Residual moisture ≤ crop limit, blocking |
| `CCP-3` | Condition | CCP | Water activity 0.35–0.60, blocking |
| `CCP-4` | Pack | CCP | Metal detection test pieces pass, blocking |
| `OPRP-03` | Pack | OPRP | Seal integrity, blocking |
| `OPRP-04` | Pack | OPRP | Label / lot / expiry verified, blocking |

`use_crop_moisture_limit` and `use_crop_aw_limit` make one control point serve
crops with different specifications by resolving the limit from `aifa.crop` at
check time.

### What a failure does

`action_record` on a failing check:
1. posts the measurement and the standing corrective action to the chatter;
2. if the point is blocking, quarantines the subject — run state, lot quality
   state, intake note;
3. opens an `aifa.ncr` pre-filled with the measurement and a severity derived
   from the point type.

`action_waive` grants a concession. It requires a written justification and is
permanently attributed to the user who granted it.

### Check-weighing

`_compute_tne` implements the standard prepackaged-goods tolerable negative error
bands (9% up to 50 g, 4.5 g to 100 g, 4.5% to 200 g, and so on). The session
reports mean, standard deviation, giveaway, packs below 1× and 2× TNE, Cpk
against the declared weight, and a verdict of *compliant*, *adjust* or
*non-compliant*.

---

## aifa_traceability

| Model | Purpose |
|---|---|
| `stock.lot` (extended) | `aifa_parent_lot_ids` / `aifa_child_lot_ids` genealogy |
| `aifa.recall` / `.line` | Drill or live recall with its resolved distribution |

### Genealogy

`_direct_parent_lots()` finds the MOs that produced a lot and returns the lots
their raw moves consumed. `action_rebuild_genealogy()` walks that backwards to a
configurable depth (default 8), caches the ancestors, and resolves the farm-gate
intake batches and dehydration runs.

Rebuild is cached rather than live because an EFDA inspector asking for the farm
of origin of a pouch would otherwise trigger a recursive walk across three
manufacturing stages. A daily cron catches up lots that have never been resolved.

### Downstream and recalls

`aifa_downstream_moves()` returns every done move line that put the lot, or a
descendant, beyond Aifa's walls. It covers customer and supplier destinations
**and** the consignment location tree — consigned stock sits in an internal
location, so a customer-usage filter alone would report a clean recall while the
product is still on a shelf.

`aifa.recall` seeds from an intake batch, a drying run or a lot, resolves the
family, records every destination with quantities, and reports the trace
duration. `action_notify_customers` refuses while `is_drill` is set.

### Public endpoints

| Route | Auth | Returns |
|---|---|---|
| `GET /trace/<lot_code>` | public | Consumer provenance page |
| `POST /aifa/api/v1/traceability/<lot_code>` | public | The same payload as JSON |

`aifa_public_payload()` exposes region, cooperative, outgrower count, share of
women, harvest dates, fresh kg, drying records and quality checks. It
deliberately exposes **no farmer name, phone number, national ID or price**.

---

## aifa_consignment

| Model | Purpose |
|---|---|
| `res.partner` (extended) | `aifa_channel`, `aifa_is_consignment`, shelf location and balance |
| `aifa.consignment` | One product+lot placement on one partner's shelf |
| `aifa.shelf.count` / `.line` | A merchandiser visit that bills the sell-through |
| `aifa.route.trip` / `.stop` | A van's day, with settlement |

`partner._aifa_get_consignment_location()` lazily creates an internal location
under `stock_location_consignment_root` the first time stock is placed.

`action_place` builds and validates an internal transfer; a constraint refuses to
place a lot whose `aifa_quality_state` is not `released`.

`action_create_sale_order` on a confirmed count raises the order and invoice for
exactly the units that sold. A count line refuses to save when counted plus
returned exceeds what was placed.

---

## aifa_impact

| Model | Purpose |
|---|---|
| `aifa.daily.kpi` | One materialised snapshot per day per crop |
| `aifa.impact.assumption` | Dated, cited counterfactual loss rate per crop and region |
| `aifa.impact.report` | Period ESG statement |

`_build_for_date(date, crop)` upserts a snapshot; `cron_build_snapshots(days_back)`
rebuilds the last few days so late data entry is picked up. Snapshots are
materialised so the executive dashboard opens instantly on a tablet over a
congested link.

`yield_gap_value` is the headline: the birr value of the gap between actual and
standard yield. It is the number the plant manager is paid to shrink.

`aifa.impact.assumption.source` is **required**. An uncited assumption is an
opinion, and the first thing a donor auditor asks about a loss-averted figure is
what baseline it was measured against.

---

## Extension points

| You want to… | Do this |
|---|---|
| Change a yield standard | Edit `aifa.crop` — master data, not code |
| Add a HACCP control point | Create an `aifa.control.point` record |
| Add a processing stage | Extend `PROCESS_STAGES` in `aifa_processing/models/aifa_stage.py` |
| Add a scrap cause | Extend `SCRAP_CAUSES` in the same file |
| Change the intake lot format | Override `aifa.intake.batch._build_lot_number()` |
| Change the WIP lot format | Override `aifa.dehydration.run._build_wip_lot()` |
| Add a field to the offline sync | Extend `_api_payload()` and the controller in `aifa_sourcing/controllers/sync_api.py` |
| Change what the public page shows | Override `stock.lot.aifa_public_payload()` |
| Add a KPI | Extend `aifa.daily.kpi._build_for_date()` |

---

## Odoo 18 notes

The suite targets 17.0. Moving to 18.0 needs:

- `<tree>` → `<list>` in every view
- `<div class="oe_chatter">` → `<chatter/>`
- `mrp.production.date_planned_start` → `date_start` (the modules avoid this
  field in Python; check any reports you add)
- `product.product.type` semantics changed — `type='product'` became
  `is_storable`

The Python business logic, the controllers and the security model carry over
unchanged.

---

## Testing

```bash
odoo -d <db> --addons-path=<core>,<repo>/addons \
    -i aifa_base,aifa_sourcing,aifa_processing,aifa_quality,aifa_traceability,aifa_consignment,aifa_impact \
    --stop-after-init

odoo shell -d <db> --addons-path=<core>,<repo>/addons < tools/seed_demo.py
```

`tools/seed_demo.py` asserts at every stage: a manufacturing order that does not
reach `done` and a component with no stock both raise rather than silently
producing an empty demo.

Two Odoo 17 details the seed documents, because they are easy to get wrong when
scripting MRP:

- `qty_producing` and `lot_producing_id` must be set through a `Form` so the
  onchange chain fills the finished move. Writing them directly leaves the
  finished move at zero and `_post_inventory` then **cancels** the order.
- A component only counts as consumed when its move carries `picked`; otherwise
  the order stalls at `to_close` behind a consumption warning.
