# -*- coding: utf-8 -*-
"""Shared vocabulary for the three processing stages.

Keeping the selection in one place means a BOM, a manufacturing order, a prep
log and a yield report all agree on what "Stage 2" means.
"""

PROCESS_STAGES = [
    ("prep", "Stage 1 - Preparation"),
    ("dry", "Stage 2 - Dehydration"),
    ("condition", "Stage 2b - Conditioning"),
    ("pack", "Stage 3 - Packing"),
]

SCRAP_CAUSES = [
    ("peel", "Peel / Skin"),
    ("core", "Core / Crown"),
    ("stone", "Stone / Seed"),
    ("trim", "Trim & Sizing Offcuts"),
    ("reject", "Rejected (decay / bruise)"),
    ("spill", "Spillage & Floor Loss"),
    ("sample", "QA Sampling"),
]
