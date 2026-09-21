# Free Hosting — What I Recommend, and Why

You want this online without paying. That is achievable, but only on platforms
that give you a real machine or container. Below is what it actually needs,
then two free options in detail.

---

## 1. What it needs (measured, not guessed)

Measured on this build — all seven modules, demo data, a full seeded cycle:

| | Memory |
|---|---|
| Odoo, peak during module installation | **176 MB** |
| Odoo, steady state serving pages | **158 MB** |
| PostgreSQL (includes 128 MB shared buffers) | **~380 MB** |
| **Combined peak** | **~560 MB** |

Installation is the heavy phase; day-to-day is lighter. What that means:

| RAM | Verdict |
|---|---|
| 512 MB | **No.** The install will be killed by the OOM reaper part way through, leaving a broken database |
| 1 GB | Works, with a 1–2 GB swap file. Fine for a demo |
| 2 GB+ | Comfortable. No tuning needed |

It also needs a **process that stays running**, a **persistent disk**, and
**PostgreSQL**. That is why static and serverless hosts cannot run it — see
`06-HOSTING-AND-TESTING.md` section 0.

---

## 2. The free options, honestly compared

| Option | Really free? | RAM | URL | Catch |
|---|---|---|---|---|
| **GitHub Codespaces** | Yes — 120 core-hours/month on a personal account, no card | 8 GB | `https://…app.github.dev` | Stops after 30 min idle; URL dies with the codespace |
| **Oracle Cloud Always Free** | Yes — free forever, card for identity check only | 6–24 GB (ARM) | Your own domain | Signup friction; ARM capacity can be unavailable in busy regions |
| Google Cloud e2-micro | Free forever, card needed | 1 GB | Your own domain | US regions only, so latency from Addis is poor |
| Render / Railway / Fly free tiers | Partly | 256–512 MB | Provided | **Below the 560 MB peak — the install dies.** Also sleep on idle, and a cold Odoo start takes minutes |
| Vercel / Netlify / Pages | N/A | — | — | Cannot run Odoo at all |

**My recommendation, in two parts:**

- **To show the client this week → GitHub Codespaces.** Zero infrastructure, no
  credit card, working public URL in about fifteen minutes. The repo already
  carries the configuration.
- **For a link that stays live → Oracle Cloud Always Free.** A real VM, free
  permanently, your own domain with TLS. Set it up once when you are not under
  time pressure.

Do both. Codespaces for the meeting, Oracle for what you leave them with.

---

## 3. Option 1 — GitHub Codespaces (start here)

**What you get:** a public HTTPS URL, an 8 GB machine, nothing to install
locally. **Free allowance:** 120 core-hours/month on a personal account. The
2-core machine this repo requests uses 2 core-hours per wall-clock hour, so
roughly **60 hours a month**. A demo costs about an hour.

### Step 1 — Launch the codespace

1. Open the repository on GitHub.
2. Switch to the `claude/focused-davinci-b8f4ki` branch.
3. **Code ▾** → **Codespaces** tab → **Create codespace on
   claude/focused-davinci-b8f4ki**.

It builds for 2–3 minutes. `.devcontainer/devcontainer.json` in the repo asks
for a 2-core / 8 GB machine with Docker inside, so you do not configure
anything.

### Step 2 — Build the demo

In the codespace terminal:

```bash
cd deploy
./demo-up.sh
```

About ten minutes: starts PostgreSQL and Odoo, creates the database with
Ethiopia so amounts are in birr, installs the seven modules, seeds a complete
farm-to-shelf cycle, runs the smoke test, prints the URL. It stops at the first
failure rather than leaving you half-built.

You are done when you see `14 passed, 0 failed`.

### Step 3 — Make the URL public

By default the forwarded port is private to you, so the client would hit a
GitHub login page.

1. Open the **PORTS** tab, next to TERMINAL.
2. Find port **8069**.
3. Right-click → **Port Visibility** → **Public**.
4. Copy the **Forwarded Address** — `https://<something>-8069.app.github.dev`.

Test it in a private browser window before you send it. If it shows a GitHub
sign-in page, the visibility did not stick — set it again.

### Step 4 — Change the admin password

`admin`/`admin` is fine on a laptop. This URL is on the public internet.

In Odoo: **Settings → Users & Companies → Users → Mitchell Admin** → *Change
password*.

### Step 5 — Demo, then stop it

Follow `docs/04-DEMO-SCRIPT.md`.

When finished, stop the codespace so it does not spend your hours:
github.com/codespaces → **⋯** → **Stop codespace**.

> The codespace suspends itself after 30 minutes idle. Restarting keeps your
> data — the containers and volumes are still there — but **the public URL
> changes**, and port visibility resets to private. Re-do step 3 and send the
> new link. Before a scheduled call, start it 15 minutes early and load a page
> so it is warm.

### Watch your hours

github.com/settings/billing shows the usage. Stop the codespace when you are
not using it; that is the whole trick. Delete it entirely when the demo period
is over.

---

## 4. Option 2 — Oracle Cloud Always Free (the permanent one)

**What you get:** a real VM, free *forever* — not a trial. The Arm Ampere A1
allowance is up to 4 cores and 24 GB RAM, which is more than most paid VPS
plans. Plus 200 GB of storage and a fixed public IP.

**The catch:** signup wants a credit card for identity verification (it is not
charged as long as you stay on Always Free resources), and A1 capacity is
sometimes unavailable in busy regions — you will see *"Out of host capacity"*.
Two ways around that: pick a less crowded region at signup, or take the AMD
`VM.Standard.E2.1.Micro` instead, which is also Always Free at 1 GB RAM and is
enough with a swap file.

The official `odoo:17.0` Docker image publishes both `amd64` and `arm64`
builds, so the repo's compose file runs unchanged on either shape. I verified
this against Docker Hub rather than assuming it.

### Step 1 — Create the account

1. cloud.oracle.com → **Sign up for free**.
2. Choose your **Home Region** carefully — it cannot be changed later. For
   Ethiopia, `eu-frankfurt-1` or `me-jeddah-1` give the best latency; Jeddah is
   usually less contended for A1 capacity.
3. Verify with a card. Confirm the account shows **Always Free Eligible**.

### Step 2 — Create the VM

**Menu → Compute → Instances → Create Instance**

| Field | Value |
|---|---|
| Image | Canonical **Ubuntu 22.04** |
| Shape | **VM.Standard.A1.Flex**, 2 OCPU, 12 GB (stays inside Always Free) |
| Network | Create a new VCN, **assign a public IPv4** |
| SSH keys | Upload your public key, or let Oracle generate one and **download it** |

If it refuses with *"Out of host capacity"*, either retry over the next day or
switch the shape to **VM.Standard.E2.1.Micro** (1 GB) and add swap in step 4.

### Step 3 — Open the firewall

Oracle blocks everything by default, in **two** places. Miss either and the
site is unreachable — this is the single most common Oracle mistake.

**A. The cloud firewall (security list)**

Instance → **Virtual Cloud Network** → **Security Lists** → default list →
**Add Ingress Rules**:

| Source CIDR | Protocol | Destination port |
|---|---|---|
| `0.0.0.0/0` | TCP | `80` |
| `0.0.0.0/0` | TCP | `443` |

**B. The firewall on the VM itself** — step 4 covers it.

### Step 4 — Prepare the VM

SSH in:

```bash
ssh -i /path/to/your_key ubuntu@<public-ip>
```

```bash
# Ubuntu on Oracle ships iptables rules that drop everything but SSH
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80 -j ACCEPT
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 443 -j ACCEPT
sudo netfilter-persistent save

# Swap. Skip on a 12 GB A1; do it on the 1 GB micro shape.
sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile
sudo mkswap /swapfile && sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab

# Docker
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker ubuntu
newgrp docker
```

### Step 5 — Point a domain at it

Caddy needs a hostname to get a certificate. Free options:

- **DuckDNS** — duckdns.org, sign in with GitHub, pick a subdomain, paste your
  public IP. Gives `yourname.duckdns.org` in about a minute.
- Or an `A` record on a domain you already own.

### Step 6 — Deploy

```bash
git clone https://github.com/Riham-Awol/ERP-manufacturing-management.git
cd ERP-manufacturing-management/deploy

# Your hostname in place of the example
sed -i 's/aifa-demo.example.com/yourname.duckdns.org/' Caddyfile

# Change every password before this is exposed
nano docker-compose.yml     # POSTGRES_PASSWORD, PASSWORD
nano odoo.conf              # db_password, admin_passwd
                            # also set:  list_db = False
                            #            proxy_mode = True

./demo-up.sh
docker compose -f docker-compose.yml -f docker-compose.https.yml up -d
```

Caddy fetches a Let's Encrypt certificate on the first request — give it thirty
seconds, then open `https://yourname.duckdns.org`.

### Step 7 — Lock it down

```bash
docker compose exec -T odoo odoo shell -d aifa_demo < ../tools/smoke_test.py
```

- [ ] Admin password changed in the Odoo UI
- [ ] `list_db = False` in `odoo.conf`
- [ ] `proxy_mode = True` in `odoo.conf`
- [ ] All database passwords changed from the defaults
- [ ] Smoke test passes

The stack restarts with the VM (`restart: unless-stopped` is set in the HTTPS
overlay), so a reboot needs no intervention.

---

## 5. Which to choose

**Doing a demo in the next few days, nothing else:** Codespaces. Fifteen
minutes, no card, no DNS, no firewall. Accept that the URL is disposable.

**Leaving the client something to look at:** Oracle. Budget an hour, most of it
waiting on signup. Free permanently, and it is the same setup you would run in
production, so nothing is thrown away.

**Ignore the small free tiers** — Render, Railway, Fly. Their free RAM is below
the measured 560 MB install peak, so the build dies part way and you spend the
evening debugging an OOM instead of preparing the demo.

---

## 6. The Vercel half

Odoo cannot run on Vercel, but the *client-facing* page can, and it is free
there permanently — no sleeping, no hours to watch.

`site/` is a Next.js page carrying the proposal, the corrected yield analysis
and a live traceability lookup. Import the repository at vercel.com with
**Root Directory = `site`** (leave it at `/` and you get the 404 that started
all this, because the repository root is a Python project with no front end).

Set `ODOO_BASE_URL` in the Vercel project settings to point it at your Odoo —
Codespace or Oracle VM — and the lookup switches from bundled sample data to
live. With no backend reachable it degrades to the sample rather than breaking,
so the page is never dead in front of a client.

That gives the split most teams end up with anyway: a fast public page on a CDN,
the stateful ERP on a machine that can hold a database.

---

## 7. Cost if you ever outgrow free

For context, since the proposal quotes 290,000 ETB/year for managed hosting and
support:

| | Monthly |
|---|---|
| Hetzner CX22 (2 vCPU, 4 GB) | ~€4 |
| DigitalOcean / Vultr basic (1 vCPU, 2 GB) | ~$12 |
| Oracle Always Free | **0** |

Infrastructure is not what the SLA line item is for — that is monitoring,
backups, patching and a person answering the phone. Worth being clear about
that when the client asks why hosting costs anything at all.
