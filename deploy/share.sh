#!/usr/bin/env bash
#
# Put the local demo on a public HTTPS URL for a client call, without
# provisioning a server.
#
#   ./share.sh
#
# Starts a Cloudflare quick tunnel to the Odoo container and prints a
# https://<random>.trycloudflare.com address. No Cloudflare account needed.
#
# Good for: a scheduled demo call, a link someone opens once.
# Not good for: leaving up. The URL changes every run, the tunnel dies when
# you close this terminal, and your laptop has to stay awake. For anything
# the client will come back to, use a VPS - see docs/06-HOSTING-AND-TESTING.md
# section 4.
#
# Odoo must be told it is behind a proxy or its redirects point back at
# localhost. This script checks that for you.

set -euo pipefail
cd "$(dirname "$0")"

say()  { printf '\n\033[1m==> %s\033[0m\n' "$*"; }
fail() { printf '\n\033[31mFAILED: %s\033[0m\n' "$*" >&2; exit 1; }

docker compose ps --status running 2>/dev/null | grep -q odoo \
    || fail "the demo is not running. Start it first:  ./demo-up.sh"

if ! grep -qE '^\s*proxy_mode\s*=\s*True' odoo.conf; then
    say "Enabling proxy_mode in odoo.conf (required behind a tunnel)"
    printf '\n; Set automatically by share.sh - Odoo must know it is behind a\n; proxy or every redirect points back at localhost.\nproxy_mode = True\n' >> odoo.conf
    docker compose restart odoo
    sleep 8
fi

if ! command -v cloudflared >/dev/null 2>&1; then
    cat <<'MSG'

cloudflared is not installed. Install it, then re-run this script:

  macOS          brew install cloudflared
  Debian/Ubuntu  curl -L --output /tmp/cf.deb \
                   https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb \
                   && sudo dpkg -i /tmp/cf.deb
  Windows        winget install --id Cloudflare.cloudflared

Or use ngrok instead:  ngrok http 8069

MSG
    exit 1
fi

cat <<'BANNER'

  ------------------------------------------------------------------
   Starting a public tunnel to http://localhost:8069

   Watch for the https://....trycloudflare.com line below - that is
   the address to send the client.

   Before you share it:
     - change the admin password (Settings > Users > Administrator).
       admin/admin is fine on a laptop, not on a public URL.
     - keep this terminal open; closing it kills the tunnel.

   Ctrl-C to stop.
  ------------------------------------------------------------------

BANNER

exec cloudflared tunnel --url http://localhost:8069
