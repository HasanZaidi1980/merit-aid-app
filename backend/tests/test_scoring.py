"""Scoring and flag-handling tests.

The point of these is the RISK_FLAGS / DATA_GAPS split: `exclude_flagged` must drop
colleges whose *ranking* is untrustworthy and keep ones that are merely missing a
display field. Every fixture here is built in memory, so the suite does not depend on
the generated sample data (which has no missing values at all and therefore exercises
none of this).
"""
import numpy as np
import pandas as pd
import pytest

from app.scoring import add_metrics, rank_and_filter

COA_PARTS = ["TUITION2", "CHG4AY3", "CHG5AY3"]

# A college with nothing wrong with it. Each fixture row overrides one field.
HEALTHY = dict(TUITION2=30000.0, CHG4AY3=12000.0, CHG5AY3=1200.0, IGRNT_A=15000.0,
               NET_PRICE_MID=18000.0, GRAD_RATE=0.70, ADMISSIONS_RATE=0.55,
               SATVR75=600.0, SATMT75=620.0)


def _build(rows: list[dict]) -> pd.DataFrame:
    """Assemble a frame the way data.build_dataset() does, then add metrics.

    COA and COA_COMPLETE have to be derived here rather than left to add_metrics,
    because that is where data.py computes them -- a frame that skipped that step
    would fall back to the not-null check and never report an incomplete sticker.
    """
    df = pd.DataFrame(rows)
    df["UNITID"] = range(1, len(df) + 1)
    df["COA"] = df[COA_PARTS].sum(axis=1, min_count=1)
    df["COA_COMPLETE"] = df[COA_PARTS].notna().all(axis=1)
    df["SAT_TOTAL_75"] = df["SATVR75"] + df["SATMT75"]
    return add_metrics(df)


@pytest.fixture
def one_per_failure_mode() -> pd.DataFrame:
    """Five colleges: one clean, one per way a row can be deficient."""
    return _build([
        {**HEALTHY, "INSTNM": "Clean"},
        {**HEALTHY, "INSTNM": "NoSAT", "SATVR75": np.nan, "SATMT75": np.nan},
        {**HEALTHY, "INSTNM": "NoAdmit", "ADMISSIONS_RATE": np.nan},
        # Reports tuition but no room/board or books: COA is a partial sum, so its
        # Discount and Aid Share are measured against an understated sticker.
        {**HEALTHY, "INSTNM": "PartialCOA", "CHG4AY3": np.nan, "CHG5AY3": np.nan},
        {**HEALTHY, "INSTNM": "NoGradRate", "GRAD_RATE": np.nan},
    ])


def _shortlist(df, **overrides) -> list[str]:
    kwargs = dict(max_net_price=25000, mgi_at_least_median=False, top_n=50,
                  exclude_flagged=True)
    kwargs.update(overrides)
    return list(rank_and_filter(df, **kwargs)["INSTNM"])


def test_flags_land_in_the_right_column(one_per_failure_mode):
    """Scoring problems go to RISK_FLAGS, display-only gaps to DATA_GAPS."""
    f = one_per_failure_mode.set_index("INSTNM")

    assert f.loc["Clean", "RISK_FLAGS"] == ""
    assert f.loc["Clean", "DATA_GAPS"] == ""

    # Missing SAT / admit rate feed no metric, so they must not be risk flags.
    assert f.loc["NoSAT", "DATA_GAPS"] == "no_sat"
    assert f.loc["NoSAT", "RISK_FLAGS"] == ""
    assert f.loc["NoAdmit", "DATA_GAPS"] == "no_admit_rate"
    assert f.loc["NoAdmit", "RISK_FLAGS"] == ""

    # A partially reconstructed sticker distorts the money comparison.
    assert f.loc["PartialCOA", "COA_COMPLETE"] is np.False_
    assert f.loc["PartialCOA", "RISK_FLAGS"] == "incomplete_coa"

    # No grad rate means no Value Score at all.
    assert f.loc["NoGradRate", "RISK_FLAGS"] == "no_grad_rate"
    assert pd.isna(f.loc["NoGradRate", "VALUE_SCORE"])


def test_exclude_flagged_keeps_display_only_gaps(one_per_failure_mode):
    """The default view must not discard colleges over a missing SAT figure."""
    shortlist = _shortlist(one_per_failure_mode, exclude_flagged=True)

    assert "NoSAT" in shortlist
    assert "NoAdmit" in shortlist
    assert "PartialCOA" not in shortlist


def test_exclude_flagged_off_restores_partial_coa_but_not_unscoreable(one_per_failure_mode):
    """Turning the filter off is not a licence to rank a college with no score."""
    shortlist = _shortlist(one_per_failure_mode, exclude_flagged=False)

    assert "PartialCOA" in shortlist
    # Unscoreable rows are dropped unconditionally -- never ranked last, never imputed.
    assert "NoGradRate" not in shortlist


def test_exclude_flagged_changes_the_result_set(one_per_failure_mode):
    """Regression guard: the toggle must still do something.

    When no_sat / no_admit_rate were risk flags and COA_COMPLETE was always true,
    this toggle was a no-op on any row that survived the unscoreable drop -- a UI
    control that silently did nothing.
    """
    assert (_shortlist(one_per_failure_mode, exclude_flagged=True)
            != _shortlist(one_per_failure_mode, exclude_flagged=False))


def test_partial_coa_outranks_a_clean_college(one_per_failure_mode):
    """Why the default matters: an understated sticker inflates the Value Score.

    PartialCOA is identical to Clean except for the missing charge components, which
    shrink its COA, inflate AID_SHARE (grant / COA) and lift its generosity
    percentile. Left in, it ranks first on a flattering artefact of missing data.
    """
    f = one_per_failure_mode.set_index("INSTNM")
    assert f.loc["PartialCOA", "AID_SHARE"] > f.loc["Clean", "AID_SHARE"]
    assert f.loc["PartialCOA", "VALUE_SCORE"] > f.loc["Clean", "VALUE_SCORE"]
    assert _shortlist(one_per_failure_mode, exclude_flagged=False)[0] == "PartialCOA"


def test_no_grad_rate_never_reaches_the_output(one_per_failure_mode):
    """`no_grad_rate` is real in /api/meta's counts but unreachable in a ranked row.

    rank_and_filter drops unscoreable rows before the flag filter, so in practice
    `exclude_flagged` is gated by `incomplete_coa` alone. Documented here so the
    contract's "drops exactly these rows" is not read as implying otherwise.
    """
    for flagged in (True, False):
        returned = rank_and_filter(one_per_failure_mode, 25000, False, 50, flagged)
        assert not any("no_grad_rate" in flags for flags in returned["RISK_FLAGS"])


def test_mgi_median_is_dataset_wide_not_post_filter():
    """The threshold must not move when the user drags the net-price slider.

    Cheap colleges are usually the generous ones, so a median taken after the
    net-price filter sits well above "more generous than a typical 4-year college",
    which is what this filter claims to mean.
    """
    # Same sticker throughout; MGI varies only via the grant. The two affordable
    # colleges are the generous ones, so the post-filter median (0.75) is far above
    # the dataset median (0.45).
    df = _build([
        {**HEALTHY, "INSTNM": "CheapGenerous", "TUITION2": 10000.0, "CHG4AY3": 40000.0,
         "IGRNT_A": 8000.0, "NET_PRICE_MID": 10000.0},
        {**HEALTHY, "INSTNM": "CheapGeneroustoo", "TUITION2": 10000.0, "CHG4AY3": 40000.0,
         "IGRNT_A": 7000.0, "NET_PRICE_MID": 12000.0},
        {**HEALTHY, "INSTNM": "DearStingy", "TUITION2": 10000.0, "CHG4AY3": 40000.0,
         "IGRNT_A": 2000.0, "NET_PRICE_MID": 40000.0},
        {**HEALTHY, "INSTNM": "DearStingytoo", "TUITION2": 10000.0, "CHG4AY3": 40000.0,
         "IGRNT_A": 1000.0, "NET_PRICE_MID": 45000.0},
    ])
    assert df["MGI"].median() == pytest.approx(0.45)

    kept = _shortlist(df, mgi_at_least_median=True)
    # Both affordable colleges clear the dataset median. Against the post-filter
    # median only the single most generous one would survive.
    assert kept == ["CheapGenerous", "CheapGeneroustoo"]


def test_api_row_schema_exposes_data_gaps():
    """The contract is 24 fields now; DATA_GAPS is additive, nothing was removed."""
    from app.main import ROW_FIELDS

    assert len(ROW_FIELDS) == 24
    assert "DATA_GAPS" in ROW_FIELDS
    assert "RISK_FLAGS" in ROW_FIELDS
