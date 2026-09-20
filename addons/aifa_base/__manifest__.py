{
    "name": "Aifa Agro ERP - Base",
    "version": "17.0.1.0.0",
    "category": "Manufacturing/Agro-Processing",
    "summary": "Shared master data, security roles and menus for the Aifa Foods agro-processing suite",
    "description": """
Aifa Agro ERP - Base
====================

Foundation module for the Aifa Foods / Yarashoo Agro Industry ERP suite on
Odoo Community Edition.

Provides:

* Sourcing region / collection-centre geography master data
* Crop (commodity) and cultivar master data carrying the reference
  fresh-to-dry conversion factors used by the processing modules
* The nine operational security personas described in the FRS
  (Field Sourcing Agent, Receiving Inspector, Processing Operator,
  Packaging Lead, QA/QC Manager, Warehouse Custodian, Route Sales,
  Finance, Executive)
* The shared "Aifa Agro" root menu and lot-numbering sequences
""",
    "author": "Aifa ERP Implementation Team",
    "website": "https://yarashoo.co",
    "license": "LGPL-3",
    "depends": ["base", "mail", "product", "stock", "uom", "product_expiry"],
    "data": [
        "security/aifa_security.xml",
        "security/ir.model.access.csv",
        "data/ir_sequence_data.xml",
        "data/uom_data.xml",
        "views/aifa_menus.xml",
        "views/aifa_region_views.xml",
        "views/aifa_crop_views.xml",
    ],
    "demo": ["demo/aifa_base_demo.xml"],
    "application": True,
    "installable": True,
    "auto_install": False,
    "images": ["static/description/banner.png"],
}
