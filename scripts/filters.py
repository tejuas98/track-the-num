#!/usr/bin/env python3
"""Canonical Category / Sector filter definitions for the Seva challenge analytics API.

Single source of truth, shared by:
  - scripts/fetch_snapshot.py (bakes the filter matrix for the static site)
  - server.py                 (computes any combination on demand for the live site)

Why variants: the source database stores some sectors under two spellings
(e.g. "Women & Child" = 28 applications and "Women and Child" = 22 applications are
different rows). The UI should offer one option per sector, so each canonical sector
carries every value that must be fetched and summed.
"""

ALL = "All categories"
ALL_SECTORS = "All sectors"

# (label shown in the dashboard, [values sent as ?category=...])
CATEGORIES = [
    (ALL, []),
    ("Women Category", ["Women Category"]),
    ("Age below 18", ["Age below 18"]),
    ("Age below 21", ["Age below 21"]),
    ("General Category", ["General Category"]),
]

# (label shown in the dashboard, [values sent as ?sector=...])
SECTORS = [
    (ALL_SECTORS, []),
    ("Agriculture", ["Agriculture"]),
    ("Law and Order", ["Law and Order", "Law & Order"]),
    ("Women and Child", ["Women & Child", "Women and Child"]),
    ("Urban Development", ["Urban Development"]),
    ("Health and Medical", ["Health and Medical", "Health & Medical"]),
    ("Defence", ["Defence"]),
    ("Education and Employability", ["Education and Employability"]),
    ("Emerging Technologies - AI, Blockchain and Others", ["Emerging Technologies - AI, Blockchain and Others"]),
    ("Infrastructure and Mobility", ["Infrastructure and Mobility", "Infrastructure & Mobility"]),
    ("Sustainability - Energy, Climate and Others", ["Sustainability - Energy, Climate and Others"]),
    ("Other", ["Other"]),
]

CATEGORY_LABELS = [c for c, _ in CATEGORIES]
SECTOR_LABELS = [s for s, _ in SECTORS]

C_BY_LABEL = dict(CATEGORIES)
S_BY_LABEL = dict(SECTORS)


def combo_key(category_label, sector_label):
    return f"{category_label}||{sector_label}"


def resolve(category_label=None, sector_label=None):
    """Labels -> list of (category_value|None, sector_value|None) pairs to fetch."""
    cvals = C_BY_LABEL.get(category_label, [])
    svals = S_BY_LABEL.get(sector_label, [])
    cats = cvals or [None]
    secs = svals or [None]
    return [(c, s) for c in cats for s in secs]


def variants_for(category_label=None, sector_label=None):
    """Labels -> the raw upstream values (for building query params)."""
    return resolve(category_label, sector_label)


if __name__ == "__main__":       # quick self-check
    print("categories:", CATEGORY_LABELS)
    print("sectors   :", SECTOR_LABELS)
    print("General Category + Health and Medical ->", resolve("General Category", "Health and Medical"))
    print("All + Women and Child ->", resolve(ALL, "Women and Child"))
