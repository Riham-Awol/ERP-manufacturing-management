# Demo Runbook — 30 minutes with Aifa Foods

A demo that opens screens will bore them. A demo that answers the questions the
plant manager and the QA manager already argue about will not. This script is
built around five such questions.

---

## Before you start

```bash
# 1. Start the stack
cd deploy && docker compose up -d && docker compose logs -f odoo   # wait for "HTTP service running"

# 2. Create the database with Ethiopia as the country, so every figure on
#    screen is in birr. This cannot be fixed later.
docker compose exec odoo python3 /mnt/aifa-tools/create_db.py aifa_demo

# 3. Install the Aifa modules
docker compose exec odoo odoo -d aifa_demo \
    -i aifa_base,aifa_sourcing,aifa_processing,aifa_quality,aifa_traceability,aifa_consignment,aifa_impact \
    --stop-after-init

# 4. Drive one complete farm-to-shelf cycle so the demo has real traced data
docker compose exec -T odoo odoo shell -d aifa_demo < ../tools/seed_demo.py

# 5. Confirm it is healthy before you present
docker compose exec -T odoo odoo shell -d aifa_demo < ../tools/smoke_test.py
```

Then open <http://localhost:8069>, log in as `admin` / `admin`, and go to
**Aifa Agro**.

Full hosting instructions, including putting this on a URL the client can open:
[`06-HOSTING-AND-TESTING.md`](06-HOSTING-AND-TESTING.md).

Open these tabs in advance so you are not navigating while talking:

1. Aifa Agro → Sourcing → Raw Intake Batches
2. Aifa Agro → Processing → Dehydration Runs
3. Aifa Agro → Quality → Failed Checks
4. Aifa Agro → Traceability → Lot Genealogy
5. Aifa Agro → Distribution → Consignment Placements
6. `http://localhost:8069/trace/` in a separate browser (ideally a phone)

---

## Act 1 — "Where did this fruit come from?" (5 min)

**Sourcing → Raw Intake Batches.** Open a pineapple batch.

Talk to:
- One farmer, one crop, one weighing, **one lot number**:
  `LOT-RAW-PINE-GMA-202609-00009`. The region and month are in the number, so
  even a photocopied crate label carries meaning.
- Gross, crate tare, net, accepted, rejected — each one its own field. *"Today
  the difference between what you weighed and what you kept is a memory. Here
  it is a number, per farmer, per week."*
- **Print Crate Label** → QR and GS1-128, ready for the Zebra printer.

**Sourcing → Field Purchases.** Open the demo one.

- Note the **Synced Offline** ribbon and the Sync Metadata tab: device ID, GPS,
  sync timestamp. *"This was captured at Arba Minch with no network and replayed
  when the truck reached signal. Replay it twice and you still get one purchase."*
- The agent never typed a price. Configuration → Farm Gate Prices resolved it.

---

## Act 2 — "Why did we only get 48 kg?" (8 min)

This is the question the plant manager cannot answer today.

**Processing → Prep Logs.** Open the pineapple log.

- Raw in, prepped out, scrap by cause: peel, core, trim, reject. Each with a
  destination.
- Actual yield against the standard, with a variance flag.
- Try to confirm a log that does not balance — it refuses. *"That refusal is the
  product. Today an unexplained 2–5% is normal. Here it cannot be saved."*

**Processing → Dehydration Runs.** Open the released pineapple run.

- Wet in 480 kg → dry out 81.6 kg → 17.0% against a 17.0% standard.
- Duration, average and peak temperature, ambient RH.
- **4.51 kWh per kg of dried fruit.** *"That is your biggest controllable cost
  and it has never had a number before."*
- Try creating a run above the chamber's rated load — it refuses, and explains
  why: overloading is what produces under-dried centre trays.

**Configuration → Master Data → Crops.** Open Tomato.

> This is the moment to raise the correction. *"Your proposal used one 8:1 to
> 10:1 ratio across the range. Pineapple is about 10.7:1 and mango about 7.7:1,
> so that holds. But tomato is 94% water — it is closer to 15:1. If you budget a
> tomato line on the pineapple factor you will under-buy fruit by about half.
> These are per crop and per cultivar here, and Phase 1 will replace our
> baselines with your own trial batches."*

---

## Act 3 — "What happens when a batch fails?" (7 min)

**Quality → Failed Checks.** Open the mango water activity failure.

- Measured 0.68 against a 0.60 limit. Measured 17.4% moisture against 15%.
- Now open the linked dehydration run: **state is Quarantine, QA Blocked**. Try
  to release it to packing — refused, with the numbers in the message.
- Open the NCR. Root cause: chamber at 100% of rated load on a 61% RH night.
  Preventive action: cap the load at 85% when ambient RH exceeds 55%.
- *"The NCR will not close without a root cause, and a critical one will not
  close without a preventive action. That is the difference between a quality
  system and a quality folder."*

**Quality → Check-Weighing.** Open the 35 g mango session.

- Mean, standard deviation, giveaway, packs below 1× and 2× TNE, Cpk, verdict.
- *"Two different questions. Are you giving product away — that is the mean. Is
  any individual pouch short — that is the TNE rule. Operators conflate them and
  the answers are different."*

---

## Act 4 — "Trace this pouch back to the farm." (5 min)

The headline. Do it live and time it.

**Traceability → Lot Genealogy.** Open the finished goods lot
`LOT-FG-PINE100-...`, tab **Farm-to-Shelf Genealogy**.

- Two farm-gate intake lots, named outgrowers, cooperative, region, intake dates.
- The drying run with its profile and release results.
- **Print Audit Dossier** → one PDF with every check, the farm-gate origin, the
  drying records and a signature block for the inspector. *"48 hours becomes
  one button."*

**Traceability → Recalls & Drills.** Open the mock recall, press **Run Trace**.

- Affected lots, customer destinations, and the trace duration in seconds.
- *"Note that it found the consignment stock on the Friendship shelf. That stock
  is still yours and it is still on sale. A recall that only looks at delivery
  notes misses it."*

**Now hand them a phone.** Open `http://<host>:8069/trace/LOT-FG-PINE100-...`

- Region, cooperative, number of outgrowers, share of women, harvest date, the
  drying record, the quality checks passed.
- No farmer name, no phone number, no price. *"Provenance, not personal data."*
- *"This is what the QR on the pouch does. It is a marketing asset and an audit
  artefact at the same time."*

---

## Act 5 — "Where is my cash?" (5 min)

The strongest item in the business case.

**Distribution → Consignment Placements.** Open the Friendship placement.

- 120 placed, 64 sold, balance on shelf, value on shelf, next count due.
- *"That stock is on your balance sheet, not theirs, because you still own it.
  Today it is on a paper delivery note and you invoice weeks later."*

**Distribution → Shelf Counts.** Open the count.

- Expected, counted, returned with a reason, therefore sold. The order and
  invoice were generated for exactly the 64 that sold.
- *"42 days to 18 days. On your numbers that is about 650,000 birr of working
  capital, which is more than the whole project."*

**Reporting → Daily Plant KPIs.** Graph view.

- Output trend, and the **yield gap valued in birr**.
- *"Your proposal projected a 2.5% yield improvement worth about 350,000 birr.
  This measures it. Which also means it can disprove it — and you should track
  it from day one."*

**Reporting → ESG Impact Reports.** Open and press Compute.

- Sourced kg, loss averted kg, outgrowers, share of women, scrap valorised.
- Open the "How the figure was derived" box. *"Every donor auditor asks 'against
  what baseline?'. The counterfactual rate is per crop, dated and cited, and it
  lives in configuration — not hard-coded in a slide."*

---

## Closing

Three sentences, then stop:

1. Everything you just saw runs on Odoo Community — **zero licence fees, ever**,
   and the source is yours.
2. Nothing here was typed in for the demo; it was produced by one scripted run of
   the real workflow.
3. The one thing we still need from you is week 1: walk us through the line, and
   let us weigh three trial batches per crop so the yield standards are yours
   rather than ours.

---

## Questions you should expect

**"Our yields are not those numbers."** Good — that is the point of Phase 1.
Open Configuration → Crops and change one in front of them. Show that every
variance alert follows immediately. It is master data, not code.

**"Can operators bypass this?"** Show the security groups. Only a QA manager can
release a quarantine, and a concession is permanently attributed to a name. Then
be honest: someone can always write the wrong number on a form. The system makes
the wrong number visible and attributable, which is a different thing from making
it impossible.

**"What if the internet goes down?"** Two answers. Rural sourcing is offline-first
with an idempotent replay — show the sync metadata tab. The plant floor runs on
the edge appliance and syncs upstream when connectivity returns.

**"How long to make a change?"** Depends on the change. Yield standards, prices,
control-point limits, shelf-life and count cadence are all master data — minutes.
A new stage in the process is development. Be specific about which is which
rather than saying "flexible".

**"What about the MoR fiscal integration?"** Answer it straight: we cannot
certify a device integration without the certified vendor's device and the
current MoR specification. We build the VAT, withholding and TOT calculation and
an export-ready payload, run the dual-track approach at go-live, and scope the
digital sync as a follow-on. Do not let go-live depend on it.
