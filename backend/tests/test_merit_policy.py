"""Merit-aid policy flagging.

The app is named for merit aid but IGRNT_A conflates need-based and merit grants,
and IPEDS publishes no split. Per-institution CDS H2A sourcing is the partial fix;
these tests pin the properties that make it honest rather than misleading:

  1. `unknown` must never read as a claim. It means UNCHECKED, which is true of
     almost the whole dataset, and it must stay distinct from BOTH findings.
  2. The flag must not touch any score. It is a fact about the college, not a
     measurement of it, so adding it cannot reshuffle the ranking.
  3. Every non-unknown value must carry provenance -- source URL, CDS year, the
     H2A figures and when it was checked. A hand-maintained list without
     provenance rots silently, which is exactly what happened to the version this
     replaced: five of its 26 entries asserted the opposite of what the
     institution's own CDS reported.
"""
import numpy as np
import pandas as pd
import pytest

from app.merit_policy import (AWARDS_MERIT, NEED_ONLY, UNKNOWN, coverage,
                              merit_policy, provenance, roster, unverified)
from app.scoring import add_metrics, rank_and_filter

# Yale and Haverford report zero on CDS H2A line n; Harvard and Stanford report more
# than zero. Harvard and Stanford were on the old need-only roster and were being
# mislabelled -- these constants are the regression guard for that.
YALE, HAVERFORD = 130794, 212911
HARVARD, STANFORD = 166027, 243744
NOT_ON_LIST = 999001  # no such institution; stands in for "never checked"

HEALTHY = dict(TUITION2=30000.0, CHG4AY3=12000.0, CHG5AY3=1200.0, IGRNT_A=15000.0,
               NET_PRICE_MID=18000.0, GRAD_RATE=0.70, ADMISSIONS_RATE=0.55,
               SATVR75=600.0, SATMT75=620.0)
COA_PARTS = ["TUITION2", "CHG4AY3", "CHG5AY3"]


def _build(rows: list[dict]) -> pd.DataFrame:
    """Assemble a frame the way data.build_dataset() does. UNITID is explicit here,
    because that is the key the policy records match on."""
    df = pd.DataFrame(rows)
    df["COA"] = df[COA_PARTS].sum(axis=1, min_count=1)
    df["COA_COMPLETE"] = df[COA_PARTS].notna().all(axis=1)
    df["SAT_TOTAL_75"] = df["SATVR75"] + df["SATMT75"]
    return add_metrics(df)


@pytest.fixture
def four_colleges() -> pd.DataFrame:
    """One of each policy value, plus a second need_only. Identical in every other
    respect, so any difference in score between them could only come from the flag."""
    return _build([
        {**HEALTHY, "UNITID": YALE, "INSTNM": "Yale University"},
        {**HEALTHY, "UNITID": HAVERFORD, "INSTNM": "Haverford College"},
        {**HEALTHY, "UNITID": HARVARD, "INSTNM": "Harvard University"},
        {**HEALTHY, "UNITID": NOT_ON_LIST, "INSTNM": "Unchecked College"},
    ])


def test_policy_keys_on_unitid_not_name():
    """Names carry legal suffixes that shift between releases; UNITIDs do not."""
    ids = pd.Series([YALE, NOT_ON_LIST, HARVARD])
    assert list(merit_policy(ids)) == [NEED_ONLY, UNKNOWN, AWARDS_MERIT]

    # A college renamed in a later IPEDS release must still resolve.
    assert merit_policy(pd.Series([HAVERFORD])).iloc[0] == NEED_ONLY


def test_unknown_is_not_a_claim(four_colleges):
    """Absence from the verified set means unchecked -- not either finding.

    This is the whole reason the column is a string and not a bool. 9 of 1,907
    colleges have been checked against their own CDS; a False on the other 1,898
    would turn a known gap into an invented answer. `awards_merit` now exists as a
    real third value, so `unknown` has to stay distinct from BOTH.
    """
    assert set(four_colleges["MERIT_POLICY"]) == {NEED_ONLY, AWARDS_MERIT, UNKNOWN}
    assert len({NEED_ONLY, AWARDS_MERIT, UNKNOWN}) == 3
    assert four_colleges.loc[3, "MERIT_POLICY"] == UNKNOWN


def test_policy_does_not_touch_any_score(four_colleges):
    """A fact about the college must not change its measurement.

    All four rows carry identical money and outcome figures, so every metric must
    come out identical regardless of merit policy. If this ever fails, the flag has
    leaked into scoring and the rankings moved for a non-reason.
    """
    for col in ["MGI", "AID_SHARE", "VALUE_SCORE", "DISCOUNT", "COMPOSITE_LEGACY"]:
        assert four_colleges[col].nunique() == 1, col

    # And it is not a data-quality problem either -- it belongs in neither column.
    assert (four_colleges["RISK_FLAGS"] == "").all()
    assert (four_colleges["DATA_GAPS"] == "").all()


def test_exclude_no_merit_drops_only_need_only(four_colleges):
    """The filter drops need_only only. It must NOT drop awards_merit (that college
    is the opposite of what the user asked to hide) or unknown (never checked)."""
    kept = set(rank_and_filter(four_colleges, 25000, False, 50, True,
                               exclude_no_merit=True)["INSTNM"])
    assert kept == {"Harvard University", "Unchecked College"}


def test_exclude_no_merit_defaults_off(four_colleges):
    """Opt-in by design: filtering by default would imply the rest were cleared."""
    from app import config

    assert config.DEFAULTS["exclude_no_merit"] is False
    # Positional call without the new argument -- the pre-existing call signature.
    assert len(rank_and_filter(four_colleges, 25000, False, 50, True)) == 4


def test_roster_is_internally_consistent():
    """Guards the failure modes of a hand-maintained list: duplicated rows, and
    claims with no source behind them."""
    entries = roster()
    unitids = [e["unitid"] for e in entries]

    assert len(unitids) == len(set(unitids))
    assert all(isinstance(u, int) for u in unitids)
    assert {e["policy"] for e in entries} <= {NEED_ONLY, AWARDS_MERIT}
    assert all(e["name"] for e in entries)

    # Provenance is the point: every claim names the document it came from, the CDS
    # year it applies to, the figures read, and when and how it was checked.
    for e in entries:
        assert e["source_url"].startswith("http"), e["name"]
        assert e["cds_year"], e["name"]
        assert e["checked_on"] and e["method"], e["name"]
        assert e["line_n"], e["name"]


def test_every_verified_institution_has_provenance():
    for e in roster():
        p = provenance(e["unitid"])
        assert p and p["source_url"] == e["source_url"]
    assert provenance(NOT_ON_LIST) is None


def test_coverage_is_reported_not_implied():
    """The UI must be able to say how far the sourcing got. Reporting a count with
    no denominator is how the previous version implied completeness."""
    c = coverage()
    assert c["need_only"] + c["awards_merit"] == c["verified"]
    assert c["verified"] + c["unresolved"] == c["attempted"]
    assert c["unresolved"] > 0            # honest: the check did not finish
    assert len(unverified()) == c["unresolved"]
    for u in unverified():
        assert u["reason"]                # every gap says why


def test_institutions_that_report_merit_aid_are_not_labelled_need_only():
    """Regression guard. Harvard, Stanford, Wellesley, Middlebury and Amherst were
    all on the old need-only roster while their own CDS H2A line n reported more
    than zero. That was a false statement about a named institution."""
    WELLESLEY, MIDDLEBURY, AMHERST = 168218, 230959, 164465
    got = merit_policy(pd.Series([HARVARD, STANFORD, WELLESLEY, MIDDLEBURY, AMHERST]))
    assert set(got) == {AWARDS_MERIT}


def test_unverified_institutions_are_unknown_not_need_only():
    """The 17 that could not be read must claim nothing at all."""
    for u in unverified():
        assert merit_policy(pd.Series([u["unitid"]])).iloc[0] == UNKNOWN


def test_missing_unitid_column_does_not_crash_the_filter():
    """A frame built before MERIT_POLICY existed must still rank.

    rank_and_filter guards on the column's presence; without that guard an older
    cached frame would raise KeyError rather than simply skipping the filter.
    """
    df = _build([{**HEALTHY, "UNITID": NOT_ON_LIST, "INSTNM": "Solo"}])
    df = df.drop(columns=["MERIT_POLICY"])
    assert len(rank_and_filter(df, 25000, False, 50, True, exclude_no_merit=True)) == 1


def test_summary_skips_nan_and_survives_an_empty_series():
    """The education strips are drawn from these summaries.

    A dimension like SAT covers 985 of 1,907 colleges, so every summary has to be
    computed over the present values only -- counting the blanks would drag every
    median toward zero and quietly mislabel the distribution.
    """
    from app.education import _summary

    s = _summary(pd.Series([1.0, 2.0, np.nan, 3.0, np.nan]))
    assert s["n"] == 3
    assert s["median"] == 2.0
    assert s["min"] == 1.0 and s["max"] == 3.0
    assert len(s["bin_edges"]) == len(s["bin_counts"]) + 1
    assert sum(s["bin_counts"]) == 3

    assert _summary(pd.Series([], dtype=float)) == {"n": 0}
