# Start Here — hosting this and showing it to a client

There are **two things** to put online, and they go to different places because
they are different kinds of software.

| | What it is | Where it goes | Cost |
|---|---|---|---|
| **The pitch page** (`site/`) | A Next.js page: the proposal, the yield finding, a traceability lookup | **Vercel** | Free, permanent |
| **The ERP** (`addons/`) | Odoo — a long-running Python server with a database | **Codespace or a VM** | Free |

You do not need both. Pick by what the meeting needs:

- **Sending a link ahead of a meeting** → the pitch page alone is enough.
- **Demoing the working system** → the ERP.
- **Both** → deploy the pitch page, put the ERP on a Codespace, and connect them.

---

## A. The pitch page on Vercel (10 minutes, permanent)

This is the one that stays up forever for free.

1. Go to **vercel.com** → **Add New… → Project**.
2. Import `Riham-Awol/ERP-manufacturing-management`.
3. **Set Root Directory to `site`.** ← the important step. The repository root
   is a Python project; leave the root at `/` and Vercel finds nothing to build
   and serves `404 NOT_FOUND`.
4. Framework preset is detected as Next.js. Click **Deploy**.

You get `https://<project>.vercel.app`. The traceability lookup works
immediately using a bundled sample — the real payload from a seeded run — so
the page is never dead, even with no ERP running.

Optional, under **Settings → Environment Variables**:

| Variable | Effect |
|---|---|
| `ODOO_BASE_URL` | Point at a reachable Odoo. Lookups go live and are labelled as such. |
| `NEXT_PUBLIC_DEMO_URL` | Adds an "Open the live system" button to the hero. |

Redeploy after adding them.

---

## B. The ERP on a Codespace (20 minutes, free, best for a demo call)

No credit card, no server to provision. Free allowance is 120 core-hours a
month; the machine this repo asks for uses 2 per hour, so about 60 hours.

1. On GitHub, switch to branch **`claude/focused-davinci-b8f4ki`**.
2. **Code ▾ → Codespaces → Create codespace on
   claude/focused-davinci-b8f4ki**. Wait 2–3 minutes.
3. In the terminal:
   ```bash
   cd deploy
   ./demo-up.sh
   ```
   About ten minutes. It creates the database with Ethiopia so figures are in
   birr, installs the seven modules, seeds a complete farm-to-shelf cycle and
   runs a smoke test. **You are ready when you see `14 passed, 0 failed`.**
4. Open the **PORTS** tab → port **8069** → right-click → **Port Visibility →
   Public**.
5. Copy the **Forwarded Address** (`https://…-8069.app.github.dev`).
6. **Change the admin password**: Settings → Users & Companies → Users →
   Administrator. `admin`/`admin` must not survive on a public URL.

Test the link in a private browser window before sending it. A GitHub sign-in
page means step 4 did not stick — set it again.

> The codespace suspends after 30 minutes idle. Restarting keeps your data but
> **changes the URL and resets the port to private**. Before a call, start it 15
> minutes early, load a page, and re-check step 4.

### Connecting the two

Put the codespace address into `ODOO_BASE_URL` on Vercel and redeploy. The
pitch page's lookup switches from sample to live. When the codespace stops, the
page falls back to the sample instead of breaking.

---

## C. A permanent ERP URL — Oracle Always Free

When you want something the client can return to weeks later, rather than a
disposable codespace link. A real VM, free forever, your own domain with TLS.
Budget an hour, most of it waiting on signup.

Full steps: [`07-FREE-HOSTING.md`](07-FREE-HOSTING.md) section 4.

---

## Demo day

**The night before**

- [ ] `./demo-up.sh` has been run and smoke test shows `14 passed, 0 failed`
- [ ] Admin password changed
- [ ] The public URL opens in a private browser window
- [ ] You have read [`04-DEMO-SCRIPT.md`](04-DEMO-SCRIPT.md)

**Fifteen minutes before**

- [ ] Codespace started and warm (load a page — a cold start is slow)
- [ ] Port 8069 visibility is still **Public**
- [ ] These tabs open: Raw Intake Batches · Dehydration Runs · Failed Checks ·
      Lot Genealogy · Consignment Placements · `/trace/` on your phone

**If it breaks**

```bash
cd deploy
./logs.sh              # the real traceback behind any 500
./demo-up.sh --fresh   # rebuild from scratch, ~10 minutes
```

Worst case, the Vercel pitch page still works on its bundled sample and carries
the whole argument on its own.

---

## The 30 minutes

[`04-DEMO-SCRIPT.md`](04-DEMO-SCRIPT.md) is built around five questions the
plant already argues about:

1. *Where did this fruit come from?* — the farm-gate lot
2. *Why did we only get 48 kg?* — the mass-balance guard, and the tomato ratio
3. *What happens when a batch fails?* — quarantine that actually blocks stock
4. *Trace this pouch back to the farm* — under a second, then hand them a phone
5. *Where is my cash?* — consignment sell-through, 42 days to 18

Close on: zero licence fees, nothing on screen was typed in for the demo, and
the one thing you need from them is a week to walk the line.

---

## Honest status

Verified by running it: the seven modules install on a clean Odoo 17 Community
database, the seeded cycle completes, the smoke test passes 14/14, the
traceability API answers live, and the pitch page builds and renders in light,
dark and on a phone.

Not verified by running it: `demo-up.sh` against a real Docker daemon, and the
Codespaces and Oracle steps — this environment has no Docker daemon and no
cloud accounts. The script's control flow was exercised against a stubbed
Docker (fresh install, existing database, `--fresh`, bad flag, and an install
failure aborting correctly), and every Odoo command inside it was run natively.
If something fails, `./logs.sh` gives you the actual error.
