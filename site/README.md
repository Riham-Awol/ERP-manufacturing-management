# Aifa ERP — client pitch site

A Next.js site that deploys free to Vercel. It presents the proposal, the
corrected yield analysis and the traceability demo, and it optionally talks to a
live Odoo instance.

**It is not the ERP.** Odoo cannot run on Vercel — see
[`../docs/06-HOSTING-AND-TESTING.md`](../docs/06-HOSTING-AND-TESTING.md) section 0.
This is the front-of-house: the page you send a client, sitting in front of the
real system hosted on a VM or a Codespace.

---

## Deploy to Vercel

### Through the dashboard

1. vercel.com → **Add New… → Project** → import
   `Riham-Awol/ERP-manufacturing-management`.
2. **Root Directory → `site`.** This matters. The repository root is a Python
   Odoo project; if you leave the root at `/`, Vercel finds no front end and the
   deployment 404s.
3. Framework preset: Next.js (detected automatically).
4. Deploy. First build takes about a minute.

### Through the CLI

```bash
npm i -g vercel
cd site
vercel          # preview
vercel --prod   # production
```

---

## Environment variables

Both optional. The site works with neither.

| Variable | Effect |
|---|---|
| `ODOO_BASE_URL` | Base URL of a reachable Odoo instance, e.g. `https://aifa.example.com`. The trace lookup proxies to it and results are labelled *Live from the connected ERP*. Without it, the lookup answers from a bundled sample. |
| `NEXT_PUBLIC_DEMO_URL` | If set, the hero shows an **Open the live system** button pointing at your Odoo login. |

Set them in **Project → Settings → Environment Variables**, then redeploy.

`ODOO_BASE_URL` is read server-side only, so the backend address never reaches
the browser bundle.

---

## How the trace lookup behaves

`app/api/trace/[lot]/route.js` is the only dynamic route. Three paths, all
tested against a live Odoo:

| Situation | Response |
|---|---|
| Backend configured, lot found | `source: "live"` with the real payload |
| Backend configured, lot unknown | HTTP 404, `source: "live"`, a clear message |
| Backend unreachable or not configured | `source: "sample"` and, when a backend *was* configured, a `degraded` reason. The page still renders. |

Two details worth knowing if you change it:

- Odoo's `type="json"` controllers speak **JSON-RPC 2.0**, not REST. The call is
  a POST carrying `{"jsonrpc":"2.0","method":"call","params":{}}` and the answer
  is unwrapped from `result`. A plain GET gets a 404 from Odoo's router.
- The route proxies rather than letting the browser call Odoo directly, because
  Odoo sends no CORS headers by default.

The bundled sample in `lib/sample-trace.js` is not invented — it is the verbatim
payload from a seeded instance after `tools/seed_demo.py` ran a full cycle.

---

## Local development

```bash
cd site
npm install
npm run dev                                     # sample data
ODOO_BASE_URL=http://localhost:8069 npm run dev # against a local Odoo
```

---

## Notes on the chart

`components/YieldChart.jsx` is hand-built inline SVG — no chart library, so
there is nothing to keep patched.

It is a **single series**: one measure (fresh-to-dried ratio) across three
crops, so every bar takes the same blue rather than a colour per crop. Tomato's
outlier status is carried by bar length and its direct label, not by hue. The
blue is validated against both the light and dark surfaces (lightness band,
chroma floor, and ≥3:1 contrast). Hover gives the per-crop breakdown, and
*Show the numbers* opens the table view for anyone who cannot use the chart.

Verified rendered in light, dark and at 380px wide: no label collisions and zero
horizontal overflow.
