# Aifa Foods Agro-Processing ERP

Custom Odoo 17 Community add-ons and proposal documentation for **Yarashoo Agro
Industry PLC**, trading as **Aifa Foods** — an Ethiopian producer of
additive-free dried pineapple, mango, tomato and mixed-fruit snacks, sourcing
from 200+ smallholder outgrowers in Gamo, Sidama, Afar and the Rift Valley.

Seven modules turn a stock Odoo Community install into a fruit dehydration plant
system: farm-gate sourcing, three-stage dehydration BOMs with real yield control,
HACCP quality gates that actually block stock, farm-to-shelf traceability, retail
consignment, and donor-grade ESG reporting.

---

## Quick start

```bash
git clone https://github.com/Riham-Awol/ERP-manufacturing-management.git
cd ERP-manufacturing-management/deploy
./demo-up.sh
```

That brings up the stack, creates the database with Ethiopia so amounts are in
birr, installs all seven modules, seeds a complete farm-to-shelf cycle, runs a
smoke test and prints the URL. Add `--fresh` to wipe a previous attempt first.

To show a client on a call, put it on a public HTTPS URL without provisioning
anything: `./share.sh`.

**Hosting it free?** Open the repo in a GitHub Codespace, run
`cd deploy && ./demo-up.sh`, and set port 8069 to Public — a working URL in
about 15 minutes, no card. For a link that stays up, Oracle Cloud's Always Free
tier runs it permanently. Both written out step by step in
[`docs/07-FREE-HOSTING.md`](docs/07-FREE-HOSTING.md).

Getting `Internal Server Error`? Run `./logs.sh` for the real traceback, or
`./demo-up.sh --fresh` to rebuild from scratch. See
[`docs/06-HOSTING-AND-TESTING.md`](docs/06-HOSTING-AND-TESTING.md) section 6.

> **This will not deploy to Vercel, Netlify or any static/serverless host** —
> they give `404 NOT_FOUND` because there is no front end to build. Odoo is a
> long-running Python server with a PostgreSQL database and a filestore on
> disk. It needs a VPS or a container platform. See
> [`docs/06-HOSTING-AND-TESTING.md`](docs/06-HOSTING-AND-TESTING.md) section 0.

<details>
<summary>The same thing step by step</summary>

```bash
cd deploy
docker compose up -d

# Create the database with Ethiopia as the country, so amounts are in ETB.
# Odoo will not let you change the currency once journal entries exist, so
# this has to happen at creation - see docs/06-HOSTING-AND-TESTING.md section 1.
docker compose exec odoo python3 /mnt/aifa-tools/create_db.py aifa_demo

docker compose exec odoo odoo -d aifa_demo \
    -i aifa_base,aifa_sourcing,aifa_processing,aifa_quality,aifa_traceability,aifa_consignment,aifa_impact \
    --stop-after-init

# Recommended: drive one complete farm-to-shelf cycle so the demo carries
# real traced data rather than static fixtures.
docker compose exec -T odoo odoo shell -d aifa_demo < ../tools/seed_demo.py

# Confirm the deployment is healthy (read-only, PASS/FAIL per check).
docker compose exec -T odoo odoo shell -d aifa_demo < ../tools/smoke_test.py
```

</details>

Open <http://localhost:8069> (`admin` / `admin`) and go to **Aifa Agro**.

Installing into an existing Odoo 17 deployment instead:

```bash
./deploy/install.sh <database> [odoo-bin] [core-addons-path]
```

Hosting it for a client demo, with TLS: **[`docs/06-HOSTING-AND-TESTING.md`](docs/06-HOSTING-AND-TESTING.md)**.

---

## Documentation

| Document | What it is for |
|---|---|
| [`docs/01-WORKFLOW-BLUEPRINT.md`](docs/01-WORKFLOW-BLUEPRINT.md) | **Start here.** The proposed farm-to-shelf process, every assumption tagged by source, and twelve questions Phase 1 must answer |
| [`docs/02-PROPOSAL.md`](docs/02-PROPOSAL.md) | Proposal v3.0 — what was built, corrections to v2.4, what is *not* deliverable as specified, plan and commercials |
| [`docs/03-FRS-COVERAGE.md`](docs/03-FRS-COVERAGE.md) | Every v2.4 functional requirement mapped to built / partial / core Odoo / not built |
| [`docs/04-DEMO-SCRIPT.md`](docs/04-DEMO-SCRIPT.md) | A 30-minute demo built around five questions the plant already argues about |
| [`docs/05-MODULE-REFERENCE.md`](docs/05-MODULE-REFERENCE.md) | Models, key fields, REST endpoints, extension points |
| [`docs/06-HOSTING-AND-TESTING.md`](docs/06-HOSTING-AND-TESTING.md) | Running it locally, hosting it with TLS, the smoke test, and troubleshooting |
| [`docs/07-FREE-HOSTING.md`](docs/07-FREE-HOSTING.md) | Hosting it for free: measured requirements, GitHub Codespaces and Oracle Always Free, step by step |

---

## The modules

| Module | FRS | What it does |
|---|---|---|
| `aifa_base` | — | Regions, collection centres, crop/cultivar master with yield and quality standards, nine security personas, lot sequences, product catalogue |
| `aifa_sourcing` | M1 | Outgrower and cooperative registry, dated grade price matrix, offline-capable field purchases with idempotent replay, raw intake lots, payout ledger, crate labels |
| `aifa_processing` | M2, M3 | Three-stage BOM tagging, prep logs with scrap by cause and a mass-balance guard, dehydration runs with profile / moisture / energy, yield variance control |
| `aifa_quality` | M4 | HACCP control points with critical limits, checks that quarantine on failure, NCR with root cause and CAPA, check-weighing SPC, CIP logs, EFDA audit dossier |
| `aifa_traceability` | 4.5, 5.3 | Materialised lot genealogy to the farm gate, recall simulation including consigned stock, public `/trace/<lot>` provenance page |
| `aifa_consignment` | M6 | Per-customer consignment locations, shelf counts that bill exactly what sold, van route trips with settlement |
| `aifa_impact` | M8 | Nightly plant KPI snapshots with the yield gap valued in birr, P4G/CARE impact reporting from dated cited assumptions |

Dependency order is `base → sourcing → processing → quality → traceability`, with
`consignment` and `impact` on top. Install them together; `install.sh` does.

---

## Three things worth knowing before you read the code

**Yield factors are per crop, not global.** The v2.4 proposal used one 8:1–10:1
fresh-to-dry ratio. Pineapple is ≈10.7:1 and mango ≈7.7:1, so that holds; tomato
is ≈14.6:1 because it is 94% water. Planning a tomato line on the pineapple
factor understates the raw budget for that line by about half. The factors live
in `aifa.crop` and are meant to be recalibrated from real trial batches in
Phase 1 — it is master data, not code.

**Odoo's Quality app is Enterprise-only.** `aifa_quality` is the Community
equivalent, built around Aifa's own HACCP plan. Failing a blocking control point
quarantines the lot and nothing downstream can consume it.

**A recall must find consigned stock.** Stock on a supermarket shelf under
consignment sits in an *internal* Odoo location, so a trace that filters on
customer-usage destinations reports a clean recall while the product is still on
sale. `aifa_traceability` walks the consignment location tree as well.

---

## Requirements

- Odoo **17.0 Community** (LGPLv3)
- PostgreSQL 13+ (16 used in testing)
- Python 3.10+
- Core Odoo modules: `mrp`, `stock`, `purchase`, `sale_management`, `account`,
  `product_expiry`, `mail`

All seven modules are LGPLv3, matching Odoo Community. No licence fees, ever.

---

## Verification

Every module was installed on a clean Odoo 17.0 Community database with demo
data, and `tools/seed_demo.py` drove a complete cycle: field purchase → gate QA →
farm-gate lots → prep → dehydration → release testing → packing → check-weighing
→ genealogy → consignment → shelf count → invoice → recall drill → KPI snapshots
→ impact report. The public provenance page and both PDF reports were rendered
against the resulting data.

```
Stage 1 prep: 878.4 kg raw -> 483.1 kg prepped (55.00% against a 55.00% standard)
Stage 2 dry:  480.0 kg wet -> 81.6 kg dried at 17.0% yield, 4.510 kWh/kg
Genealogy:    2 farm-gate lots, 1 drying run, 2 outgrowers across Gamo / Arba Minch
Mock recall:  2 lots, 1 customer destination, traced in under a second
Impact:       3,209 kg sourced, 1,135 kg loss averted, 60% women outgrowers
```

---

## Status

This is a **demo and proposal build**, not a production deployment. It is
deliberately honest about its edges — see `docs/02-PROPOSAL.md` §6 for what is
not built, what is not deliverable as specified in v2.4, and why. The offline
mobile client, the MoR fiscal device integration and full Amharic coverage are
each discussed there rather than implied to exist.
