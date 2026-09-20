# FRS Coverage Matrix

Every functional requirement in the v2.4 proposal, mapped to what exists in the
demo build.

**Legend**
- ✅ **Built** — implemented and exercised by the end-to-end seed run
- 🟡 **Partial** — core implemented, a named piece outstanding
- 🔵 **Core Odoo** — delivered by standard Odoo Community, configuration only
- ⬜ **Not built** — deferred, with the reason stated

---

## FRS-M1 · Outgrower Management & Rural Sourcing

| Req | Requirement | Status | Where |
|---|---|---|---|
| 1.1 | Farmer profile & plot registration | ✅ | `aifa.farmer`, `aifa.farmer.plot` — GPS, acreage, cultivar, soil, irrigation, harvest window |
| 1.2 | Offline field purchase order | 🟡 | Server side built and idempotent: `POST /aifa/api/v1/sourcing/field-purchase`. Mobile client is a separate build |
| 1.3 | Bluetooth scale ingestion | 🟡 | `scale_serial` + `scale_verified` on the line; API accepts machine-weighed readings. Device pairing is in the mobile client build |
| 1.4 | Harvest quality grading gate | ✅ | `field_grade` / `gate_grade` with automatic re-pricing on re-grade and a logged reason |
| 1.5 | Raw intake lot serialisation | ✅ | `LOT-RAW-PINE-GMA-202609-00042`, system-generated, never typed |
| 1.6 | Farmer payout & micro-payment ledger | ✅ | `aifa.farmer.payout` with advance and crate deductions, CSV wallet export |
| 1.7 | Transport & dispatch manifest | ✅ | Truck plate, driver, transit tare on `aifa.field.purchase` |
| 1.8 | Harvest volume predictive analytics | ⬜ | Deferred: needs one full season of plot-level actuals. `expected_yield_kg` per plot captures the input data now |

## FRS-M2 · Recipe Management & Multi-Stage BOM

| Req | Requirement | Status | Where |
|---|---|---|---|
| 2.1 | Multi-tier BOM | ✅ | `aifa_stage` on `mrp.bom`: prep → dry → pack, each producing real stock and a real lot |
| 2.2 | Dynamic shrinkage & moisture ratios | ✅ | Per-crop and per-cultivar standards on `aifa.crop`; every run scored against them |
| 2.3 | Packaging BOM | ✅ | Pouch, oxygen absorber, label, master carton on the Stage-3 BOMs |
| 2.4 | Mixed medley recipe engine | ✅ | `bom_pack_medley_100` — 40/40/20 by dried weight, each component keeping its own lot |
| 2.5 | BOM versioning & engineering change | ✅ | `aifa_version`, `aifa_change_note`, approval by QA manager |

## FRS-M3 · Production & Shop-Floor Execution

| Req | Requirement | Status | Where |
|---|---|---|---|
| 3.1 | Work order generation & dispatch | 🔵 | Standard Odoo MRP, with stage-filtered actions per stage |
| 3.2 | Prep scrap & waste tracking | ✅ | `aifa.prep.log` + `aifa.prep.scrap` by cause and destination, with a mass-balance guard |
| 3.3 | Dehydration chamber batch cycling | ✅ | `aifa.dehydration.run` — chamber, trays, profile, duration, operator; capacity enforced |
| 3.4 | Intermediate WIP lot serialisation | ✅ | `LOT-DRY-<CROP>-<YYYYMMDD>-<SEQ>` on unload |
| 3.5 | Packaging check-weighing | ✅ | `aifa.checkweigh.session` — mean, sd, giveaway, TNE breaches, Cpk, verdict |
| 3.6 | Energy & utility cost allocation | ✅ | kWh and tariff per run; kWh/kg dried computed and rolled into the KPI snapshot |

## FRS-M4 · Quality Assurance & Food Safety

| Req | Requirement | Status | Where |
|---|---|---|---|
| 4.1 | Raw intake QA inspection gate | ✅ | Decay index, Brix, pulp temperature, foreign matter; control points `QA-01`, `OPRP-01` |
| 4.2 | Post-drying moisture & water activity gate | ✅ | `CCP-2` and `CCP-3`; failure blocks packing release automatically |
| 4.3 | Non-conformance & quarantine workflow | ✅ | `aifa.ncr` — not closable without root cause and disposition; critical NCRs need a preventive action |
| 4.4 | Batch sanitisation & clean-room log | ✅ | `aifa.sanitation.log` with ATP swab and two-person sign-off |
| 4.5 | Rapid bidirectional traceability | ✅ | Materialised genealogy; public QR page; recall drill traced in under a second |
| 4.6 | EFDA / export audit report generator | ✅ | Per-lot dossier: checks, farm-gate origin, drying records, declaration block |

## FRS-M5 · Warehouse, Inventory & Lot Traceability

| Req | Requirement | Status | Where |
|---|---|---|---|
| 5.1 | Multi-warehouse virtual mapping | 🔵 | Odoo locations; consignment and van-sales location trees added by `aifa_consignment` |
| 5.2 | Automated FEFO picking | 🔵 | Odoo `product_expiry` FEFO removal strategy; shelf life set per product |
| 5.3 | Barcode & QR scanning | ✅ | GS1-128 and QR on the crate label; QR resolves to the public provenance page |
| 5.4 | Reorder level & safety stock | 🔵 | Odoo reordering rules on packaging materials |
| 5.5 | Cycle counting & reconciliation | 🔵 | Odoo physical inventory; consignment shelf counts add the off-site equivalent |

## FRS-M6 · B2B Sales, Distribution & Consignment

| Req | Requirement | Status | Where |
|---|---|---|---|
| 6.1 | Customer master & multi-tier pricing | 🔵 | Odoo pricelists, plus `aifa_channel` on the partner for channel reporting |
| 6.2 | Supermarket consignment register | ✅ | `aifa.consignment` — per-customer internal location, stock stays on the balance sheet until counted |
| 6.3 | Mobile route van sales & delivery | ✅ | `aifa.route.trip` / `aifa.route.stop` with signature capture and end-of-day settlement |
| 6.4 | Return & damage processing | ✅ | Returns with mandatory reason on the shelf count line |
| 6.5 | Export order & packing list | 🔵 | Odoo multi-currency sales; `aifa_channel = export` for reporting |

## FRS-M7 · Financial Accounting & Statutory Compliance

| Req | Requirement | Status | Where |
|---|---|---|---|
| 7.1 | Ethiopian chart of accounts & GL | 🔵 | Odoo accounting; chart configured in Phase 2 |
| 7.2 | AR & ageing analysis | 🔵 | Odoo; consignment billing is what makes the ageing meaningful |
| 7.3 | MoR e-invoicing integration | ⬜ | Not deliverable without the certified device and current MoR specification. Dual-track approach — see proposal §6.2 |
| 7.4 | Standard vs actual production costing | 🟡 | Yield gap valued per day in `aifa.daily.kpi`; full standard-cost variance accounting is Phase 2 configuration |
| 7.5 | Fixed asset depreciation | 🔵 | Odoo assets module |

## FRS-M8 · Executive Analytics & ESG Impact

| Req | Requirement | Status | Where |
|---|---|---|---|
| 8.1 | Executive KPI dashboard | ✅ | `aifa.daily.kpi` — nightly snapshot, graph/pivot views, yield gap valued in birr |
| 8.2 | Post-harvest loss impact dashboard | ✅ | `aifa.impact.report`, with dated and cited per-crop counterfactual assumptions |
| 8.3 | Gender & farmer livelihood analytics | ✅ | Gender-disaggregated outgrower counts, payouts, cooperative engagement |

---

## Non-functional requirements

| NFR | Requirement | Status | Note |
|---|---|---|---|
| 6.1 | Transaction latency < 1.2 s | 🟡 | KPI snapshots are materialised nightly and the genealogy is cached specifically so dashboards and traces do not run expensive queries at open time. Measure under load in Phase 4 |
| 6.1 | 50 concurrent users | 🔵 | Odoo with PostgreSQL 16 handles this comfortably at the stated volumes. Size the instance in Phase 2 |
| 6.2 | MFA, TLS 1.3, AES-256 at rest | 🔵 | Odoo MFA; TLS and encryption at rest are hosting configuration |
| 6.2 | Immutable audit logging | 🔵 | Odoo's mail.thread tracking on every Aifa model with a state machine; field-level before/after captured |
| 6.3 | Amharic + English UI | 🟡 | Custom module strings are all translatable; core Odoo Amharic coverage is partial — see proposal §6.2 |
| 6.3 | Touch-optimised shop-floor UI | 🟡 | Standard Odoo responsive web works on a tablet. A dedicated large-target kiosk view for the chamber operator is a worthwhile Phase 3 addition |
| 6.4 | 99.8% uptime | 🟡 | Against the hosted service. Plant-side power and connectivity are mitigated by the edge appliance, not by the SLA — see proposal §6.2 |
| 6.4 | 4-hourly backups, RPO ≤ 2 h, RTO ≤ 4 h | 🔵 | Hosting configuration |

---

## Summary

| Status | Count |
|---|---|
| ✅ Built and exercised | 26 |
| 🟡 Partial, with the gap named | 8 |
| 🔵 Core Odoo configuration | 14 |
| ⬜ Not built, with the reason stated | 2 |
