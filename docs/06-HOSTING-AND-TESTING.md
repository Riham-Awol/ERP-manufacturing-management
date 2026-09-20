# Hosting and Testing

Three ways to run this, depending on what you need it for.

| You want to… | Use | Time |
|---|---|---|
| Try it on your laptop | **Option A — Docker** | ~10 min |
| Develop or debug the modules | **Option B — native** | ~30 min |
| Show the client from a URL | **Option C — VPS + TLS** | ~45 min |

Whichever you pick, **read §1 first**. Getting the currency wrong at database
creation is the one mistake that is genuinely annoying to undo.

---

## 1. Create the database with Ethiopia as the country

Odoo derives the company currency from the country chosen when the database is
created, and then **refuses to change it once any journal entry exists**. Demo
accounting data creates journal entries immediately, so by the time you notice
the prices are in dollars it is too late — you have to start over.

Create the database with Ethiopia and you get ETB everywhere:

`tools/create_db.py` does exactly this and reports back what it got:

```bash
# Docker - tools/ is mounted at /mnt/aifa-tools by the compose file
docker compose exec odoo python3 /mnt/aifa-tools/create_db.py aifa_demo

# native - run it from your Odoo checkout so the odoo package is importable
cd ~/odoo17
python3 ~/aifa/tools/create_db.py aifa_demo \
    --addons-path=$HOME/odoo17/addons,$HOME/aifa/addons
```

```
Creating 'aifa_demo' with country_code=et (demo data: True)...
Created 'aifa_demo'  country=Ethiopia  currency=ETB
```

Equivalently, use the web database manager at
`http://<host>:8069/web/database/manager` and pick **Ethiopia** in the Country
field.

> Do not try `odoo shell -d postgres` for this. `postgres` is not an Odoo
> database, so the shell fails building an environment against it before your
> script runs.

> If you skip this, everything still works — the amounts just display in USD.
> The smoke test in §5 will tell you which you have.

---

## 2. Option A — Docker on your laptop

Needs Docker Desktop or Docker Engine with the Compose plugin.

**One command**, if you just want a demo that works:

```bash
git clone https://github.com/Riham-Awol/ERP-manufacturing-management.git
cd ERP-manufacturing-management/deploy
./demo-up.sh            # add --fresh to wipe any previous attempt first
```

It starts the stack, waits for Postgres and Odoo, creates the database with
Ethiopia so amounts are in birr, installs the seven modules, seeds a complete
farm-to-shelf cycle, runs the smoke test, and prints the URL and credentials.
It stops at the first failure rather than leaving you with a half-built demo.

If a previous attempt left things in a strange state, `./demo-up.sh --fresh`
is almost always faster than debugging it.

The rest of this section is the same thing done by hand.

```bash
docker compose up -d

# wait for "HTTP service (werkzeug) running"
docker compose logs -f odoo
```

Create the database with Ethiopia as the country (§1), then install the modules:

```bash
docker compose exec odoo python3 /mnt/aifa-tools/create_db.py aifa_demo

docker compose exec odoo odoo -d aifa_demo \
    -i aifa_base,aifa_sourcing,aifa_processing,aifa_quality,aifa_traceability,aifa_consignment,aifa_impact \
    --stop-after-init
```

`--stop-after-init` does not bind the HTTP port, so this does not clash with the
server already running in the same container.

Load a complete worked cycle so the demo carries real traced data:

```bash
docker compose exec -T odoo odoo shell -d aifa_demo < ../tools/seed_demo.py
```

Open <http://localhost:8069>, log in as `admin` / `admin`, go to **Aifa Agro**.

To stop: `docker compose down`. To wipe everything including the data volumes:
`docker compose down -v`.

---

## 3. Option B — native install, no Docker

This is the path used to verify the build, so it is the one with no surprises.

**Requirements:** Python 3.10+, PostgreSQL 13+ (16 used in testing), git.

```bash
# PostgreSQL
sudo apt install -y postgresql
sudo service postgresql start
sudo -u postgres createuser -s "$USER"        # superuser role for your shell user

# Odoo 17 source
git clone --depth 1 --branch 17.0 https://github.com/odoo/odoo.git ~/odoo17
pip install -r ~/odoo17/requirements.txt
```

If `requirements.txt` fails to build a few optional packages (`ebaysdk`,
`ofxparse`, `python-ldap`, `vobject`, `rjsmin`, `docopt`), install the core set
individually — none of the failing ones are needed here:

```bash
pip install --only-binary :all: babel decorator docutils gevent passlib Pillow \
    polib psutil pydot PyPDF2==2.12.1 pyserial pytz qrcode reportlab werkzeug \
    xlrd XlsxWriter num2words freezegun lxml lxml_html_clean greenlet chardet \
    python-stdnum libsass rjsmin psycopg2-binary pyopenssl zeep
```

`PyPDF2` must be pinned to 2.x — Odoo 17 calls APIs that PyPDF2 3.0 removed, and
a core demo module fails to load otherwise.

Then:

```bash
git clone https://github.com/Riham-Awol/ERP-manufacturing-management.git ~/aifa

cd ~/odoo17
python3 ~/aifa/tools/create_db.py aifa_demo \
    --addons-path=$HOME/odoo17/addons,$HOME/aifa/addons

./odoo-bin -d aifa_demo \
    --addons-path=$HOME/odoo17/addons,$HOME/aifa/addons \
    -i aifa_base,aifa_sourcing,aifa_processing,aifa_quality,aifa_traceability,aifa_consignment,aifa_impact \
    --stop-after-init

./odoo-bin shell -d aifa_demo \
    --addons-path=$HOME/odoo17/addons,$HOME/aifa/addons < ~/aifa/tools/seed_demo.py

./odoo-bin -d aifa_demo --addons-path=$HOME/odoo17/addons,$HOME/aifa/addons
```

Or use the helper: `~/aifa/deploy/install.sh aifa_demo ~/odoo17/odoo-bin ~/odoo17/addons`

---

## 4. Option C — host it for the client

A demo the client can open from their own office is worth far more than a laptop
screen share.

**Server:** any small VPS — 2 vCPU, 4 GB RAM, 40 GB disk is comfortable for a
demo. Ubuntu 22.04 or 24.04.

```bash
# on the server
curl -fsSL https://get.docker.com | sh
git clone https://github.com/Riham-Awol/ERP-manufacturing-management.git
cd ERP-manufacturing-management/deploy
```

**Before you bring it up**, do all four of these:

1. Change `POSTGRES_PASSWORD` in `docker-compose.yml` and the matching
   `db_password` and `PASSWORD` values.
2. Change `admin_passwd` in `odoo.conf` — that is the master password that can
   create and drop databases.
3. Set `list_db = False` and `proxy_mode = True` in `odoo.conf`.
4. Put your hostname in `Caddyfile` and point an A record at the server.

Then:

```bash
docker compose -f docker-compose.yml -f docker-compose.https.yml up -d
```

Caddy obtains and renews a Let's Encrypt certificate automatically. Create the
database and install the modules exactly as in Option A, using
`docker compose exec`.

**Two things the overlay handles that are easy to miss:**

- Odoo's live updates ride a websocket. The Caddyfile routes `/websocket`
  explicitly, so when you later move to multi-worker Odoo you only have to point
  that one route at the gevent port (8072).
- The database manager is blocked at the proxy. It can drop databases, and it
  should never be reachable from the internet.

**Change the admin password** on the hosted instance. `admin`/`admin` is fine on
a laptop and not fine on a public URL.

---

## 5. Testing

### Automated smoke test

Run this after any install, any upgrade, and before any client demo:

```bash
# Docker
docker compose exec -T odoo odoo shell -d aifa_demo < ../tools/smoke_test.py

# native
./odoo-bin shell -d aifa_demo --addons-path=<core>,<repo>/addons < ~/aifa/tools/smoke_test.py
```

It is read-only and prints a PASS/FAIL line per check:

```
  PASS   All seven modules installed             7/7
  PASS   Nine security personas present          9/9
  PASS   Crop master populated                   3 crop(s)
  PASS   Tomato ratio is crop-specific (>12:1)   14.6 : 1
  PASS   HACCP control points loaded             9 point(s), 7 blocking
  PASS   Every CCP blocks release                4 CCP(s)
  PASS   Company currency is ETB
  PASS   Genealogy resolves to the farm gate     1 lot(s) with resolved origin
  PASS   Recall trace reaches distribution       2 line(s) across 1 recall(s)
  PASS   Quarantine gate is holding stock        1 run(s) blocked from packing
  14 passed, 0 failed, 0 skipped
```

Checks that need seeded data report `SKIP` on a fresh install rather than
failing. A partial install is detected and fails loudly.

### End-to-end functional test

`tools/seed_demo.py` is the functional test. It asserts at every stage — a
manufacturing order that does not reach `done`, or a component with no stock,
raises rather than silently producing an empty demo. Expected output:

```
Stage 1 prep: 878.4 kg raw -> 483.1 kg prepped (55.00% against a 55.00% standard)
Stage 2 dry:  480.0 kg wet -> 81.6 kg dried at 17.0% yield, 4.510 kWh/kg
Genealogy:    2 farm-gate lots, 1 drying run, 2 outgrowers across Gamo / Arba Minch
Mock recall:  2 lots, 1 customer destination, traced in under a second
Impact:       3,209 kg sourced, 1,135 kg loss averted, 60% women outgrowers
```

It commits, so run it against a demo database, not one holding real data.

### Manual checks worth doing yourself

The things most likely to be wrong on a new host are the ones that touch
rendering and routing rather than the ORM:

| Check | How |
|---|---|
| Public QR page | Open `/trace/<lot>` for a finished lot — should show region, cooperative, drying record, checks passed, **no farmer names** |
| Unknown lot | Open `/trace/NONSENSE` — should show a friendly "could not find" page, not a 404 or a traceback |
| Audit dossier PDF | Lot Genealogy → open a finished lot → **Print Audit Dossier** |
| Crate label PDF | Raw Intake Batches → open one → **Print Crate Label** — QR and GS1-128 must both render |
| Quarantine actually blocks | Processing → Dehydration Runs → open the quarantined mango run → try **Release to Packing** — it must refuse and quote both measurements |
| Mass balance guard | Prep Logs → new log → put output and scrap that do not add up → **Confirm** must refuse |

PDF rendering needs `wkhtmltopdf`. The official Odoo Docker image ships it. On a
native install, `sudo apt install wkhtmltopdf` — without it the reports render as
HTML instead of PDF.

### Upgrading after a code change

```bash
docker compose exec odoo odoo -d aifa_demo -u aifa_quality --stop-after-init
docker compose restart odoo
```

Use `-u <module>` for one module, or `-u all` after changing anything in
`aifa_base`. Re-run the smoke test afterwards.

---

## 6. "Internal Server Error" at http://localhost:8069/

This is Werkzeug's generic 500 page. It never shows the reason — but Odoo
always logs the full traceback.

**First, read the actual error:**

```bash
cd deploy
./logs.sh          # prints the last traceback
./logs.sh -f       # follow live, then reload the page in the browser
```

Then work down this list. They are ordered by how often each one is the cause.

| # | Cause | How to confirm | Fix |
|---|---|---|---|
| 1 | **No database yet, or the wrong one is being picked.** Odoo auto-selects when it finds exactly one database, and a half-installed one then blows up with no hint of which it tried | `docker compose exec db psql -U odoo -l` | Create it properly: `docker compose exec odoo python3 /mnt/aifa-tools/create_db.py aifa_demo`. `odoo.conf` now pins `db_name`/`dbfilter` to `aifa_demo`, so `/` goes straight to the right login page |
| 2 | **Module install failed part way**, leaving a broken registry | `./logs.sh` shows a `ParseError` or `KeyError` from a module load | Easiest is to start clean: `./demo-up.sh --fresh` |
| 3 | **Postgres is not reachable** — container unhealthy, or native service not started | `docker compose ps` shows `db` unhealthy, or `./logs.sh` shows `OperationalError` / `Connection to the database failed` | `docker compose up -d db`, or `sudo service postgresql start` on a native install |
| 4 | **Odoo is still starting.** A large install takes minutes and the port answers before the registry is ready | `docker compose logs odoo` has not yet printed `HTTP service (werkzeug) running` | Wait, then reload |
| 5 | **Assets cannot compile** (native installs only) | Traceback mentions `sass`, `libsass` or `rjsmin` | `pip install libsass rjsmin` and restart |
| 6 | **Stale browser session** pointing at a database that no longer exists | The error persists on `/web` but `/web/login?db=aifa_demo` works | Clear cookies for `localhost:8069`, or use a private window |

**The fastest route back to a working demo**, if you do not need to know why:

```bash
cd deploy
./demo-up.sh --fresh
```

That destroys the containers and volumes and rebuilds everything from scratch.
Roughly ten minutes, and it ends with a smoke test telling you it is healthy.

---

## 7. Troubleshooting

These are the failures actually hit while building this, with what they mean.

| Symptom | Cause | Fix |
|---|---|---|
| `PyPDF2.errors.DeprecationError: isEncrypted is deprecated` during install | PyPDF2 3.x with Odoo 17 | `pip install "PyPDF2==2.12.1"` |
| `ImportError: lxml.html.clean module is now a separate project` | lxml 5.x split | `pip install lxml_html_clean` |
| `External ID not found in the system: aifa_base.crop_pineapple` | Modules installed without demo data, but something references it | Install with demo data, or don't use the demo-dependent records |
| Everything installs but menus are empty | Your user is not in an Aifa group | Settings → Users → give yourself **Executive / Plant Manager** |
| Prices show `$` instead of `Br` | Database created without Ethiopia | See §1 — it cannot be changed after journal entries exist |
| Reports open as HTML, not PDF | `wkhtmltopdf` missing | Install it, restart Odoo |
| `Address already in use` on port 8069 | Something else is on that port | `docker compose down`, or change the published port |
| Websocket errors in the browser console behind a proxy | `proxy_mode` not set | Set `proxy_mode = True` in `odoo.conf` and restart |
| Seed script raises `Manufacturing order … did not complete` | Stock missing for a component, or an MO stalled | Read the assertion — it names the product, lot and location |
| `KeyError: 'res.users'` from `odoo shell -d postgres` | `postgres` is not an Odoo database | Use `tools/create_db.py`, not `odoo shell`, to create databases |
| `ModuleNotFoundError: No module named 'odoo'` running `create_db.py` | The script's own directory is on `sys.path`, not your Odoo checkout | `cd` into the Odoo source tree first, or set `PYTHONPATH=/path/to/odoo` |

---

## 8. Before this goes anywhere near production

The demo stack is a demo stack. It is deliberately convenient and deliberately
not hardened. Minimum list before real data touches it:

- [ ] Every password changed — Postgres, Odoo master, admin user
- [ ] `list_db = False`, database manager unreachable
- [ ] TLS in front, HTTP redirected
- [ ] `workers` set above 0 and sized to the server, with the websocket route
      pointed at the gevent port
- [ ] Automated off-site backups — the FRS asks for 4-hourly incrementals,
      RPO ≤ 2 h and RTO ≤ 4 h, and none of that is configured here
- [ ] Odoo MFA enabled for the finance and executive roles
- [ ] A restore actually tested, not just a backup taken

Sections 6.2 and 6.4 of the proposal set out the non-functional requirements
these map to.
