#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Create an Odoo database with Ethiopia as the country, so the currency is ETB.

Odoo derives the company currency from the country chosen at database creation
and then refuses to change it once any journal entry exists. Demo data creates
journal entries immediately, so picking the country afterwards is not an option
- the database has to be recreated. This script gets it right the first time.

Usage::

    # native - run it from your Odoo checkout so the odoo package is importable
    cd ~/odoo17 && python3 <repo>/tools/create_db.py aifa_demo \
        --addons-path=$HOME/odoo17/addons,<repo>/addons

    # docker (tools/ is mounted at /mnt/aifa-tools)
    docker compose exec odoo python3 /mnt/aifa-tools/create_db.py aifa_demo

    # docker, without the mount
    docker compose exec -T odoo python3 - aifa_demo < tools/create_db.py

Anything after the database name is handed straight to Odoo's own option
parser, so --addons-path, --data-dir, --db_host and friends all work. Inside
the official Docker image none of them are needed: the entrypoint has already
written /etc/odoo/odoo.conf.

The equivalent in the web UI is the database manager at
/web/database/manager with Country set to Ethiopia.
"""

import os
import sys

USAGE = "usage: create_db.py <database> [odoo options...]"


def _import_odoo():
    """Import Odoo whether or not this script sits inside the Odoo checkout.

    Python puts the *script's* directory on sys.path, not the working
    directory, so running this from an Odoo source tree still would not find
    the package. Try the plain import first (installed Odoo, as in the Docker
    image), then the working directory (a source checkout you cd'd into).
    """
    try:
        import odoo
        return odoo
    except ImportError:
        pass
    sys.path.insert(0, os.getcwd())
    try:
        import odoo
        return odoo
    except ImportError:
        print(
            "Could not import odoo.\n"
            "  - running from source? cd into your Odoo checkout first, e.g.\n"
            "      cd ~/odoo17 && python3 <repo>/tools/create_db.py <db> ...\n"
            "  - or set PYTHONPATH=/path/to/odoo",
            file=sys.stderr,
        )
        raise SystemExit(2)

DEFAULTS = {
    "demo": True,
    "lang": "en_US",
    "password": "admin",
    "login": "admin",
    "country_code": "et",
}


def main(argv):
    if len(argv) < 2 or argv[1].startswith("-"):
        print(USAGE, file=sys.stderr)
        return 2

    db_name = argv[1]

    odoo = _import_odoo()
    from odoo.tools import config

    config.parse_config(argv[2:])

    if odoo.service.db.exp_db_exist(db_name):
        print("Database %r already exists. Drop it first, or pick another name."
              % db_name, file=sys.stderr)
        return 1

    print("Creating %r with country_code=%s (demo data: %s)..."
          % (db_name, DEFAULTS["country_code"], DEFAULTS["demo"]))
    odoo.service.db.exp_create_database(
        db_name,
        DEFAULTS["demo"],
        DEFAULTS["lang"],
        DEFAULTS["password"],
        login=DEFAULTS["login"],
        country_code=DEFAULTS["country_code"],
    )

    env = odoo.api.Environment(
        odoo.registry(db_name).cursor(), odoo.SUPERUSER_ID, {}
    )
    company = env.company
    print("Created %r  country=%s  currency=%s"
          % (db_name, company.country_id.name or "-", company.currency_id.name))
    if company.currency_id.name != "ETB":
        print("WARNING: currency is %s, not ETB. Odoo cannot change this later; "
              "drop the database and retry." % company.currency_id.name,
              file=sys.stderr)
    env.cr.close()

    print("\nNext: install the modules, then seed a worked cycle.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
