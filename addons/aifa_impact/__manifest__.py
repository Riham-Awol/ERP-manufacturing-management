{
    "name": "Aifa Agro ERP - Executive KPIs & ESG Impact",
    "version": "17.0.1.0.0",
    "category": "Reporting/Agro-Processing",
    "summary": "Plant KPI dashboard plus P4G / CARE post-harvest-loss and livelihood impact reporting",
    "description": """
Aifa Agro ERP - Executive Analytics & ESG Impact (FRS-M8)
=========================================================

* **Daily plant KPI snapshot** - one record per day per crop holding intake kg,
  prepped kg, dried kg, realised yield against standard, energy per kg, chamber
  utilisation and quality first-pass rate. Computed by a scheduled job so the
  executive dashboard never runs an expensive query at open time.
* **Post-harvest loss averted** - the headline P4G / CARE metric, derived from
  real accepted intake weights rather than estimated, with the counterfactual
  loss rate configurable per crop and region so the claim is defensible under
  donor audit.
* **Livelihood and gender analytics** - cumulative payouts disbursed, number of
  active outgrowers, share of women among outgrowers and among the workforce,
  and average income per participating household.

Every figure traces back to a transactional record; nothing here is typed in by
hand, which is precisely what a donor verification visit tests.
""",
    "author": "Aifa ERP Implementation Team",
    "website": "https://yarashoo.co",
    "license": "LGPL-3",
    "depends": ["aifa_base", "aifa_sourcing", "aifa_processing", "aifa_quality"],
    "data": [
        "security/ir.model.access.csv",
        "data/aifa_impact_cron.xml",
        "views/aifa_kpi_views.xml",
        "views/aifa_impact_views.xml",
        "views/aifa_impact_menus.xml",
    ],
    "demo": ["demo/aifa_impact_demo.xml"],
    "installable": True,
    "application": False,
}
