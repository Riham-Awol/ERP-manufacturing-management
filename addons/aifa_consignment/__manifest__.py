{
    "name": "Aifa Agro ERP - Consignment & Route Sales",
    "version": "17.0.1.0.0",
    "category": "Sales/Agro-Processing",
    "summary": "Supermarket consignment register, sell-through billing and mobile van route sales",
    "description": """
Aifa Agro ERP - Consignment & Route Distribution (FRS-M6)
=========================================================

Addresses the single largest working-capital drag in the as-is process: stock
sitting on a supermarket shelf that Aifa still owns, reconciled on paper weeks
later.

* **Consignment placements** - stock transferred to a retail partner stays on
  Aifa's balance sheet in a per-customer consignment location until it is sold.
  Each placement carries the lot, so shelf stock is still traceable and still
  subject to FEFO and expiry alerts.
* **Shelf counts** - a van driver or merchandiser records sold / returned /
  remaining in one screen; the system reconciles it against what was placed and
  raises the variance rather than absorbing it.
* **Sell-through billing** - confirming a count generates the sales order and
  invoice for exactly the units sold, which is what turns a 42-day cash
  conversion cycle into an 18-day one.
* **Van route trips** - plan a day's stops, load the van from finished goods,
  capture deliveries, returns and cash, and settle the van stock at the end of
  the day so nothing is written off to "shrinkage".
""",
    "author": "Aifa ERP Implementation Team",
    "website": "https://yarashoo.co",
    "license": "LGPL-3",
    "depends": ["aifa_base", "aifa_quality", "sale_management", "stock", "account"],
    "data": [
        "security/ir.model.access.csv",
        "data/aifa_consignment_data.xml",
        "views/aifa_consignment_views.xml",
        "views/aifa_route_views.xml",
        "views/res_partner_views.xml",
        "views/aifa_consignment_menus.xml",
    ],
    "demo": ["demo/aifa_consignment_demo.xml"],
    "installable": True,
    "application": False,
}
