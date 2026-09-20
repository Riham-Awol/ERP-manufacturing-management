#!/usr/bin/env bash
#
# Show the actual error behind an "Internal Server Error".
#
#   ./logs.sh          # the last traceback, or the tail if there is none
#   ./logs.sh -f       # follow the log live, then reload the page in the browser
#
# Odoo always logs the full Python traceback for a 500. The browser page never
# shows it, which is why that error looks so opaque.

set -uo pipefail
cd "$(dirname "$0")"

if [ "${1:-}" = "-f" ]; then
    echo "Following the Odoo log. Reload the failing page in your browser now."
    exec docker compose logs -f --tail=20 odoo
fi

LOG="$(docker compose logs --no-color --tail=4000 odoo 2>/dev/null)"
if [ -z "$LOG" ]; then
    echo "No Odoo logs. Is the stack running?  docker compose ps"
    exit 1
fi

LAST="$(printf '%s\n' "$LOG" | grep -n 'Traceback (most recent call last)' | tail -1 | cut -d: -f1)"
if [ -n "$LAST" ]; then
    echo "=== last traceback in the Odoo log ==="
    printf '%s\n' "$LOG" | tail -n "+$((LAST > 3 ? LAST - 3 : 1))"
else
    echo "=== no traceback found; last 60 lines ==="
    printf '%s\n' "$LOG" | tail -60
    echo
    echo "No traceback means the 500 probably is not Odoo itself."
    echo "Check the database container too:  docker compose logs db"
fi
