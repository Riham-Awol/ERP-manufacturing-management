{
    "name": "Aifa Agro ERP - Outgrower Sourcing",
    "version": "17.0.1.0.0",
    "category": "Manufacturing/Agro-Processing",
    "summary": "Outgrower registry, offline field purchasing, raw intake lot serialisation and farmer payouts",
    "description": """
Aifa Agro ERP - Outgrower Sourcing (FRS-M1)
===========================================

Covers the farm-gate half of the value chain:

* Outgrower and cooperative registry with plot GPS, acreage and harvest windows
* Grade price matrix (A / B / C) per crop, with effective dates
* Field Purchase Orders that can be captured offline on a rural tablet and
  replayed through a JSON endpoint when connectivity returns
* Raw intake batches with gross / tare / net weighing, Brix and decay index,
  automatic lot serialisation (LOT-RAW-PINE-GMA-202609-00001) and creation of
  the matching Odoo receipt and stock lot
* Farmer payout ledger with advance and crate-deposit deductions, ready for
  Telebirr / CBE Birr bulk payment export
""",
    "author": "Aifa ERP Implementation Team",
    "website": "https://yarashoo.co",
    "license": "LGPL-3",
    "depends": ["aifa_base", "purchase", "stock"],
    "data": [
        "security/ir.model.access.csv",
        "data/aifa_sourcing_data.xml",
        "views/aifa_farmer_views.xml",
        "views/aifa_field_purchase_views.xml",
        "views/aifa_intake_batch_views.xml",
        "views/aifa_payout_views.xml",
        "views/aifa_sourcing_menus.xml",
        "report/aifa_intake_label.xml",
    ],
    "demo": ["demo/aifa_sourcing_demo.xml"],
    "installable": True,
    "application": False,
}
