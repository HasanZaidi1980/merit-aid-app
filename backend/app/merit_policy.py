"""Which institutions award merit aid -- the one thing IPEDS does not tell us.

`IGRNT_A` is *total* institutional grant aid: need-based awards and merit awards
added together. All 663 columns of SFA2122 were checked and no variable splits
them; NCES does not require institutions to report the split at all. So every
generosity metric in this app -- MGI, AID_SHARE -- measures institutional
generosity, not merit generosity.

That distinction matters because the two work by opposite mechanisms. Need-based
aid is awarded on the family's finances; merit aid is awarded on the student's
record. A college can therefore be extremely generous and still be unreachable
for a family hoping to *earn* a scholarship: the money is real, but no amount of
academic improvement unlocks it. Before this module, 11 of the top 23 ranked
colleges awarded no merit aid whatsoever, with nothing in the UI to say so.

The authoritative fix is the Common Data Set, section H2A, which splits
need-based from non-need-based institutional aid per institution. There is no
bulk download, so covering all 1,907 colleges is a scraping project -- see
PROJECT_STATE.md Phase 4. Until then this module closes the worst of the gap
with a hand-curated list of institutions that publicly award no merit
scholarships at all.

The list is deliberately small and deliberately one-sided. Absence from it means
"not checked", never "awards merit aid" -- which is why the column carries
`unknown` rather than a boolean `False`. Treating silence as a negative would
swap a visible gap for an invisible wrong answer.
"""
import pandas as pd

# No *academic merit* scholarships: institutional grant aid is awarded on
# demonstrated financial need alone.
#
# Scope note, because the distinction is easy to overclaim: several entries here
# are Division I and do award athletic scholarships (Stanford, Georgetown,
# Colgate). That is outside what this flag is about. The question the app has to
# answer is "can a strong student earn a scholarship here with their record?",
# and for every institution on this list the answer is no.
#
# Two bases, both institution-published rather than inferred:
#
#   ivy_agreement   The Ivy League agreement commits all eight members to
#                   need-based aid only -- no academic *or* athletic
#                   scholarships. The most stable entries here.
#   published       The institution's own financial-aid pages state that all aid
#                   is need-based and that it offers no merit scholarships.
#
# Keyed on UNITID, not name: IPEDS names carry punctuation and legal suffixes
# that shift between releases ("Columbia University in the City of New York"),
# and a name match that silently stops matching would quietly disable the flag.
# The name is recorded only so a reader can audit a row without a lookup.
#
# STATUS: provisional. Compiled from well-documented institutional policy, NOT
# yet checked line-by-line against each institution's current CDS H2A. Verify
# before treating a `need_only` label as authoritative -- see PROJECT_STATE.md.
_NEED_ONLY: tuple[tuple[int, str, str], ...] = (
    # --- Ivy League (ivy_agreement) ---
    (217156, "Brown University", "ivy_agreement"),
    (190150, "Columbia University in the City of New York", "ivy_agreement"),
    (190415, "Cornell University", "ivy_agreement"),
    (182670, "Dartmouth College", "ivy_agreement"),
    (166027, "Harvard University", "ivy_agreement"),
    (215062, "University of Pennsylvania", "ivy_agreement"),
    (186131, "Princeton University", "ivy_agreement"),
    (130794, "Yale University", "ivy_agreement"),
    # --- Other research universities (published) ---
    (110404, "California Institute of Technology", "published"),
    (131496, "Georgetown University", "published"),
    (166683, "Massachusetts Institute of Technology", "published"),
    (243744, "Stanford University", "published"),
    # --- Liberal arts colleges (published) ---
    (164465, "Amherst College", "published"),
    (189097, "Barnard College", "published"),
    (160977, "Bates College", "published"),
    (161004, "Bowdoin College", "published"),
    (161086, "Colby College", "published"),
    (190099, "Colgate University", "published"),
    (191515, "Hamilton College", "published"),
    (212911, "Haverford College", "published"),
    (230959, "Middlebury College", "published"),
    (121345, "Pomona College", "published"),
    (216287, "Swarthmore College", "published"),
    (197133, "Vassar College", "published"),
    (168218, "Wellesley College", "published"),
    (168342, "Williams College", "published"),
)

NEED_ONLY_UNITIDS: frozenset[int] = frozenset(u for u, _, _ in _NEED_ONLY)

# Column values. Kept as strings rather than a bool so a third state can be
# added (e.g. "merit_confirmed" once CDS data lands) without a schema change.
NEED_ONLY = "need_only"
UNKNOWN = "unknown"


def merit_policy(unitids: pd.Series) -> pd.Series:
    """Label each institution's merit-aid policy: `need_only` or `unknown`."""
    return pd.Series(
        [NEED_ONLY if u in NEED_ONLY_UNITIDS else UNKNOWN for u in unitids],
        index=unitids.index, dtype="object",
    )


def roster() -> list[dict]:
    """The curated list itself, for the API to expose and the UI to cite."""
    return [{"unitid": u, "name": n, "basis": b} for u, n, b in _NEED_ONLY]
