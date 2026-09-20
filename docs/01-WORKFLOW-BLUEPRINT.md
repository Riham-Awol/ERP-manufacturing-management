# Aifa Foods — Agro-Processing Workflow Blueprint

**Status:** Draft for Phase 1 discovery validation
**Version:** 1.0 · September 2026
**Audience:** Yarashoo Agro Industry plant management, QA, finance; ERP implementation team

---

## Why this document exists

The v2.4 proposal specifies *what the system must do* (the FRS) but not *how the
plant actually runs*. Nobody on either side has yet walked the line end to end
and written the process down. That gap is the single biggest risk to an
eight-week implementation: you cannot configure a BOM, a quality gate or a lot
numbering scheme without knowing the real sequence of operations.

This blueprint proposes that sequence. It is assembled from three sources, and
every statement is tagged so you can see which:

| Tag | Meaning |
|---|---|
| **[STD]** | Industry standard practice for fruit and vegetable dehydration (FAO fruit & vegetable processing guidance, Codex hygiene codes, HACCP practice). Safe to assume until contradicted. |
| **[PUB]** | Published information about Aifa Foods / Yarashoo specifically. |
| **[DOC]** | Taken from the v2.4 proposal document. |
| **[ASSUMED]** | Our working assumption. **Must be confirmed in Phase 1.** Each one is listed again in §10 with the question to ask. |

Where our research contradicts the v2.4 document, that is called out explicitly.
The most important contradiction is in §4.3.

---

## 1. The value chain in one line

```
Farm gate → Collection centre → Transport → Plant reception → Preparation →
Dehydration → Conditioning → Packing → Finished store → Distribution → Retail shelf
```

Each arrow is a point where mass changes, custody changes, or both. The ERP's
job is to make every one of those changes a record rather than a memory.

---

## 2. Stage 0 — Sourcing at the farm gate

**Who:** Field sourcing agent, at a rural collection centre
**System:** Offline mobile client → `aifa.field.purchase` → `aifa.intake.batch`

### 2.1 Sequence

1. **Harvest booking [ASSUMED].** The agent knows roughly which outgrowers will
   deliver on which day, from the plot register and the cultivar harvest window.
2. **Arrival and gross weighing.** The consignment is weighed in its crates on a
   Bluetooth platform scale. The weight arrives in the app without being typed.
3. **Tare deduction.** Crate count × crate tare. Crates are reusable and are
   tracked as a loan balance against the farmer, because an untracked crate
   fleet disappears at roughly 15–20% per season **[STD]**.
4. **Field grading.** Grade A (export / prime processing), B (standard drying),
   C (salvage — juice, compost, local fresh sale; **never dried**) **[STD]**.
5. **Brix reading** on a small sample. Brix drives the sweetness of the finished
   dried fruit and therefore the sensory profile the brand is built on.
6. **Pricing.** The agent does *not* type a price. The app sends crop + grade
   + region and the server resolves the farm-gate price from a dated matrix.
   This is what makes purchase cost auditable and stops price drift at the depot.
7. **Payout accrual.** The amount is accrued against the farmer, net of input
   advances and unreturned crate deposits. Actual settlement is a separate,
   approved run — cash at a rural depot should never be a single-person action.
8. **Dispatch manifest.** Truck plate, driver, transit tare. Consignments from
   several farmers travel together but stay separately identified.

### 2.2 Why offline-first is not optional

Rural connectivity in Gamo, Sidama and Afar is intermittent **[DOC]**. If the
buying session cannot proceed without a network, the plant loses the
consignment to a competitor or the agent falls back to paper — which is the
process being replaced. The mobile client therefore queues locally and replays
through an idempotent endpoint keyed on a device-generated UUID, so a dropped
response cannot create a duplicate purchase.

### 2.3 Lot identity is born here

```
LOT-RAW-<CROP>-<REGION>-<YYYYMM>-<SEQ>
LOT-RAW-PINE-GMA-202609-00042
```

One farmer + one crop + one weighing = one lot. This is the root of the
genealogy tree; everything downstream inherits from it. It is assigned by the
system, never typed.

---

## 3. Stage 1 — Reception and raw QA at the plant

**Who:** Receiving inspector
**System:** `aifa.intake.batch` → QA gate → `stock.picking` + `stock.lot`

### 3.1 Sequence

1. **Gate weighing.** Re-weigh on arrival. A gap between depot net weight and
   gate net weight is transit loss (juice loss, spillage, theft) and should be
   visible, not absorbed **[STD]**.
2. **Receiving inspection** (control points `QA-01`, `OPRP-01`):
   - visual decay / mould share of the consignment — action limit 10% **[STD]**
   - ripeness uniformity
   - Brix confirmation
   - pulp temperature (matters for fruit that travelled in the sun)
   - foreign matter (stones, plastic, metal)
3. **Accept / partial reject / reject.** A partial reject records the rejected
   kilograms separately so the rejection rate per farmer and per region becomes
   a real metric rather than an argument.
4. **Re-grade if needed.** If the gate grade differs from the field grade, the
   consignment is re-priced automatically and the change is logged with a reason.
   This is the single most common source of farmer disputes, so it must be
   transparent.
5. **Putaway.** Accepted fruit goes to the cold room or raw holding bay, with a
   short shelf life (2–6 days depending on crop) so FEFO applies from the first
   day, not just to finished goods.

### 3.2 Why the gate is a hard boundary

Mouldy fruit entering a wash tank contaminates the whole tank and therefore the
whole shift. Rejecting at the gate costs one consignment; accepting it can cost
a day of production. The system should make rejecting easy and accepting
sloppy fruit hard.

---

## 4. Stage 2 — Preparation

**Who:** Prep line operators, supervisor
**System:** Stage-1 manufacturing order + `aifa.prep.log`

### 4.1 Sequence

1. **Pre-operational sanitation** signed off before the line starts
   (`aifa.sanitation.log`). No signed clean, no production **[STD]**.
2. **Wash / sanitise** — **CCP-1**. Free chlorine 50–200 ppm, or an equivalent
   approved sanitiser, monitored at the start of the shift and after each water
   change **[STD]**. Note that chlorine loses effect above pH 7.5, so pH is
   recorded alongside.
3. **Sort and trim.** Remove decayed, bruised and undersized fruit.
4. **Peel / core / de-crown / de-stone**, crop-specific.
5. **Slice to spec.** Thickness is a process-critical parameter: thicker slices
   dry unevenly and case-harden, thinner slices go brittle. Pineapple ~8 mm,
   mango ~7 mm, tomato halved rather than sliced **[STD/ASSUMED]**.
6. **Pretreatment** — for Aifa, normally **none**. The brand proposition is
   additive-free: no sulphur dioxide, no added sugar **[PUB]**. Any citric or
   ascorbic dip, or steam blanch, must be a documented QA decision because it
   changes the label.
7. **Output weighing** into trays or totes, and **scrap weighing by cause**.

### 4.2 The mass balance rule

```
raw in  =  prepped out  +  declared scrap  +  unaccounted
```

The prep log refuses to confirm when `unaccounted` exceeds the greater of 1% of
input or 1 kg. This is deliberate friction. The as-is process estimates losses
at week end **[DOC]**; the whole point of the system is to stop an unexplained
2–5% from being normal.

Scrap is recorded **by cause** — peel, core, stone, trim, reject, spillage — and
**by destination** — compost, animal feed, secondary product, waste. The
destination is what makes the ESG "post-harvest loss averted" claim defensible.

### 4.3 Yield standards — and a correction to the v2.4 proposal

The v2.4 document states a fresh-to-dry ratio of **8:1 to 10:1** and applies it
across the product range **[DOC]**. That is approximately right for pineapple
and generous for mango, but it is **substantially wrong for tomato**, and using
one factor for all three will distort costing, capacity planning and the raw
material budget.

Tomato is roughly 94% water. 100 kg of fresh tomato carries about 6 kg of dry
solids; dried to 12% residual moisture that yields about 6.8 kg of product.
After prep losses the real farm-gate ratio is around **15:1**.

| Crop | Prep yield (% of accepted raw) | Drying yield (% of prepped) | Fresh : dried |
|---|---|---|---|
| Pineapple | 55% (crown, shell, core ≈ 45%) | 17% | **≈ 10.7 : 1** |
| Mango | 65% (peel + stone ≈ 35%) | 20% | **≈ 7.7 : 1** |
| Tomato | 95% (calyx + rejects only) | 7.2% | **≈ 14.6 : 1** |

These are **[STD]** baselines calibrated against published moisture contents,
carried in the `aifa.crop` master record, and they are *starting points*. Phase 1
must re-derive them from three real trial batches per crop and per dominant
cultivar. Cultivar matters: Queen Victoria pineapple and Smooth Cayenne differ by
several percentage points, and mango stone share varies widely between Tommy
Atkins and Keitt.

Every production run is scored against these standards, and drift beyond the
tolerance band raises a task rather than disappearing into a month-end variance.

---

## 5. Stage 3 — Dehydration

**Who:** Chamber operator
**System:** Stage-2 manufacturing order + `aifa.dehydration.run`

### 5.1 Sequence

1. **Pre-load check.** Chamber clean (CIP logged), trays clean, ambient RH noted.
2. **Tray loading.** Single layer, no overlap. Record tray count and wet load kg.
   **The chamber's rated wet load is enforced** — overloading is the most common
   cause of under-dried centre trays, and under-dried fruit fails the water
   activity gate downstream **[STD]**.
3. **Drying profile.** 55–65 °C for 12–18 hours is the working band for these
   crops **[STD/DOC]**. Higher temperatures case-harden the surface and trap
   moisture inside — which looks dry and fails the lab test.
4. **In-run monitoring.** Data logger trace, or manual temperature readings.
   Trolley rotation at the mid-point where the chamber has a known cold spot.
5. **Unloading and dry weighing.** This is the number that determines the
   drying yield and therefore the product cost.
6. **WIP lot assignment.** `LOT-DRY-<CROP>-<YYYYMMDD>-<SEQ>` on the tote,
   carrying forward the link to the prep logs and thus to the farm-gate lots.
7. **Energy capture.** kWh consumed per run. Drying is the dominant energy cost
   in dehydration; without per-run capture, product costing is guesswork.

### 5.2 Why the run is a first-class record, not a work-order comment

A drying run is where the margin is made or lost. A percentage point of drying
yield drift is raw fruit that was paid for at the farm gate and never sold. The
run therefore captures four things a clipboard cannot:

1. exact wet in / dry out, per chamber, per load;
2. the profile actually achieved, not the one intended;
3. the release criteria (moisture, water activity);
4. the energy consumed.

---

## 6. Stage 4 — Conditioning and release

**Who:** QA
**System:** `aifa.quality.check` on control points CCP-2 and CCP-3

This stage is **missing from the v2.4 process description** and should not be.
Fruit coming out of a chamber has an uneven moisture distribution across the
load. Equilibrating it in sealed bins for 12–24 hours before testing gives a
representative result; testing straight off the tray gives an optimistic one
**[STD]**.

### Release criteria

| Control point | Limit | Rationale |
|---|---|---|
| **CCP-2** Residual moisture | ≤ 12–15% depending on crop | Mould and yeast growth within shelf life |
| **CCP-3** Water activity | ≤ 0.60, and ≥ 0.35 | Above 0.60, osmophilic yeast and mould can grow. Below 0.35 the product is brittle and off-brand — so this limit has a floor as well as a ceiling **[STD]** |

**Sample at least three points** across the load (top, centre, last trolley).
Fibrous cultivars scatter widely; a single sample is not a result.

**Failing this gate quarantines the load automatically.** Packing cannot draw on
a blocked run. The disposition — re-dry, downgrade, dispose — requires a QA
manager's sign-off and a recorded root cause. "Release under concession" is
possible but is permanently attributed to the person who granted it.

---

## 7. Stage 5 — Packing

**Who:** Packaging line lead
**System:** Stage-3 manufacturing order + `aifa.checkweigh.session`

### 7.1 Sequence

1. **Metal detection / sieving** — **CCP-4**. Test pieces (ferrous, non-ferrous,
   stainless) at start, middle and end of the run **[STD]**.
2. **Pouch filling** to the target fill, which is deliberately a little above the
   declared weight.
3. **Oxygen absorber** insertion.
4. **Nitrogen flush** (bulk foodservice packs, and retail where specified).
5. **Seal** and **seal integrity test** — squeeze plus dye penetration on a
   sample. A leaking seal defeats both the absorber and the barrier foil, so the
   12-month shelf life no longer holds.
6. **Check-weighing** with running statistics.
7. **Labelling** with lot, manufacture date, expiry, and GS1-128 / QR codes;
   scan-verify that the decoded lot matches the production order — **OPRP-04**.
   A wrong lot code destroys traceability for the whole run.
8. **Cartonise** (24 or 48 units) and palletise.

### 7.2 Check-weighing: two different questions

Operators routinely conflate these, and they have different answers:

- **"Is the line giving product away?"** — the *mean* fill against the declared
  weight. Every gram of mean overfill is margin donated to the consumer.
- **"Is any individual pouch short?"** — the *tolerable negative error* rule. For
  a 35 g pack the TNE is 9% (3.15 g); for a 100 g pack it is 4.5 g. A small
  number of packs may fall below nominal by up to 1× TNE; **none** may fall below
  2× TNE **[STD]**.

The system computes mean, standard deviation, giveaway, TNE breaches and Cpk,
and gives a verdict: compliant, adjust the line, or non-compliant.

---

## 8. Stage 6 — Warehouse and dispatch

- **FEFO picking** on finished goods, driven by the expiry date derived from
  the manufacture date plus the product's shelf life.
- **Expiry alerts** at 90 days out, so slow-moving stock can be pushed through
  promotion or foodservice rather than written off.
- **Reorder points** on packaging materials. Running out of 100 g pouches stops
  the line just as effectively as running out of fruit, and has a longer lead time.
- **Cycle counting** rather than an annual wall-to-wall count.

---

## 9. Stage 7 — Distribution

Aifa sells through channels with materially different commercial mechanics, and
treating them the same is what produces a 42-day cash conversion cycle **[DOC]**.

| Channel | Mechanic | System treatment |
|---|---|---|
| Supermarket chains (Friendship, Bambis, Allmart, Lomyad) | **Consignment** — title stays with Aifa until sold | Internal per-customer location; sale and invoice raised on shelf count |
| Cafés and hotels (Tomoca, Hyatt) | Firm order, credit terms | Standard sale order → delivery → invoice |
| E-commerce (ZMall, BEU) | Usually consignment or short-cycle | Consignment with a 7-day count cadence |
| Export | Proforma, FX, phytosanitary documents | Multi-currency sale order |

### 9.1 The consignment loop

```
Place stock on shelf  →  (stock stays on Aifa's balance sheet)
   →  Merchandiser counts shelf: remaining / returned / therefore sold
   →  Sale order + invoice for exactly what sold
   →  Returns processed with a reason (expired, damaged, delisted)
```

Recording consignment as a sale at delivery overstates revenue and understates
inventory; recording it only on paper delays collection by weeks. Modelling it
as an internal transfer into a customer-named location is both the honest
accounting treatment and the one that makes the receivable collectable.

### 9.2 Van route sales

Load the van, plan the stops, capture a signature per delivery, settle the van at
end of day. The settlement matters most: without it, van stock quietly becomes
"shrinkage". A route cannot be closed with stops still marked as planned.

---

## 10. Open questions for Phase 1 discovery

Every one of these is an **[ASSUMED]** above. They are ordered by how much
rework a wrong assumption causes.

| # | Question | Why it matters | Who answers |
|---|---|---|---|
| 1 | What are the real prep and drying yields, per crop **and per cultivar**, from three trial batches each? | Drives costing, capacity planning, raw material budget and every yield variance alert | Plant manager + QA |
| 2 | Is tomato really ~15:1, or does the current practice dry it less far? | If tomato is planned on a 10:1 factor, the raw budget is understated by ~50% for that line | Plant manager |
| 3 | Does a conditioning / equilibration step exist today, or is moisture tested straight off the tray? | Determines whether release results are representative; affects the shelf-life claim | QA |
| 4 | What sanitiser, at what concentration, in the wash tank — and is it monitored? | This is CCP-1. If it is not monitored today, it is the highest-value single change in the project | QA |
| 5 | Is any pretreatment used (citric dip, blanching)? | Affects the additive-free label claim | QA + marketing |
| 6 | Rated wet load and tray count per chamber, and known cold spots | Enforced at run creation; wrong values either block legitimate loads or permit overloading | Maintenance |
| 7 | Which retail partners are genuinely consignment vs firm sale, and on what count cadence? | Determines revenue recognition and the AR ageing profile | Sales + finance |
| 8 | Current crate fleet size and loss rate | Sizes the deposit scheme | Sourcing |
| 9 | Actual pouch fill set points and historical giveaway | Sets the check-weigh targets | Packaging lead |
| 10 | Is there a metal detector on the packing line today? | If not, CCP-4 is a capital item, not a configuration item | Plant manager |
| 11 | Who is authorised to grant a quality concession, and to approve a payout? | Segregation of duties in the security model | Managing director |
| 12 | Counterfactual post-harvest loss rates agreed with CARE / P4G | The impact figure must match what the donor will accept | MD + CARE |

---

## 11. What changes versus today

| Today **[DOC]** | Under the blueprint |
|---|---|
| Handwritten intake logs, transcribed days later | Machine-weighed, priced by the server, synced when there is signal |
| Prep loss estimated weekly in aggregate | Weighed by cause per shift; log will not confirm unless it balances |
| Drying start times on a clipboard | Per-run record with profile, yield, moisture, aw and kWh |
| Batch numbers hand-written on foil | System-generated lot inherited through three manufacturing stages |
| Tracing a pouch to a farm takes 48+ hours | Resolved in under a second, and printable as an audit dossier |
| Paper delivery notes, reconciled weeks later | Shelf count generates the invoice for exactly what sold |
| Month-end spreadsheet consolidation | Nightly KPI snapshot, with the yield gap valued in birr |

---

## 12. Sources

- FAO, *Fruit and vegetable processing* — processing flow-sheets and dried fruit
  chapter: <https://www.fao.org/4/v5030e/v5030e0y.htm>
- FAO, *Dried fruit* technical guidance:
  <https://openknowledge.fao.org/server/api/core/bitstreams/ef8602df-edcd-49e2-8ad7-5bda59589228/content>
- FDA, *HACCP Principles & Application Guidelines*:
  <https://www.fda.gov/food/hazard-analysis-critical-control-point-haccp/haccp-principles-application-guidelines>
- Drying kinetics and chemical properties of mango (moisture targets):
  <https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9388300/>
- Water activity ranges for dried fruit (0.4–0.6 band, texture effects):
  <https://aqualab.com/en/knowledge-base/webinars/natural-ingredients-101-moisture-dried-fruit-nuts>
- Effect of pretreatments and drying methods on quality:
  <https://www.tandfonline.com/doi/pdf/10.1080/23311932.2020.1747961>
- P4G, *Yarashoo Agro Industry – CARE* partnership (scope, tonnage, farmer numbers):
  <https://p4gpartnerships.org/pioneering-green-partnerships/all-p4g-partnerships/yarashoo-agro-industry-care>
- Yarashoo Agro Industry / Aifa Foods:
  <https://yarashoo.co/>
- Odoo 17 FEFO removal strategy documentation:
  <https://www.odoo.com/documentation/17.0/applications/inventory_and_mrp/inventory/shipping_receiving/removal_strategies/fefo.html>
