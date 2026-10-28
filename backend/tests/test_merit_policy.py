"""Merit-aid policy flagging.

The app is named for merit aid but IGRNT_A conflates need-based and merit grants,
and IPEDS publishes no split. The curated need-only list is the partial fix; these
tests pin the two properties that make it honest rather than misleading:

  1. `unknown` must never read as a claim. The vocabulary has no value meaning
     "offers merit aid", because nothing in the pipeline could justify one.
  2. The flag must not touch any score. It is a fact about the college, not a
     measurement of it, so adding it cannot reshuffle the ranking.
"""
import numpy as np
import pandas as pd
import pytest

from app.merit_policy import NEED_ONLY, UNKNOWN, merit_policy, roster
from app.scoring import add_metrics, rank_and_filter

HARVARD, YALE, STANFORD = 166027, 130794, 243744
NOT_ON_LIST = 999001  # no such institution; stands in for "never checked"

HEALTHY = dict(TUITION2=30000.0, CHG4AY3=12000.0, CHG5AY3=1200.0, IGRNT_A=15000.0,
               NET_PRICE_MID=18000.0, GRAD_RATE=0.70, ADMISSIONS_RATE=0.55,
               SATVR75=600.0, SATMT75=620.0)
COA_PARTS = ["TUITION2", "CHG4AY3", "CHG5AY3"]


def _build(rows: list[dict]) -> pd.DataFrame:
    """Assemble a frame the way data.build_dataset() does. UNITID is explicit here,
    because that is the key the curated list matches on."""
    df = pd.DataFrame(rows)
    df["COA"] = df[COA_PARTS].sum(axis=1, min_count=1)
    df["COA_COMPLETE"] = df[COA_PARTS].notna().all(axis=1)
    df["SAT_TOTAL_75"] = df["SATVR75"] + df["SATMT75"]
    return add_metrics(df)


@pytest.fixture
def four_colleges() -> pd.DataFrame:
    """Three on the curated list, one not. Identical in every other respect, so any
    difference in score between them could only come from the flag."""
    return _build([
        {**HEALTHY, "UNITID": HARVARD, "INSTNM": "Harvard University"},
        {**HEALTHY, "UNITID": YALE, "INSTNM": "Yale University"},
        {**HEALTHY, "UNITID": STANFORD, "INSTNM": "Stanford University"},
        {**HEALTHY, "UNITID": NOT_ON_LIST, "INSTNM": "Unchecked College"},
    ])


def test_policy_keys_on_unitid_not_name():
    """Names carry legal suffixes that shift between releases; UNITIDs do not."""
    ids = pd.Series([HARVARD, NOT_ON_LIST, STANFORD])
    assert list(merit_policy(ids)) == [NEED_ONLY, UNKNOWN, NEED_ONLY]

    # A college renamed in a later IPEDS release must still be flagged.
    assert merit_policy(pd.Series([HARVARD])).iloc[0] == NEED_ONLY


def test_unknown_is_not_a_claim(four_colleges):
    """Absence from the list means unchecked, never "awards merit aid".

    This is the whole reason the column is a string and not a bool. 26 of 1,907
    colleges have been checked; a False on the other 1,881 would turn a known gap
    into an invented answer.
    """
    assert set(four_colleges["MERIT_POLICY"]) == {NEED_ONLY, UNKNOWN}
    # No third value exists that could be read as a positive finding.
    assert NEED_ONLY != UNKNOWN
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


def test_exclude_no_merit_drops_only_the_curated_list(four_colleges):
    kept = list(rank_and_filter(four_colleges, 25000, False, 50, True,
                                exclude_no_merit=True)["INSTNM"])
    assert kept == ["Unchecked College"]


def test_exclude_no_merit_defaults_off(four_colleges):
    """Opt-in by design: filtering by default would imply the rest were cleared."""
    from app import config

    assert config.DEFAULTS["exclude_no_merit"] is False
    # Positional call without the new argument -- the pre-existing call signature.
    assert len(rank_and_filter(four_colleges, 25000, False, 50, True)) == 4


def test_roster_is_internally_consistent():
    """Guards the one failure mode of a hand-maintained list: a duplicated row."""
    entries = roster()
    unitids = [e["unitid"] for e in entries]

    assert len(unitids) == len(set(unitids))
    assert all(isinstance(u, int) for u in unitids)
    # Every entry records why it is on the list, so a reader can check it.
    assert {e["basis"] for e in entries} <= {"ivy_agreement", "published"}
    assert all(e["name"] for e in entries)


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
