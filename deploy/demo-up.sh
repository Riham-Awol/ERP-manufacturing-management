#!/usr/bin/env bash
#
# Bring up a client-ready Aifa demo in one command.
#
#   ./demo-up.sh            # build on whatever is already there
#   ./demo-up.sh --fresh    # destroy the volumes first and start clean
#
# Runs: compose up -> wait for Postgres and Odoo -> create the database with
# Ethiopia (so amounts are in birr) -> install the seven modules -> seed one
# complete farm-to-shelf cycle -> smoke test.
#
# Stops on the first failure rather than leaving you with a half-built demo.

set -euo pipefail

cd "$(dirname "$0")"

DB="${AIFA_DB:-aifa_demo}"
COMPOSE=(docker compose)
FRESH=0

for arg in "$@"; do
    case "$arg" in
        --fresh) FRESH=1 ;;
        -h|--help) sed -n '2,12p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) echo "unknown option: $arg" >&2; exit 2 ;;
    esac
done

say()  { printf '\n\033[1m==> %s\033[0m\n' "$*"; }
fail() { printf '\n\033[31mFAILED: %s\033[0m\n' "$*" >&2; exit 1; }

command -v docker >/dev/null 2>&1 || fail "docker is not installed or not on PATH"
"${COMPOSE[@]}" version >/dev/null 2>&1 || fail "the docker compose plugin is not available"

if [ "$FRESH" = "1" ]; then
    say "Destroying existing containers and volumes"
    "${COMPOSE[@]}" down -v || true
fi

say "Starting Postgres and Odoo"
"${COMPOSE[@]}" up -d

say "Waiting for Postgres"
for _ in $(seq 1 60); do
    if "${COMPOSE[@]}" exec -T db pg_isready -U odoo >/dev/null 2>&1; then
        echo "  Postgres is accepting connections"
        break
    fi
    sleep 2
done
"${COMPOSE[@]}" exec -T db pg_isready -U odoo >/dev/null 2>&1 \
    || fail "Postgres never came up. Check: docker compose logs db"

say "Waiting for Odoo to answer on 8069"
PROBE="import urllib.request as u; print(u.urlopen('http://localhost:8069/web/login', timeout=3).status)"
for _ in $(seq 1 60); do
    if code=$("${COMPOSE[@]}" exec -T odoo python3 -c "$PROBE" 2>/dev/null) && [ -n "$code" ]; then
        echo "  Odoo responded ($code)"
        break
    fi
    sleep 2
done

EXISTS="import sys, odoo; from odoo.tools import config; config.parse_config([]); \
print('yes' if odoo.service.db.exp_db_exist(sys.argv[1]) else 'no')"
db_state=$("${COMPOSE[@]}" exec -T odoo python3 -c "$EXISTS" "$DB" 2>/dev/null | tr -d '\r' | tail -1)

case "$db_state" in
    yes)
        say "Database '$DB' already exists - skipping creation"
        ;;
    no|"")
        say "Creating database '$DB' with Ethiopia as the country (currency ETB)"
        "${COMPOSE[@]}" exec -T odoo python3 /mnt/aifa-tools/create_db.py "$DB" \
            || fail "database creation failed. Full error: docker compose logs odoo"
        ;;
    *)
        fail "could not tell whether '$DB' exists (got: $db_state)"
        ;;
esac

say "Installing the seven Aifa modules (this takes a few minutes)"
"${COMPOSE[@]}" exec -T odoo odoo -d "$DB" \
    -i aifa_base,aifa_sourcing,aifa_processing,aifa_quality,aifa_traceability,aifa_consignment,aifa_impact \
    --stop-after-init \
    || fail "module installation failed. Full error: docker compose logs odoo"

say "Seeding one complete farm-to-shelf cycle"
"${COMPOSE[@]}" exec -T odoo odoo shell -d "$DB" < ../tools/seed_demo.py \
    || fail "seed run failed"

say "Running the smoke test"
"${COMPOSE[@]}" exec -T odoo odoo shell -d "$DB" < ../tools/smoke_test.py

say "Restarting Odoo so it picks up the new database cleanly"
"${COMPOSE[@]}" restart odoo
sleep 8

cat <<BANNER

  ------------------------------------------------------------------
   Demo is up.

     URL       http://localhost:8069
     login     admin
     password  admin
     database  $DB

   Public provenance page (the QR on the pouch):
     http://localhost:8069/trace/

   Walk-through script: docs/04-DEMO-SCRIPT.md
  ------------------------------------------------------------------

BANNER
