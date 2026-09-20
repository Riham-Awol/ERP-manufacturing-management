#!/usr/bin/env bash
# Install the Aifa suite into an existing Odoo 17 Community deployment.
#
#   ./install.sh <database> [odoo-bin path] [addons path of core odoo]
#
# The script is intentionally boring: it installs the modules in dependency
# order and stops on the first failure, so a broken upgrade does not leave
# half the suite loaded.
set -euo pipefail

DB="${1:?usage: install.sh <database> [odoo-bin] [core-addons-path]}"
ODOO_BIN="${2:-odoo}"
CORE_ADDONS="${3:-/usr/lib/python3/dist-packages/odoo/addons}"
REPO_ADDONS="$(cd "$(dirname "$0")/../addons" && pwd)"

MODULES="aifa_base,aifa_sourcing,aifa_processing,aifa_quality,aifa_traceability,aifa_consignment,aifa_impact"

echo "Installing ${MODULES}"
echo "  database    : ${DB}"
echo "  core addons : ${CORE_ADDONS}"
echo "  aifa addons : ${REPO_ADDONS}"

"${ODOO_BIN}" -d "${DB}" \
    --addons-path="${CORE_ADDONS},${REPO_ADDONS}" \
    -i "${MODULES}" \
    --stop-after-init

echo
echo "Done. To load a worked farm-to-shelf example as well:"
echo "  ${ODOO_BIN} shell -d ${DB} --addons-path=${CORE_ADDONS},${REPO_ADDONS} < $(dirname "$0")/../tools/seed_demo.py"
