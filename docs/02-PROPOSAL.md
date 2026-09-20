# Aifa Foods Agro-Processing ERP — Proposal v3.0

**Client:** Yarashoo Agro Industry PLC, trading as Aifa Foods
**Platform:** Odoo 17.0 Community Edition (LGPLv3) + seven custom add-ons
**Supersedes:** v2.4, September 2026
**Status:** Working demo built and verified; commercial terms carried forward from v2.4

---

## 1. What is different about this version

v2.4 was a specification. v3.0 is a specification **plus a working system you can
open and click through**. Seven custom Odoo modules have been built, installed on
a clean Odoo 17 Community database, and driven through a complete farm-to-shelf
cycle with real data. Section 3 lists what runs today; section 6 lists what does not.

Three substantive changes to the v2.4 content:

1. **The workflow is now written down** (`docs/01-WORKFLOW-BLUEPRINT.md`), with
   every assumption tagged and twelve open questions listed for Phase 1. v2.4
   specified requirements without a process model; that gap was the largest
   schedule risk in an eight-week plan.
2. **Yield factors are corrected and made per-crop.** v2.4 applies a single
   8:1–10:1 fresh-to-dry ratio. Tomato is roughly 15:1. Planning a tomato line on
   a pineapple factor understates the raw material budget for that line by about
   half. See §2.1.
3. **Two scope items in v2.4 are not deliverable as written**, and we say so
   rather than discovering it in week six. See §6.

Everything else — scope, phasing, price, milestones — is carried forward
unchanged.

---

## 2. Corrections and findings

### 2.1 Fresh-to-dried ratios are not one number

| Crop | Prep yield | Drying yield | Fresh : dried | v2.4 said |
|---|---|---|---|---|
| Pineapple | 55% | 17% | **10.7 : 1** | 8–10 : 1 ✅ close |
| Mango | 65% | 20% | **7.7 : 1** | 8–10 : 1 ✅ close |
| Tomato | 95% | 7.2% | **14.6 : 1** | 8–10 : 1 ❌ understates by ~50% |

Tomato is about 94% water against roughly 86% for pineapple. The arithmetic is
not close enough to share a factor. These figures now live in the `aifa.crop`
master record, per crop and per cultivar, and every production run is scored
against them.

They are still **baselines**, not measurements. Phase 1 must re-derive them from
three trial batches per crop and per dominant cultivar. The system is built so
that recalibrating is a master-data change, not a code change.

### 2.2 A conditioning step is missing from v2.4

Fruit leaving a chamber has uneven moisture across the load. Testing straight off
the tray gives an optimistic result and a shelf-life claim that the product may
not honour. Standard practice is 12–24 hours of equilibration in sealed bins
before the release test, sampling at least three points across the load. This is
now Stage 2b in the blueprint and is modelled in the system.

### 2.3 Water activity needs a floor as well as a ceiling

v2.4 specifies a_w < 0.60. Correct, and it is the food-safety limit. But dried
below roughly a_w 0.35–0.40 these fruits go brittle and lose the pliable chew the
brand is built on. The control point therefore carries both limits.

### 2.4 Odoo's Quality app is Enterprise-only

v2.4 proposes Odoo Community and separately assumes quality gates. Odoo's
`quality` and `quality_control` modules are not in Community Edition. The
`aifa_quality` module in this proposal is the Community-edition equivalent,
shaped around Aifa's own HACCP plan rather than a generic inspection engine.
This is not a change in price — it was already inside the "Custom Odoo
Agro-Processing Module" and "QA Gateways" line items — but it is a change in what
those line items contain.

---

## 3. What has been built and verified

Seven modules, installed together on Odoo 17.0 Community with demo data, driven
end to end by `tools/seed_demo.py`.

### 3.1 `aifa_base` — master data and roles
Sourcing regions and collection centres; crop and cultivar master carrying the
yield, moisture, water-activity and drying-profile standards; the nine
operational personas from the FRS as security groups; lot-numbering sequences;
and the full Aifa product catalogue (raw fruit → prepped WIP → dried bulk →
retail SKUs → packaging) as demo data.

### 3.2 `aifa_sourcing` — outgrowers and farm gate (FRS-M1)
Outgrower and cooperative registry with plot GPS, acreage, cultivar and harvest
window. Dated farm-gate price matrix by crop, grade and region. Field purchase
orders capturable offline and replayed through an **idempotent** JSON endpoint
keyed on a device UUID. Raw intake batches with gross/tare/net weighing, Brix and
decay index, automatic lot serialisation, and creation of the matching Odoo
receipt and stock lot. Payout ledger with advance and crate-deposit deductions
and a bulk mobile-money export. QR + GS1-128 crate label.

### 3.3 `aifa_processing` — the shop floor (FRS-M2, FRS-M3)
Stage tagging on BOMs and manufacturing orders (prep / dry / pack), so the
three-level chain is explicit and reportable. Prep logs with scrap broken down by
cause and destination, and a mass-balance guard that refuses to confirm a log
that does not balance. Dehydration runs as first-class records: chamber, tray
load, temperature profile, wet-in / dry-out, residual moisture, water activity,
kWh and operator. Yield variance scored against the crop standard, raising a task
on drift. Chamber capacity enforced at run creation.

### 3.4 `aifa_quality` — food safety (FRS-M4)
HACCP control point definitions with critical limits, monitoring frequency and
standing corrective action. Polymorphic quality checks covering numeric, pass/fail
and option results. **A failure on a blocking control point quarantines the lot
automatically** and opens a non-conformance report. NCR with root cause category,
disposition and CAPA, not closable without both. Check-weighing with mean,
standard deviation, giveaway, TNE breaches and Cpk. Sanitation / CIP logs with
sign-off. Per-lot EFDA and export audit dossier.

### 3.5 `aifa_traceability` — farm to shelf (FRS-4.5, FRS-5.3)
Materialised lot genealogy walking stock moves back through all three
manufacturing stages to the farm gate. Recall simulation that resolves every
finished lot and every destination reached — **including consigned stock sitting
in supermarket shelf locations**, which a naive customer-location filter misses.
Public `/trace/<lot>` provenance page reachable from the QR on the pouch,
exposing region, cooperative, outgrower count, drying record and quality results,
and deliberately exposing no farmer personal data or commercial terms.

### 3.6 `aifa_consignment` — distribution (FRS-M6)
Per-customer consignment locations so shelf stock stays on Aifa's balance sheet
until a count proves sell-through. Shelf counts that reconcile placed against
counted against returned and bill exactly what sold. Van route trips with
signature capture and an end-of-day settlement that refuses to close on unvisited
stops.

### 3.7 `aifa_impact` — analytics and ESG (FRS-M8)
Nightly plant KPI snapshots: intake, prepped and dried kilograms, realised yield
against standard, **the yield gap valued in birr**, kWh per kg, chamber
utilisation, first-pass quality rate and cost per kg dried. P4G / CARE impact
statement whose post-harvest-loss figure derives from dated, cited, per-crop
counterfactual assumptions rather than a hard-coded rate — because the first
question a donor auditor asks is "against what baseline?".

### 3.8 Verified end to end

A single scripted run produces, on a clean database:

```
Confirmed 3 field purchases
Received 5 intake batches at the plant
QA-accepted 5 batches; 3,209.2 kg stocked under farm-gate lots
Paid an outgrower, net of advance recovery
Stage 1 prep: 878.4 kg raw -> 483.1 kg prepped (55.00% against a 55.00% standard)
Stage 2 dry: 480.0 kg wet -> 81.6 kg dried at 17.0% yield, 4.510 kWh/kg
Release checks recorded; dried lot released
Stage 3 pack: 720 pouches
Check-weigh: mean 102.08 g, sd 0.74 g
Genealogy: 2 farm-gate lots, 1 drying run, 2 outgrowers across Gamo / Arba Minch
Consignment: 120 placed, 64 sold, invoice raised for the 64
Mock recall: 2 lots, 1 customer destination, traced in under a second
Impact: 3,209 kg sourced, 1,135 kg post-harvest loss averted, 60% women outgrowers
```

---

## 4. Architecture

Unchanged from v2.4 in substance, restated for precision.

| Layer | Technology | Responsibility |
|---|---|---|
| ERP core | Odoo 17.0 Community (LGPLv3) | MRP, Inventory, Purchase, Sales, Invoicing, lot tracking, FEFO |
| Agro add-ons | The seven modules above | Everything specific to fruit dehydration |
| Database | PostgreSQL 16 | ACID transactions; the audit trail depends on this |
| Plant edge | On-premises Odoo worker | Floor operations continue through an internet outage |
| Mobile edge | Offline client with local queue | Rural buying without connectivity |
| Integration | JSON-RPC + the module REST endpoints | Scale telemetry, mobile sync, fiscal device, payment gateways |

**On the mobile client:** the server side is built and tested — bootstrap,
idempotent field-purchase replay, standalone intake replay and public
traceability lookup. The client application itself is a separate build; see §6.

---

## 5. Security model

Nine personas as Odoo security groups, with record-level access rules:

Field Sourcing Agent · Receiving Inspector · Processing Operator · Packaging Line
Lead · QA/QC Manager · Warehouse Custodian · Route Sales / Van Driver · Finance
Accountant · Executive / Plant Manager

Three deliberate constraints:

- **Only a QA Manager** can release a quarantined lot or grant a concession, and
  a concession is permanently attributed.
- **Only Finance** can approve and settle a payout. Accrual and settlement are
  separate actions, because cash at a rural depot should never be one person's
  decision.
- **A field agent cannot set a price.** The mobile app sends crop and grade; the
  server resolves the price from the dated matrix.

Confirm the exact authorisation boundaries in Phase 1 (blueprint question 11).

---

## 6. What is not built, and what is not deliverable as specified

Stated plainly so it is not discovered in week six.

### 6.1 Built server-side, client application still to build

| Item | Status |
|---|---|
| Offline mobile app for rural sourcing | Server API built, tested and idempotent. The Flutter/PWA client is a separate build, in scope under commercial line item 4. |
| Bluetooth scale integration | Data model and API accept machine-weighed readings and flag them as such. The device pairing layer is part of the mobile client build. |

### 6.2 Specified in v2.4 but not deliverable as written

| v2.4 item | Issue | Recommendation |
|---|---|---|
| **MoR e-invoicing / ETR fiscal integration** (FRS-7.3) | Ethiopian fiscal device integration depends on the certified vendor's device and current MoR technical specification. We can build VAT, withholding and TOT calculation and an export-ready invoice payload, but we cannot certify a device integration we have not been given the specification for. | Keep the dual-track approach v2.4 already proposes: compliant manual fiscal generation at go-live, digital sync as a scoped follow-on once the device and specification are in hand. Do not make go-live depend on it. |
| **Amharic UI throughout** (NFR 6.3) | Odoo's own Amharic translation coverage is partial. Our modules' strings are all translatable and we will supply Amharic translations for them, but core Odoo screens will be partly English. | Translate the custom modules fully, plus the ~200 core strings the floor roles actually see. Budget a translation review in Phase 5 rather than assuming completeness. |
| **99.8% uptime SLA** (NFR 6.4) | Achievable for the cloud core. Not achievable end to end if the plant's power and connectivity are the binding constraint, which in Addis they will be. | State the SLA against the hosted service, with the edge appliance and UPS as the plant-side mitigation. Measure and report both. |

### 6.3 Deliberately out of scope until the workflow is confirmed

Harvest volume predictive analytics (FRS-1.8, priority Low) depends on at least
one full season of plot-level actuals. Building a forecast on a data set that
does not yet exist produces a number nobody should trust. Recommend deferring to
a post-go-live phase.

---

## 7. Implementation plan

Carried forward from v2.4 with one change: Phase 1 now has a defined output, the
signed-off workflow blueprint answering the twelve open questions.

| Phase | Duration | Deliverable | Sign-off gate |
|---|---|---|---|
| 1. Discovery & blueprint | Week 1 | On-site process walk; **the twelve open questions answered**; three trial batches per crop weighed to calibrate yields | Approved blueprint |
| 2. Core setup & config | Weeks 2–3 | Odoo server, PostgreSQL, Ethiopian chart of accounts, warehouses, FEFO, master data | Working sandbox |
| 3. Add-on deployment & mobile | Weeks 4–5 | The seven modules configured to the signed blueprint; offline mobile client | Staging validation |
| 4. Hardware & pilot | Week 6 | Label printers, scale telemetry, scanner workflows, one shadow production day | Hardware acceptance |
| 5. Training & UAT | Week 7 | Role-based training in Amharic and English; formal UAT | UAT sign-off |
| 6. Migration & go-live | Week 8 | Opening balances, cutover, live shift supervision | Go-live certificate |
| 7. Hypercare | Weeks 9–10 | On-site standby, daily reconciliation, report tuning, source handover | Completion certificate |

**Schedule risk.** The eight-week plan assumes Phase 1 answers the twelve
questions inside one week and that trial batches can be run that week. If the
plant cannot release fruit for calibration trials in week 1, yields stay at
baseline and every variance alert is noise until they are corrected. Flag this
at kickoff.

---

## 8. Commercial terms

Unchanged from v2.4.

| Component | ETB |
|---|---|
| 1. Discovery, gap analysis & blueprint | 50,000 |
| 2. Core configuration & master data | 70,000 |
| 3. Custom agro-processing module | 110,000 |
| 4. Rural sourcing & offline mobile app | 95,000 |
| 5. QA gateways, FEFO & lot traceability | 65,000 |
| 6. B2B consignment & route distribution | 45,000 |
| 7. Hardware telemetry & thermal labelling | 30,000 |
| 8. Training, cutover & hypercare | 35,000 |
| **Total fixed fee** | **500,000 ETB** |

Software licensing: **zero**. Odoo Community is LGPLv3 and the seven custom
modules are delivered under the same licence, with source.

Recommended hardware (client procurement): **295,000 ETB**.
Annual hosting, updates and support SLA: **290,000 ETB/year**.

Milestones: 25% / 25% / 25% / 15% / 10% as set out in v2.4 §10.4.

---

## 9. Return on investment

v2.4's ROI case is sound and is carried forward. Two refinements from having
built the system:

**Yield optimisation.** v2.4 claims 2.5% improvement worth ~350,000 ETB/year. The
system now *measures* this directly: the daily KPI snapshot values the gap
between actual and standard yield in birr. The claim becomes an instrument
reading rather than a projection — which also means it can be disproved, and
should be tracked from day one.

**Working capital.** v2.4 claims a 42 → 18 day cash conversion cycle, unlocking
~650,000 ETB. This is the strongest item in the business case and it rests
entirely on the consignment loop in §3.6. It is worth more than the whole project
fee in year one.

**One caution on the loss-averted figure.** The ESG number depends on the
counterfactual loss rate. We ship 30% for pineapple, 35% for mango and 40% for
tomato with citations, but the rate CARE and P4G will accept should be agreed
with them before it appears in a donor report, not after.

---

## 10. Recommendation

Proceed to Phase 1 on the existing commercial terms, with the explicit output of
a signed workflow blueprint answering the twelve open questions and calibrated
yields from real trial batches.

Demonstrate the working system to the plant manager and QA manager **before**
Phase 1 closes. The fastest way to surface a wrong assumption is to show someone
who runs the line a screen that encodes it.

---

## 11. Acceptance

| For Yarashoo Agro Industry PLC (Aifa Foods) | For the implementation team |
|---|---|
| Name: ______________________________ | Name: ______________________________ |
| Title: Executive Managing Director | Title: Lead Enterprise Architect |
| Date: ______________________________ | Date: ______________________________ |
| Signature: __________________________ | Signature: __________________________ |
