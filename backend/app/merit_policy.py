"""Institutional merit-aid policy, sourced from each college's own Common Data Set.

SCOPE: THE SHORTLIST, NOT THE DATASET (2026-11-17, Phase 4)
-----------------------------------------------------------
Full-dataset CDS coverage was evaluated and rejected on evidence. Reading all 26
institutions on the original hand-compiled roster resolved 10 of them -- 38%
end-to-end -- and those were the Ivies and the NESCAC, the institutions most likely
to publish a readable CDS. An independent third-party CDS archive finds no public
CDS at all for 1,464 of 3,000 institutions. A 1,907-college crawl would land near
20-35%, skewed hard toward wealthy privates, so it was not built.

What is attempted instead is the **default top 50 shortlist** -- the rows a user
actually sees. All 50 have now been attempted; 23 resolved. Everything outside that
shortlist is `unknown`, which means UNCHECKED.

Coverage figures from this module therefore describe a skewed slice and must be
reported with that caveat. The top 50 is 48 private nonprofits and 2 publics -- 96%
private against 57.4% (1,095 of 1,907) in the full dataset -- and it is drawn from
the most selective, best-endowed end of that. 23 of the 50 resolved: 21 of 48
privates and both publics. The 2-college public sample supports no claim either way
about sector, so the skew to report is the *composition* of the slice, not a
measured sector difference. What does bear on the full dataset is external: a
third-party CDS archive finds no public CDS for 1,464 of 3,000 institutions, which
points to the full-dataset rate being worse than 46%, not better.

WHAT CHANGED AND WHY
--------------------
This module used to assert that 26 institutions award no merit aid, on the basis of
"published institutional policy" compiled by hand and never checked line by line.
Checking all 26 against their own CDS section H2A disproved five of them:

    Harvard     CDS 2025-26   H2A line n =  4 /  20      avg $4,728 / $5,279
    Stanford    CDS 2025-26   H2A line n =  3 /  14      avg $11,890 / $13,813
    Wellesley   CDS 2025-26   H2A line n =  4 /   5 / 0  avg $55,716
    Middlebury  CDS 2024-25   H2A line n =  3 /   8 / 0  avg $2,700 / $3,850
    Amherst     CDS 2024-25   H2A line n =  0 /   6 / 0  avg $14,801

Each was being labelled "need-based only" in the UI -- a false statement about a
named institution, which is the worst error this app can make.

Extending to the top 50 resolved 15 more, 14 of which award merit aid, including
Washington and Lee at rank 3 (29 / 132 / 0, averaging $62,110 for a first-year
recipient). Only one of the 15, Carleton, reports zero.

WHY EVERY RECORD CARRIES A YEAR, AND WHY STALE RECORDS EXPIRE
-------------------------------------------------------------
Yale's H2A line n reads 6/28/1 in 2023-24, 6/24/0 in 2024-25 and 0/0/0 in 2025-26.
The answer genuinely changes between editions, so a policy claim without a year
attached is not a fact, and a claim from an old edition is not evidence about today.

`STALE_AFTER_EDITIONS` makes that automatic: a record more than two editions behind
`CURRENT_EDITION` stops being reported and reverts to `unknown`. Nothing silently
ages into a stale assertion -- when the 2026-27 editions land, the 2024-25 records
expire by themselves and have to be re-read. This is the rule that was already
applied by hand to Colby, whose only published CDS is 2019-20.

WHAT H2A LINE n MEANS
---------------------
"Number of students in line a who had no financial need and who were awarded
institutional non-need-based scholarship or grant aid (exclude those who were
awarded athletic awards and tuition benefits)."

So this covers **academic / non-athletic institutional merit aid only**. It is not a
claim about athletic scholarships: Stanford reports 547 athletic awards and Colgate
329, both excluded from line n by the question's own wording. A college can be
`need_only` here and still fund athletes.

It is also narrow in the other direction: the CDS counts only students with *no*
financial need, so merit money layered on top of a need award is invisible to it.
`need_only` therefore means "reported zero on H2A line n for that edition", not "no
student ever received a dollar for merit".
"""
from __future__ import annotations

import functools
from types import MappingProxyType

import pandas as pd

# Policy values. `unknown` is the default for the whole dataset and means UNCHECKED --
# never "awards no merit aid", and never "awards merit aid".
NEED_ONLY = "need_only"
AWARDS_MERIT = "awards_merit"
UNKNOWN = "unknown"

# Per-row sourcing status. This is what lets the UI distinguish the two very
# different reasons a college shows no label: we read its CDS and it does not
# publish H2A readably, versus we never looked at it at all. Collapsing those into
# one dash is how a gap starts reading as an answer.
RESOLVED = "resolved"
ATTEMPTED_UNRESOLVED = "attempted_unresolved"
NOT_CHECKED = "not_checked"

# The newest CDS edition in circulation, and how far back a record may be before it
# expires. Two editions back is the window: it keeps a college that files late from
# flickering to `unknown` for a few months, while guaranteeing no verdict older than
# three years is ever shown. Bump CURRENT_EDITION when the next cycle publishes --
# records that fall outside the window revert to `unknown` with no further edits.
CURRENT_EDITION = "2025-26"
STALE_AFTER_EDITIONS = 2

# Every record below was read by Claude Code from the institution's own CDS document
# on the date shown. `line_n` is H2A line n verbatim, in the CDS column order:
# first-time full-time first-year / full-time undergrad / less-than-full-time (some
# institutions publish only the first two columns; those records carry two).
# method="parsed+read" means the document was extracted mechanically -- page text,
# AcroForm fields for a fillable PDF, or cells for a workbook -- and the H2A row was
# then read in context rather than pattern-matched in isolation.
_VERIFIED: tuple[dict, ...] = (
    # ---------------- reported ZERO on H2A line n ----------------
    {"unitid": 190099, "name": "Colgate University", "policy": NEED_ONLY,
     "cds_year": "2024-25", "line_n": "0 / 0 / 0", "avg": "$0 / $0 / $0",
     "note": "Awards 329 athletic scholarships (H2A line p), excluded from line n.",
     "source_url": "https://www.colgate.edu/sites/default/files/2025-07/Colgate%202024-25%20CDS%20for%20Website.pdf"},
    {"unitid": 212911, "name": "Haverford College", "policy": NEED_ONLY,
     "cds_year": "2025-26", "line_n": "0 / 0 / 0", "avg": "$0 / $0 / $0",
     "note": "",
     "source_url": "https://www.haverford.edu/sites/default/files/Office/President/CDS-2025-26.pdf"},
    {"unitid": 166683, "name": "Massachusetts Institute of Technology", "policy": NEED_ONLY,
     "cds_year": "2025-26", "line_n": "0 / 0 / 0", "avg": "N/App",
     "note": "Re-sourced from 2024-25 to 2025-26. The 2024-25 edition answers line n "
             "itself 'N/App', which is a non-answer, not a reported zero -- it could "
             "not support this verdict. The 2025-26 edition reports an actual 0/0/0, "
             "with N/App on line o because there are no recipients to average.",
     "source_url": "https://ir.mit.edu/projects/2025-26-common-data-set/"},
    {"unitid": 130794, "name": "Yale University", "policy": NEED_ONLY,
     "cds_year": "2025-26", "line_n": "0 / 0 / 0", "avg": "NA",
     "note": "Prior editions were NOT zero: 6/24/0 in 2024-25, 6/28/1 in 2023-24.",
     "source_url": "https://oir.yale.edu/sites/default/files/yale_cds_2025-26_md_20260616.pdf"},
    {"unitid": 173258, "name": "Carleton College", "policy": NEED_ONLY,
     "cds_year": "2025-26", "line_n": "0 / 0", "avg": "not reported",
     "note": "Fillable PDF: line n read from AcroForm fields FRSH_FT_NN_GIFT_N and "
             "UG_FT_NN_GIFT_N, both an explicit '0' (not an empty field). Athletic "
             "line p is 0 / 0 as well.",
     "source_url": "https://carleton-wp-production.s3.amazonaws.com/uploads/sites/292/2026/04/CDS-PDF-2025-2026_PDF_Carleton_041426.pdf"},

    # ------- reported NON-ZERO on H2A line n: these award academic merit aid -------
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
    {"unitid": 234207, "name": "Washington and Lee University", "policy": AWARDS_MERIT,
     "cds_year": "2025-26", "line_n": "29 / 132 / 0", "avg": "$62,110 / $49,209 / $0",
     "note": "Rank 3 in the default view, and was labelled unknown before this check. "
             "The largest per-recipient award of any institution resolved here.",
     "source_url": "https://my.wlu.edu/document/2025-common-data-set"},
    {"unitid": 227757, "name": "Rice University", "policy": AWARDS_MERIT,
     "cds_year": "2025-26", "line_n": "74 / 225", "avg": "$34,586 / $27,293",
     "note": "",
     "source_url": "https://ideas.rice.edu/wp-content/uploads/2026/10/CDS_2025-26_WEBSITE_Updated_10-7-2026.pdf"},
    {"unitid": 144050, "name": "University of Chicago", "policy": AWARDS_MERIT,
     "cds_year": "2025-26", "line_n": "57 / 428", "avg": "$16,333 / $21,320",
     "note": "",
     "source_url": "https://data.uchicago.edu/files/2026/08/CDS_2025-2026_to_publish-1.pdf"},
    {"unitid": 198385, "name": "Davidson College", "policy": AWARDS_MERIT,
     "cds_year": "2025-26", "line_n": "64 / 262", "avg": "not reported",
     "note": "Fillable PDF; line n read from AcroForm fields. The matching dollar "
             "fields are empty in the file, so no average is claimed here.",
     "source_url": "https://www.davidson.edu/media/9718/download?attachment"},
    {"unitid": 221999, "name": "Vanderbilt University", "policy": AWARDS_MERIT,
     "cds_year": "2025-26", "line_n": "134 / 744", "avg": "$32,791 / $33,730",
     "note": "Published as a workbook; read from the CDS-H sheet (rows H.2A01-H.2A06).",
     "source_url": "https://cdn.vanderbilt.edu/vu-wpfsx/wp-content/uploads/sites/70/2026/07/CDS_2025-2026.xlsx"},
    {"unitid": 198419, "name": "Duke University", "policy": AWARDS_MERIT,
     "cds_year": "2025-26", "line_n": "9 / 131 / 0", "avg": "$91,953 / $87,775 / $0",
     "note": "Average exceeds its own cost of attendance for a first-year recipient; "
             "the CDS reports it that way.",
     "source_url": "https://ir.provost.duke.edu/sites/default/files/CDS_PDF_2025-2026-20260622-website-published-version.pdf"},
    {"unitid": 164216, "name": "Washington College", "policy": AWARDS_MERIT,
     "cds_year": "2025-26", "line_n": "69 / 304 / 0", "avg": "$35,954 / $36,476 / $0",
     "note": "",
     "source_url": "https://washcoll.edu/people_departments/offices/institutional-research/common_data_sets_cds/common-data-set-2025-2026-use.pdf"},
    {"unitid": 179867, "name": "Washington University in St Louis", "policy": AWARDS_MERIT,
     "cds_year": "2025-26", "line_n": "44 / 220", "avg": "$36,250 / $35,769",
     "note": "",
     "source_url": "https://washu.edu/app/uploads/2026/06/2025-2026-WashU-CDS.pdf"},
    {"unitid": 153384, "name": "Grinnell College", "policy": AWARDS_MERIT,
     "cds_year": "2024-25", "line_n": "102 / 456 / 0", "avg": "$26,154 / $21,305",
     "note": "No 2025-26 edition is published; 2024-25 is the newest and is inside "
             "the staleness window.",
     "source_url": "https://www.grinnell.edu/doc/grinnell-college-common-data-set-2024-2025"},
    {"unitid": 199847, "name": "Wake Forest University", "policy": AWARDS_MERIT,
     "cds_year": "2025-26", "line_n": "249 / 889 / 21", "avg": "not reported",
     "note": "Fillable PDF; line n read from AcroForm fields. The dollar fields for "
             "line o are empty, though the athletic ones (line q) are populated.",
     "source_url": "https://prod.wp.cdn.aws.wfu.edu/sites/202/2026/06/CDS_2025-2026-PDF_Template_WFU.pdf"},
    {"unitid": 170976, "name": "University of Michigan-Ann Arbor", "policy": AWARDS_MERIT,
     "cds_year": "2025-26", "line_n": "1,261 / 4,300 / 99", "avg": "$4,587 / $6,240 / $4,251",
     "note": "One of only two publics in the default top 50. Far more recipients than "
             "any private here, at a far smaller award.",
     "source_url": "https://obp.umich.edu/wp-content/uploads/pubdata/cds/cds_2025-26_umaa.pdf"},
    {"unitid": 147767, "name": "Northwestern University", "policy": AWARDS_MERIT,
     "cds_year": "2024-25", "line_n": "15 / 62", "avg": "$29,000 / $21,215",
     "note": "2024-25 is the newest edition published at the host used.",
     "source_url": "https://enrollment.northwestern.edu/data/2024-2025.pdf"},
    {"unitid": 112260, "name": "Claremont McKenna College", "policy": AWARDS_MERIT,
     "cds_year": "2025-26", "line_n": "24 / 106 / 0", "avg": "$13,011 / $19,332 / $0",
     "note": "Reports zero athletic awards on line p, so line n is the whole of its "
             "non-need-based aid. Inner page headers still read 2024-2025; the cover "
             "and the H4 graduation window both place it in the 2025-26 collection.",
     "source_url": "https://www.cmc.edu/sites/default/files/CDS_2025-26_Annotated(Updated20260605).pdf"},
    {"unitid": 199120, "name": "University of North Carolina at Chapel Hill", "policy": AWARDS_MERIT,
     "cds_year": "2025-26", "line_n": "275 / 1,990 / 33", "avg": "$7,233 / $5,633 / $4,260",
     "note": "The other public in the default top 50.",
     "source_url": "https://oira.unc.edu/wp-content/uploads/sites/297/2026/06/CDS_UNCCH_2025-26_20260615.pdf"},
)

CHECKED_ON = "2026-11-17"
METHOD = "parsed+read"

# Institutions whose CDS was looked for and could not be read. They carry no policy
# value and score exactly like the ~1,850 colleges nobody has checked -- the only
# difference is that the UI can say "checked, not published" instead of a bare dash,
# and that this list is the honest denominator for any coverage claim.
_UNVERIFIED: tuple[tuple[int, str, str], ...] = (
    # --- from the original 26-institution roster ---
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
    (161086, "Colby College", "only a 2019-20 CDS is published; outside the staleness window"),
    (191515, "Hamilton College", "H2A values masked as '** *'"),
    (121345, "Pomona College", "CDS published only as a Tableau dashboard"),
    (216287, "Swarthmore College", "no current CDS located"),
    (197133, "Vassar College", "fillable PDF; values in AcroForm fields"),
    (168342, "Williams College", "CDS download 403"),

    # --- added by the top-50 sweep ---
    (162928, "Johns Hopkins University", "CDS download 403; host refuses non-browser clients"),
    (130697, "Wesleyan University", "current CDS published only in an authenticated SharePoint folder"),
    (399911, "Soka University of America", "CDS published only via a Box share; direct download 403"),
    (143084, "Augustana College", "H2A table absent from the PDF text layer"),
    (202073, "Cleveland Institute of Music", "publishes IPEDS / College Navigator figures instead of a CDS"),
    (115728, "Holy Names University", "closed 2023; no CDS located"),
    (156295, "Berea College", "no institution-hosted CDS located"),
    (197221, "Webb Institute", "no institution-hosted CDS located"),
    (149639, "VanderCook College of Music", "no institution-hosted CDS located"),
    (182917, "Magdalen College", "no institution-hosted CDS located; site unreachable"),
    (213367, "La Salle University", "no institution-hosted CDS located"),
    (247773, "Yeshiva Gedolah of Greater Detroit", "no institution-hosted CDS located"),
    (190372, "The Cooper Union for the Advancement of Science and Art", "no institution-hosted CDS located"),
    (147244, "Millikin University", "no institution-hosted CDS located"),
    (183275, "Thomas More College of Liberal Arts", "no institution-hosted CDS located"),
)


def _edition_start(cds_year: str) -> int:
    """'2024-25' -> 2024. The edition's own label, not a parsed date."""
    return int(str(cds_year)[:4])


def is_current(cds_year: str, current_edition: str | None = None) -> bool:
    """Is a verdict from this CDS edition still reportable?

    A policy claim is point-in-time (see Yale). Outside the window the record stops
    being an answer and the institution reverts to `unknown`.

    `current_edition` defaults to the module constant and exists so the expiry rule
    can be exercised against a *future* edition. Without it the mechanism is dormant
    -- today nothing is stale, so the stale branches never run until a human bumps
    CURRENT_EDITION, which is precisely when you want them already tested.
    """
    ref = CURRENT_EDITION if current_edition is None else current_edition
    return _edition_start(ref) - _edition_start(cds_year) <= STALE_AFTER_EDITIONS


_BY_UNITID: dict[int, dict] = {r["unitid"]: r for r in _VERIFIED}
_UNVERIFIED_IDS: frozenset[int] = frozenset(u for u, _, _ in _UNVERIFIED)


@functools.lru_cache(maxsize=8)
def _partition(current_edition: str, stale_after: int):
    """Split the roster into reportable and expired, for a given edition.

    Read at call time rather than frozen at import, and keyed on the edition, so that
    moving CURRENT_EDITION forward actually moves records out of the roster. The
    partition is a pure function of (records, edition, window) -- the caches are
    read-only views, because an lru_cache handing out a mutable dict is a global
    waiting to be edited by accident.
    """
    current = {u: r for u, r in _BY_UNITID.items()
               if _edition_start(current_edition) - _edition_start(r["cds_year"]) <= stale_after}
    stale = {u: r for u, r in _BY_UNITID.items() if u not in current}
    return MappingProxyType(current), MappingProxyType(stale)


def _current():
    """Records still inside the staleness window, as a read-only mapping."""
    return _partition(CURRENT_EDITION, STALE_AFTER_EDITIONS)[0]


def _stale():
    """Records that have aged out and now read as `unknown`."""
    return _partition(CURRENT_EDITION, STALE_AFTER_EDITIONS)[1]


def need_only_unitids() -> frozenset[int]:
    """UNITIDs currently reported as having answered zero on H2A line n."""
    return frozenset(u for u, r in _current().items() if r["policy"] == NEED_ONLY)


def awards_merit_unitids() -> frozenset[int]:
    """UNITIDs currently reported as having answered more than zero on H2A line n."""
    return frozenset(u for u, r in _current().items() if r["policy"] == AWARDS_MERIT)


def merit_policy(unitids: pd.Series) -> pd.Series:
    """Map UNITID -> policy value. Unverified or stale is `unknown`."""
    return pd.Series(
        [_current().get(u, {}).get("policy", UNKNOWN) for u in unitids],
        index=unitids.index, dtype="object",
    )


def merit_policy_year(unitids: pd.Series) -> pd.Series:
    """Map UNITID -> the CDS edition the verdict came from, '' when there is none.

    Carried onto the row so the label can name its year. A verdict whose year the UI
    cannot show is a verdict the user has to take on trust.
    """
    return pd.Series(
        [_current().get(u, {}).get("cds_year", "") for u in unitids],
        index=unitids.index, dtype="object",
    )


def merit_policy_status(unitids: pd.Series) -> pd.Series:
    """Map UNITID -> `resolved` / `attempted_unresolved` / `not_checked`.

    Splits the two kinds of blank. A college whose CDS was read but does not publish
    H2A readably is a different statement from one nobody has looked at, and the
    difference is the whole basis for reporting coverage honestly.
    """
    current, stale = _current(), _stale()

    def one(u: int) -> str:
        if u in current:
            return RESOLVED
        if u in _UNVERIFIED_IDS or u in stale:
            return ATTEMPTED_UNRESOLVED
        return NOT_CHECKED

    return pd.Series([one(u) for u in unitids], index=unitids.index, dtype="object")


def provenance(unitid: int) -> dict | None:
    """The full source record for one institution, or None if not currently reported."""
    r = _current().get(int(unitid))
    if r is None:
        return None
    return {**r, "checked_on": CHECKED_ON, "method": METHOD}


def roster() -> list[dict]:
    """Every currently-reported record, with its provenance. Sorted by policy, name."""
    return [
        {**r, "checked_on": CHECKED_ON, "method": METHOD}
        for r in sorted(_current().values(), key=lambda r: (r["policy"], r["name"]))
    ]


def unverified() -> list[dict]:
    """Institutions the CDS check could not resolve, with the reason.

    Includes records that aged out of the staleness window: those were attempted and
    are no longer reportable, which is the same thing from a user's point of view.
    """
    out = [{"unitid": u, "name": n, "reason": why} for u, n, why in _UNVERIFIED]
    out += [
        {"unitid": u, "name": r["name"],
         "reason": f"CDS {r['cds_year']} is outside the staleness window "
                   f"(current edition {CURRENT_EDITION}, {STALE_AFTER_EDITIONS} back)"}
        for u, r in sorted(_stale().items())
    ]
    return out


def coverage() -> dict:
    """How far the CDS sourcing actually got.

    `attempted` is the honest denominator and `scope` says where the effort went, so
    a client can report resolved / attempted / total instead of one number that
    invites being read as completeness.
    """
    return {
        "verified": len(_current()),
        "need_only": len(need_only_unitids()),
        "awards_merit": len(awards_merit_unitids()),
        "attempted": len(_current()) + len(_UNVERIFIED) + len(_stale()),
        "unresolved": len(_UNVERIFIED) + len(_stale()),
        "stale": len(_stale()),
        "checked_on": CHECKED_ON,
        "current_edition": CURRENT_EDITION,
        "stale_after_editions": STALE_AFTER_EDITIONS,
        "source": "Common Data Set section H2A, line n",
        "scope": "the default top 50 shortlist, attempted in full; not the 1,907-college dataset",
        "sector_caveat": "the top 50 is 48 private nonprofits and 2 publics -- 96% "
                         "private against 57.4% of the full dataset -- and is drawn "
                         "from its most selective, best-endowed end, so this "
                         "resolution rate describes a skewed slice and should not be "
                         "read as what the whole dataset would give",
    }
