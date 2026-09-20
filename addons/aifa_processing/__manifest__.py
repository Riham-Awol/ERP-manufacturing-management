{
    "name": "Aifa Agro ERP - Dehydration Processing",
    "version": "17.0.1.0.0",
    "category": "Manufacturing/Agro-Processing",
    "summary": "Three-stage dehydration BOMs, prep scrap logging, dehydrator batch cycling and yield variance control",
    "description": """
Aifa Agro ERP - Dehydration Processing (FRS-M2, FRS-M3)
=======================================================

Turns Odoo's generic MRP into a dehydration shop floor:

* **Stage tagging on BOMs and manufacturing orders** - Prep (wash/peel/slice),
  Dry (dehydration) and Pack (pouching) so the three-level product chain
  raw -> prepped WIP -> dried bulk -> finished pouch is explicit and reportable.
* **Prep logs** capturing scrap by cause (peel, core, stone, trim, reject) and
  computing the real prep yield against the crop standard.
* **Dehydration runs** as first-class records: chamber, tray load, temperature
  profile, wet-in / dry-out weights, residual moisture, water activity,
  kWh consumed and the operator who ran it.
* **Yield variance control** - every run is scored against the crop's standard
  and anything outside the tolerance band raises an activity on the plant
  manager instead of quietly disappearing into a month-end spreadsheet.
* **Energy cost allocation** per run so activity-based costing per kg of dried
  fruit is available without a separate costing exercise.
""",
    "author": "Aifa ERP Implementation Team",
    "website": "https://yarashoo.co",
    "license": "LGPL-3",
    "depends": ["aifa_base", "aifa_sourcing", "mrp"],
    "data": [
        "security/ir.model.access.csv",
        "data/aifa_processing_data.xml",
        "views/aifa_dehydrator_views.xml",
        "views/aifa_dehydration_run_views.xml",
        "views/aifa_prep_log_views.xml",
        "views/mrp_bom_views.xml",
        "views/mrp_production_views.xml",
        "views/aifa_processing_menus.xml",
    ],
    "demo": ["demo/aifa_processing_demo.xml"],
    "installable": True,
    "application": False,
}
