{
    "name": "Aifa Agro ERP - Quality & Food Safety",
    "version": "17.0.1.0.0",
    "category": "Manufacturing/Agro-Processing",
    "summary": "HACCP control points, quarantine workflow, non-conformance reports, check-weighing SPC and EFDA audit dossiers",
    "description": """
Aifa Agro ERP - Quality & Food Safety (FRS-M4)
==============================================

Odoo's Quality app is an Enterprise-only module, so this add-on provides the
food-safety control layer that a Community deployment needs, shaped around
Aifa's actual HACCP plan rather than a generic inspection engine:

* **Control point definitions** - one record per CCP / OPRP with its limits,
  measurement method, frequency and the stage it gates.
* **Quality checks** with numeric, boolean and option results, automatically
  scored against the control point's limits. A failing check on a *blocking*
  control point moves the lot into quarantine; nothing downstream can consume it.
* **Quarantine and disposition** - re-dry, downgrade, rework or dispose, each
  requiring the QA manager's sign-off and leaving an immutable trail.
* **Non-conformance reports** with root cause, corrective and preventive action.
* **Check-weighing** with running mean, standard deviation and the
  average-content rule applied to 35 g and 100 g pouches (FRS-3.5).
* **Sanitation (CIP) logs** with supervisor sign-off (FRS-4.4).
* **EFDA / export audit dossier** - a single PDF per batch compiling every
  check result, the drying profile and the farm-gate origin (FRS-4.6).
""",
    "author": "Aifa ERP Implementation Team",
    "website": "https://yarashoo.co",
    "license": "LGPL-3",
    "depends": ["aifa_base", "aifa_sourcing", "aifa_processing"],
    "data": [
        "security/ir.model.access.csv",
        "data/aifa_control_point_data.xml",
        "views/aifa_control_point_views.xml",
        "views/aifa_quality_check_views.xml",
        "views/aifa_ncr_views.xml",
        "views/aifa_checkweigh_views.xml",
        "views/aifa_sanitation_views.xml",
        "views/aifa_quality_menus.xml",
        "report/aifa_audit_dossier.xml",
    ],
    "demo": ["demo/aifa_quality_demo.xml"],
    "installable": True,
    "application": False,
}
