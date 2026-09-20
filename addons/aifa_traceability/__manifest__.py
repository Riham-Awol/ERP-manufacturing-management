{
    "name": "Aifa Agro ERP - Farm-to-Shelf Traceability",
    "version": "17.0.1.0.0",
    "category": "Manufacturing/Agro-Processing",
    "summary": "Bidirectional lot genealogy, public QR provenance page and one-click recall simulation",
    "description": """
Aifa Agro ERP - Traceability (FRS-4.5, FRS-5.3)
===============================================

* **Genealogy rebuild** - walks Odoo's stock moves backwards and forwards from
  any lot and materialises the ancestor / descendant links, including the
  farm-gate intake lots and the dehydration runs, so the audit dossier and the
  public page can render in milliseconds rather than re-walking the graph.
* **Recall simulation** - pick a suspect intake lot or dehydration run and the
  system lists every finished lot, every customer delivery and every
  consignment shelf it reached, with the quantities. Running this as a drill
  is an EFDA and export-audit expectation, not just a crisis tool.
* **Public provenance page** at ``/trace/<lot>`` - the QR printed on the pouch
  resolves to a consumer-facing page naming the region, the cooperative and the
  drying date. It deliberately exposes provenance and quality release, never
  farmer personal data or commercial terms.
""",
    "author": "Aifa ERP Implementation Team",
    "website": "https://yarashoo.co",
    "license": "LGPL-3",
    "depends": ["aifa_base", "aifa_sourcing", "aifa_processing", "aifa_quality", "web"],
    "data": [
        "security/ir.model.access.csv",
        "views/aifa_trace_views.xml",
        "views/aifa_recall_views.xml",
        "views/aifa_trace_portal_templates.xml",
        "views/aifa_traceability_menus.xml",
    ],
    "installable": True,
    "application": False,
}
