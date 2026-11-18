"""Institutional merit-aid policy, sourced from each college's own Common Data Set.

WHAT CHANGED AND WHY (2026-11-17)
---------------------------------
This module used to assert that 26 institutions award no merit aid, on the basis of
"published institutional policy" compiled by hand and never checked line by line.
Checking all 26 against their own current CDS section H2A disproved five of them:

    Harvard     CDS 2025-26   H2A line n =  4 /  20      avg $4,728 / $5,279
    Stanford    CDS 2025-26   H2A line n =  3 /  14      avg $11,890 / $13,813
    Wellesley   CDS 2025-26   H2A line n =  4 /   5 / 0  avg $55,716
    Middlebury  CDS 2024-25   H2A line n =  3 /   8 / 0  avg $2,700 / $3,850
    Amherst     CDS 2024-25   H2A line n =  0 /   6 / 0  avg $14,801

Each of those was being labelled "need-based only" in the UI -- a false statement
about a named institution, which is the worst error this app can make.

Sixteen more could not be verified at all: their CDS was unreachable (404/403, expired
Box links, a Tableau dashboard), or the H2A values were in AcroForm fields rather than
page text, or masked (Hamilton prints "** *"). Those are now `unknown`, which has
always meant *unchecked* and now actually is.

Yale is the reason every record carries a year. Its H2A line n reads 6/28/1 in
2023-24, 6/24/0 in 2024-25 and 0/0/0 in 2025-26. The answer genuinely changes between
editions, so a policy claim without a year attached is not a fact.

WHAT H2A LINE n MEANS
---------------------
"Number of students in line a who had no financial need and who were awarded
institutional non-need-based scholarship or grant aid (exclude those who were awarded
athletic awards and tuition benefits)."

So this covers **academic / non-athletic institutional merit aid only**. It is not a
claim about athletic scholarships: Stanford reports 547 athletic awards and Colgate
329, both excluded from line n by the question's own wording. A college can be
`need_only` here and still fund athletes.

It is also narrow in the other direction: the CDS counts only students with *no*
financial need, so merit money layered on top of a need award is invisible to it.
`need_only` therefore means "reported zero on H2A line n", not "no student ever
received a dollar for merit".
"""
from __future__ import annotations

import pandas as pd

# Policy values. `unknown` is the default for the whole dataset and means UNCHECKED --
# never "awards no merit aid", and never "awards merit aid".
NEED_ONLY = "need_only"
AWARDS_MERIT = "awards_merit"
UNKNOWN = "unknown"

# Every record below was read by Claude Code from the institution's own CDS document
# on the date shown. `line_n` is H2A line n verbatim, in the CDS column order:
# first-time full-time first-year / full-time undergrad / less-than-full-time.
# method="parsed+read" means the PDF text was extracted mechanically and the H2A row
# was then read by a human-equivalent check of the surrounding text, not pattern-matched
# in isolation.
_VERIFIED: tuple[dict, ...] = (
    # --- reported ZERO on H2A line n ---
    {"unitid": 190099, "name": "Colgate University", "policy": NEED_ONLY,
     "cds_year": "2024-25", "line_n": "0 / 0 / 0", "avg": "$0 / $0 / $0",
     "note": "Awards 329 athletic scholarships (H2A line p), excluded from line n.",
     "source_url": "https://www.colgate.edu/sites/default/files/2025-07/Colgate%202024-25%20CDS%20for%20Website.pdf"},
    {"unitid": 212911, "name": "Haverford College", "policy": NEED_ONLY,
     "cds_year": "2025-26", "line_n": "0 / 0 / 0", "avg": "$0 / $0 / $0",
     "note": "",
     "source_url": "https://www.haverford.edu/sites/default/files/Office/President/CDS-2025-26.pdf"},
    {"unitid": 166683, "name": "Massachusetts Institute of Technology", "policy": NEED_ONLY,
     "cds_year": "2024-25", "line_n": "N/App", "avg": "N/App",
     "note": "Reports the whole H2A block as Not Applicable.",
     "source_url": "https://ir.mit.edu/projects/2024-25-common-data-set/"},
    {"unitid": 130794, "name": "Yale University", "policy": NEED_ONLY,
     "cds_year": "2025-26", "line_n": "0 / 0 / 0", "avg": "NA",
     "note": "Prior editions were NOT zero: 6/24/0 in 2024-25, 6/28/1 in 2023-24.",
     "source_url": "https://oir.yale.edu/sites/default/files/yale_cds_2025-26_md_20260616.pdf"},

    # --- reported NON-ZERO on H2A line n: these award academic merit aid ---
    {"unitid": 166027, "name": "Harvard University", "policy": AWARDS_MERIT,
     "cds_year": "2025-26", "line_n": "4 / 20", "avg": "$4,728 / $5,279",
     "note": "Previously labelled need-based only. That was wrong.",
     "source_url": "https://bpb-us-e1.wpmucdn.com/sites.harvard.edu/dist/6/210/files/2026/07/CDS_2025-2026.pdf"},
    {"unitid": 243744, "name": "Stanford University", "policy": AWARDS_MERIT,
     "cds_year": "2025-26", "line_n": "3 / 14", "avg": "$11,890 / $13,813",
     "note": "Separate from its 140/547 athletic awards on line p.",
     "source_url": "https://irds.stanford.edu/data-findings/cds"},
    {"unitid": 168218, "name": "Wellesley College", "policy": AWARDS_MERIT,
     "cds_year": "2025-26", "line_n": "4 / 5 / 0", "avg": "$55,716",
     "note": "Near full tuition per recipient.",
     "source_url": "https://wellesley-college.files.svdcdn.com/production/administrative-departments"},
    {"unitid": 230959, "name": "Middlebury College", "policy": AWARDS_MERIT,
     "cds_year": "2024-25", "line_n": "3 / 8 / 0", "avg": "$2,700 / $3,850 / $0",
     "note": "",
     "source_url": "https://www.middlebury.edu/sites/default/files/2026-04/Fall%202025%20CDS%20FINAL.pdf"},
    {"unitid": 164465, "name": "Amherst College", "policy": AWARDS_MERIT,
     "cds_year": "2024-25", "line_n": "0 / 6 / 0", "avg": "$0 / $14,801 / $0",
     "note": "",
     "source_url": "https://www.amherst.edu/institutional-research/common-data-set"},
)

CHECKED_ON = "2026-11-17"
METHOD = "parsed+read"

# Institutions that were on the old hand-compiled roster but could NOT be verified.
# Kept only so the UI and PROJECT_STATE can state honestly how far the check got; they
# carry no policy value and are treated exactly like the other ~1,880 colleges.
_UNVERIFIED: tuple[tuple[int, str, str], ...] = (
    (217156, "Brown University", "CDS download 404"),
    (190150, "Columbia University in the City of New York", "H2A values absent from PDF text"),
    (190415, "Cornell University", "xlsx; H2A cells coded, values not aligned"),
    (182670, "Dartmouth College", "H2A row present, values absent from PDF text"),
    (215062, "University of Pennsylvania", "CDS behind an expired Box link"),
    (186131, "Princeton University", "CDS download 404; H2A cells blank in 2024-25 copy"),
    (110404, "California Institute of Technology", "H2A values absent from PDF text"),
    (131496, "Georgetown University", "CDS behind an expired Box link"),
    (189097, "Barnard College", "H2A values absent from PDF text"),
    (160977, "Bates College", "fillable PDF; values in AcroForm fields"),
    (161004, "Bowdoin College", "fillable PDF; values in AcroForm fields"),
    (161086, "Colby College", "only a 2019-20 CDS is published; too stale to rely on"),
    (191515, "Hamilton College", "H2A values masked as '** *'"),
    (121345, "Pomona College", "CDS published only as a Tableau dashboard"),
    (216287, "Swarthmore College", "no current CDS located"),
    (197133, "Vassar College", "fillable PDF; values in AcroForm fields"),
    (168342, "Williams College", "CDS download 403"),
)

_BY_UNITID: dict[int, dict] = {r["unitid"]: r for r in _VERIFIED}
NEED_ONLY_UNITIDS: frozenset[int] = frozenset(
    u for u, r in _BY_UNITID.items() if r["policy"] == NEED_ONLY)
AWARDS_MERIT_UNITIDS: frozenset[int] = frozenset(
    u for u, r in _BY_UNITID.items() if r["policy"] == AWARDS_MERIT)


def merit_policy(unitids: pd.Series) -> pd.Series:
    """Map UNITID -> policy value. Anything unverified is `unknown`."""
    return pd.Series(
        [_BY_UNITID.get(u, {}).get("policy", UNKNOWN) for u in unitids],
        index=unitids.index, dtype="object",
    )


def provenance(unitid: int) -> dict | None:
    """The full source record for one institution, or None if never verified."""
    r = _BY_UNITID.get(int(unitid))
    if r is None:
        return None
    return {**r, "checked_on": CHECKED_ON, "method": METHOD}


def roster() -> list[dict]:
    """Every verified record, with its provenance. Sorted by policy then name."""
    return [
        {**r, "checked_on": CHECKED_ON, "method": METHOD}
        for r in sorted(_VERIFIED, key=lambda r: (r["policy"], r["name"]))
    ]


def unverified() -> list[dict]:
    """Institutions the CDS check could not resolve, with the reason."""
    return [{"unitid": u, "name": n, "reason": why} for u, n, why in _UNVERIFIED]


def coverage() -> dict:
    """How far the CDS sourcing actually got. The UI reports this instead of a count."""
    return {
        "verified": len(_VERIFIED),
        "need_only": len(NEED_ONLY_UNITIDS),
        "awards_merit": len(AWARDS_MERIT_UNITIDS),
        "attempted": len(_VERIFIED) + len(_UNVERIFIED),
        "unresolved": len(_UNVERIFIED),
        "checked_on": CHECKED_ON,
        "source": "Common Data Set section H2A, line n",
    }
