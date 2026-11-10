"""Phase 3: the COA basis, declared rate scales, and configurable Value Score weights.

The COA tests encode the *reason* the basis changed: net price is defined as a cost
basket minus a published grant figure, so adding that grant back recovers the basket
exactly. Anything that reintroduces a hand-summed sticker breaks these.
"""
import numpy as np
import pandas as pd
import pytest

from app import config, data, scoring


def _frame(**over):
    base = dict(
        UNITID=[1, 2, 3],
        INSTNM=["A", "B", "C"],
        NET_PRICE_MID=[10000.0, 20000.0, 30000.0],
        BAND_GRANT=[5000.0, 15000.0, 1000.0],
        IGRNT_A=[4000.0, 12000.0, 900.0],
        TUITION2=[9000.0, 25000.0, 20000.0],
        GRAD_RATE=[0.5, 0.8, 0.3],
        ADMISSIONS_RATE=[0.4, 0.2, 0.9],
        SAT_TOTAL_75=[1200.0, 1500.0, 1000.0],
    )
    base.update(over)
    df = pd.DataFrame(base)
    df["COA"] = df["NET_PRICE_MID"] + df["BAND_GRANT"]
    df["COA_COMPLETE"] = df["NET_PRICE_MID"].notna() & df["BAND_GRANT"].notna()
    return df


# --- Item 1: the COA basis -------------------------------------------------

def test_discount_can_never_be_negative():
    """The defect that motivated the change: 459 of 1907 colleges had net price
    above COA, which is impossible. Recovering COA from net price makes it
    unrepresentable rather than merely unlikely."""
    out = scoring.add_metrics(_frame())
    assert (out["DISCOUNT"] >= 0).all()


def test_discount_is_exactly_the_published_band_grant():
    out = scoring.add_metrics(_frame())
    pd.testing.assert_series_equal(
        out["DISCOUNT"], out["BAND_GRANT"], check_names=False)


def test_band_grant_coalesces_on_the_same_split_as_net_price():
    """GIS4A42 (public) and GRN4A42 (private) are mutually exclusive, exactly like
    NPIS442/NPT442. Verified on the real data: 726 publics, 1181 privates, 0 both."""
    sfa = pd.DataFrame({
        "GRN4A42": [np.nan, 8000.0, np.nan],
        "GIS4A42": [3000.0, np.nan, np.nan],
    })
    got = data.band_grant(sfa)
    assert got.tolist()[:2] == [3000.0, 8000.0]
    assert pd.isna(got.iloc[2])


def test_band_grant_survives_a_missing_column():
    assert data.band_grant(pd.DataFrame({"GIS4A42": [1.0]})).tolist() == [1.0]
    assert data.band_grant(pd.DataFrame({"GRN4A42": [2.0]})).tolist() == [2.0]


def test_aid_share_above_coa_is_flagged_not_ranked():
    """IGRNT_A averages a different cohort than COA, so it can exceed the whole cost
    of attendance -- true of one real college. Generosity is meaningless there."""
    out = scoring.add_metrics(_frame(IGRNT_A=[99000.0, 12000.0, 900.0]))
    assert "aid_share_above_coa" in out.loc[0, "RISK_FLAGS"]
    assert "aid_share_above_coa" not in out.loc[1, "RISK_FLAGS"]
    kept = scoring.rank_and_filter(out, max_net_price=None, mgi_at_least_median=False,
                                   top_n=0, exclude_flagged=True)
    assert 1 not in set(kept["UNITID"])


# --- Item 2: declared rate scales -----------------------------------------

def test_percent_columns_are_scaled_by_declaration():
    df = pd.DataFrame({"ADMISSIONS_RATE": [100.0, 50.0], "GRAD_RATE": [25.0, 75.0]})
    out = data.load_rates(df.copy())
    assert out["ADMISSIONS_RATE"].tolist() == [1.0, 0.5]
    assert out["GRAD_RATE"].tolist() == [0.25, 0.75]


def test_declaration_does_not_depend_on_the_observed_maximum():
    """The old heuristic divided by 100 only when max > 1.5, so a subset whose rates
    all happened to be small was silently left 100x too low. A declaration cannot
    read the data to decide what the data means."""
    small = pd.DataFrame({"ADMISSIONS_RATE": [1.0, 0.5], "GRAD_RATE": [1.2, 0.8]})
    out = data.load_rates(small.copy())
    assert out["ADMISSIONS_RATE"].tolist() == [0.01, 0.005]


def test_a_scale_that_contradicts_its_declaration_fails_loudly():
    bad = pd.DataFrame({"GRAD_RATE": [250.0]})       # 2.5 after conversion
    with pytest.raises(ValueError, match="outside 0..1"):
        data.load_rates(bad)


# --- Items 3 + 4: configurable weights ------------------------------------

def test_weights_default_to_equal_thirds():
    w = scoring.value_weights()
    assert set(w) == {"affordability", "graduation", "generosity"}
    assert all(abs(v - 1 / 3) < 1e-9 for v in w.values())


def test_weights_are_normalised_so_the_score_stays_on_0_100():
    orig = dict(config.VALUE_WEIGHTS)
    try:
        config.VALUE_WEIGHTS.update(affordability=2, graduation=1, generosity=1)
        assert abs(sum(scoring.value_weights().values()) - 1.0) < 1e-9
        out = scoring.add_metrics(_frame())
        assert out["VALUE_SCORE"].between(0, 100).all()
    finally:
        config.VALUE_WEIGHTS.clear()
        config.VALUE_WEIGHTS.update(orig)


def test_reweighting_actually_changes_the_ordering():
    orig = dict(config.VALUE_WEIGHTS)
    try:
        config.VALUE_WEIGHTS.update(affordability=1, graduation=0, generosity=0)
        aff_only = scoring.add_metrics(_frame())["VALUE_SCORE"].tolist()
        config.VALUE_WEIGHTS.update(affordability=0, graduation=1, generosity=0)
        grad_only = scoring.add_metrics(_frame())["VALUE_SCORE"].tolist()
        assert aff_only != grad_only
    finally:
        config.VALUE_WEIGHTS.clear()
        config.VALUE_WEIGHTS.update(orig)


def test_zero_total_weight_is_rejected():
    orig = dict(config.VALUE_WEIGHTS)
    try:
        config.VALUE_WEIGHTS.update(affordability=0, graduation=0, generosity=0)
        with pytest.raises(ValueError, match="sum to more than 0"):
            scoring.value_weights()
    finally:
        config.VALUE_WEIGHTS.clear()
        config.VALUE_WEIGHTS.update(orig)
