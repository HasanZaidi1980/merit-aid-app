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
  4. The year must reach the row. The UI claimed each label named its year while
     rendering no year at all, because cds_year never left this module.
  5. A verdict must expire. Yale answers H2A line n differently in three
     consecutive editions, so an old record is not evidence about today.
"""
import re

import numpy as np
import pandas as pd
import pytest

from app import merit_policy as mp
from app.merit_policy import (
    ATTEMPTED_UNRESOLVED,
    AWARDS_MERIT,
    CURRENT_EDITION,
    NEED_ONLY,
    NOT_CHECKED,
    RESOLVED,
    STALE_AFTER_EDITIONS,
    UNKNOWN,
    coverage,
    is_current,
    merit_policy,
    merit_policy_status,
    merit_policy_year,
    provenance,
    roster,
    unverified,
)
from app.scoring import add_metrics, rank_and_filter

# Yale and Haverford report zero on CDS H2A line n; Harvard and Stanford report more
# than zero. Harvard and Stanford were on the old need-only roster and were being
# mislabelled -- these constants are the regression guard for that.
YALE, HAVERFORD = 130794, 212911
HARVARD, STANFORD = 166027, 243744
MIT = 166683
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


def test_the_year_reaches_the_row():
    """Defect: the UI said "each label names the year it came from" and rendered no
    year, because cds_year never left merit_policy.py. A claim the user cannot date
    is a claim they have to take on trust."""
    ids = pd.Series([YALE, HARVARD, NOT_ON_LIST])
    years = merit_policy_year(ids)

    assert years.iloc[0] and years.iloc[1]
    for y in years.iloc[:2]:
        assert re.fullmatch(r"\d{4}-\d{2}", y), y
    # Unchecked carries no year -- not a blank that renders as one.
    assert years.iloc[2] == ""

    # And it has to survive the real pipeline, not just the helper.
    df = _build([{**HEALTHY, "UNITID": YALE, "INSTNM": "Yale University"}])
    assert df.loc[0, "MERIT_POLICY_YEAR"] == provenance(YALE)["cds_year"]


def test_every_reported_verdict_has_a_year_on_the_row(four_colleges):
    """Whatever carries a policy value must carry the edition behind it."""
    for _, r in four_colleges.iterrows():
        if r["MERIT_POLICY"] == UNKNOWN:
            assert r["MERIT_POLICY_YEAR"] == ""
        else:
            assert r["MERIT_POLICY_YEAR"], r["INSTNM"]


def test_status_separates_the_two_kinds_of_blank(four_colleges):
    """`unknown` has two causes and they must not read alike: we read the college's
    CDS and H2A was not in it, versus nobody looked. Collapsing them is how a
    coverage gap starts reading as a finding."""
    assert merit_policy_status(pd.Series([YALE])).iloc[0] == RESOLVED
    assert merit_policy_status(pd.Series([NOT_ON_LIST])).iloc[0] == NOT_CHECKED

    attempted = unverified()[0]["unitid"]
    assert merit_policy_status(pd.Series([attempted])).iloc[0] == ATTEMPTED_UNRESOLVED
    # Attempted-but-unresolved is still `unknown` as a policy. The status says how
    # hard we tried; it never upgrades to an answer.
    assert merit_policy(pd.Series([attempted])).iloc[0] == UNKNOWN

    assert set(four_colleges["MERIT_POLICY_STATUS"]) <= {
        RESOLVED, ATTEMPTED_UNRESOLVED, NOT_CHECKED}


def test_a_stale_verdict_expires_instead_of_standing():
    """Yale reads 6/28/1, 6/24/0 then 0/0/0 across three editions, so a verdict is
    point-in-time. Records outside the window must revert to `unknown` on their own
    -- nothing may age quietly into a current-sounding claim."""
    cur = int(CURRENT_EDITION[:4])

    assert is_current(CURRENT_EDITION)
    assert is_current(f"{cur - STALE_AFTER_EDITIONS}-{str(cur - STALE_AFTER_EDITIONS + 1)[2:]}")
    assert not is_current(f"{cur - STALE_AFTER_EDITIONS - 1}-00")
    assert not is_current("2019-20")          # the Colby case, now a rule

    # Nothing currently reported may already be outside the window.
    for e in roster():
        assert is_current(e["cds_year"]), e["name"]

    # And an expired record is reported as attempted, with the reason saying so.
    # Matched on the generated wording, not on the phrase "staleness window" alone --
    # Colby's hand-written reason says that too, and it is unresolved for a different
    # cause (it has only ever published a 2019-20 edition).
    stale = [u for u in unverified()
             if f"current edition {CURRENT_EDITION}" in u["reason"]]
    assert len(stale) == coverage()["stale"]


def test_mit_is_sourced_from_an_edition_that_actually_reports_zero():
    """Defect: MIT was labelled need_only citing line n = "N/App". Not-applicable is
    a non-answer, not a reported zero -- the same gap in reasoning that produced the
    five false labels. Verified directly: MIT's 2024-25 CDS does answer line n
    "N/App", while its 2025-26 edition reports an actual 0/0/0. The verdict stands
    only on the edition whose evidence supports it."""
    p = provenance(MIT)

    assert p["policy"] == NEED_ONLY
    assert p["cds_year"] == "2025-26"
    assert p["line_n"] == "0 / 0 / 0"
    # The non-answer must not reappear in the field the verdict rests on.
    assert "N/App" not in p["line_n"]


def test_no_verdict_rests_on_a_non_answer():
    """Generalises the MIT defect across the roster. "N/App", "NA", "n/a" and a
    blank are all refusals to answer; only a figure can carry a policy claim."""
    NON_ANSWERS = {"", "n/app", "na", "n/a", "not reported", "-", "--"}
    for e in roster():
        assert e["line_n"].strip().lower() not in NON_ANSWERS, e["name"]
        assert re.search(r"\d", e["line_n"]), e["name"]


def test_coverage_states_its_scope_and_its_skew():
    """A coverage number without its scope is the same mistake as a count without a
    denominator. The sourcing covers a shortlist of mostly wealthy privates, and the
    figure has to say so wherever it travels."""
    c = coverage()
    assert "top 50" in c["scope"]
    assert c["sector_caveat"] and "private" in c["sector_caveat"]
    assert c["current_edition"] == CURRENT_EDITION
    assert c["stale_after_editions"] == STALE_AFTER_EDITIONS


def _edition_label(start_year: int) -> str:
    """2027 -> '2027-28'. The CDS names an edition by the academic year it covers."""
    return f"{start_year}-{str(start_year + 1)[2:]}"


def test_expiry_fires_when_the_edition_advances(monkeypatch):
    """Cover the mechanism, not its current dormancy.

    Nothing on the roster is stale today, so every stale branch -- dropping a record
    from the roster, re-labelling it attempted, generating its reason -- is unreached
    code until a human bumps CURRENT_EDITION. That bump is exactly when a regression
    would ship, and the instinct at that moment is to edit whichever number went red.
    So the edition is injected here and the records are watched leaving.

    Counts are derived from the roster rather than written down, so this test does
    not have to be rewritten every time a record is added or a year moves on.
    """
    before = coverage()
    assert before["stale"] == 0, "nothing is stale yet -- that is what makes the rule dormant"

    oldest = min(int(e["cds_year"][:4]) for e in roster())
    future = _edition_label(oldest + STALE_AFTER_EDITIONS + 1)
    expiring = {e["unitid"] for e in roster()
                if int(e["cds_year"][:4]) == oldest}

    monkeypatch.setattr(mp, "CURRENT_EDITION", future)

    after = coverage()
    assert after["stale"] == len(expiring) >= 1
    assert after["verified"] == before["verified"] - len(expiring)
    # Attempting an institution does not un-happen. The denominator is stable; what
    # moves is how many of those attempts still count as answers.
    assert after["attempted"] == before["attempted"]
    assert after["unresolved"] == before["unresolved"] + len(expiring)
    assert after["current_edition"] == future

    victim = sorted(expiring)[0]
    # Reverts to `unknown` on its own -- no edit to the record, no list to maintain.
    assert mp.merit_policy(pd.Series([victim])).iloc[0] == UNKNOWN
    assert mp.merit_policy_year(pd.Series([victim])).iloc[0] == ""
    assert mp.merit_policy_status(pd.Series([victim])).iloc[0] == ATTEMPTED_UNRESOLVED
    assert provenance(victim) is None
    assert victim not in {e["unitid"] for e in roster()}

    # And it is reported as attempted, with the reason saying why it stopped counting.
    reasons = {u["unitid"]: u["reason"] for u in unverified()}
    assert "outside the staleness window" in reasons[victim]
    assert f"current edition {future}" in reasons[victim]

    # Nothing inside the window moved.
    for e in roster():
        assert is_current(e["cds_year"], future), e["name"]

    # Reversible, because expiry is a function of the edition and not a mutation of
    # state. A record that aged out comes back if the edition is corrected.
    monkeypatch.undo()
    assert coverage() == before
    assert provenance(victim) is not None


def test_a_count_that_must_be_asserted_freezes_the_edition(monkeypatch):
    """How to write a count assertion here without tying it to the calendar.

    Pin the edition, and the counts stop being a function of when the suite runs.
    This one holds the whole roster current, so it asserts the true totals: 24
    records read from a CDS, 5 of them reporting zero on H2A line n, 19 reporting
    more than zero, out of 56 institutions attempted.
    """
    newest = max(int(e["cds_year"][:4]) for e in roster())
    monkeypatch.setattr(mp, "CURRENT_EDITION", _edition_label(newest))

    c = coverage()
    assert c["verified"] == 24
    assert c["need_only"] == 5
    assert c["awards_merit"] == 19
    assert c["need_only"] + c["awards_merit"] == c["verified"]
    assert c["attempted"] == 56
    assert c["stale"] == 0

    # 24 of 56 attempted, not 24 of 1,907. The scope is part of the number.
    assert c["verified"] < c["attempted"]
    assert "not the 1,907-college dataset" in c["scope"]


def test_no_verdict_depends_on_the_clock():
    """The expiry rule must stay a function of a declared edition, never of today's
    date. A suite whose results change overnight teaches you to edit the number
    rather than ask what moved, and a verdict that expires on a Tuesday with no
    commit is not auditable."""
    import inspect

    src = inspect.getsource(mp)
    for forbidden in ["datetime", "time.time", "date.today", "utcnow"]:
        assert forbidden not in src, f"merit_policy reads {forbidden}"

    # Belt and braces: nothing clock-shaped was imported into the module either.
    clocks = {k for k, v in vars(mp).items()
              if getattr(v, "__name__", "") in {"datetime", "date", "time", "calendar"}}
    assert not clocks, clocks
