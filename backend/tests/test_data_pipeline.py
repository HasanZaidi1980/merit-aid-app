"""The real read path: load, merge, clean, sentinels, drops, empty results.

Why this file exists. Before Phase 6 every test in this suite built its frame in
memory and called `add_metrics` directly, so `data.py` -- the code that reads the six
CSVs off disk, filters the universe, coalesces the public/private column pairs,
converts sentinels, reconstructs COA and decides which colleges are dropped -- never
ran under test at all. It is the code that produced every number the app displays,
and it was the least covered thing in the project.

These tests run it against `tests/fixtures/ipeds_synthetic/`: 13 invented
institutions, each present to make one path run. The fixture is unmistakably fake and
is never the app's data -- see `tests/fixtures/README.md`.

The checks are modelled on the ones that caught real defects here (CLAUDE.md §1):
impossible values, who is actually in the rows, and reproducing a known number.
"""
import os

import numpy as np
import pandas as pd
import pytest

from app import config, data
from app.data import DatasetUnavailable, load_rates

# Paths spelled out here rather than imported from conftest: a test module that
# depends on pytest's import mode to find a helper is a test that breaks when the
# runner is invoked from a different directory.
FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")
SYNTHETIC = os.path.join(FIXTURES, "ipeds_synthetic")
ALL_DROPPED = os.path.join(FIXTURES, "ipeds_all_dropped")

# Every institution in the fixture, by the path it exists to exercise.
HEALTHY_PRIVATE, HEALTHY_PUBLIC = 999001, 999002
SENTINELS, NO_GRAD_RATE = 999003, 999004
NO_TUITION, TWO_YEAR, NON_DEGREE = 999005, 999006, 999007
ABSENT_FROM_SFA, GRANT_OVER_COST = 999008, 999009
NO_BAND_GRANT, FOR_PROFIT, UNCLASSIFIED = 999010, 999011, 999012
SUPPRESSED_GRANT = 999013

SURVIVES = {HEALTHY_PRIVATE, HEALTHY_PUBLIC, SENTINELS, NO_GRAD_RATE,
            GRANT_OVER_COST, NO_BAND_GRANT, FOR_PROFIT, UNCLASSIFIED}
DROPPED = {NO_TUITION: "no tuition reported",
           TWO_YEAR: "ICLEVEL=2, not a 4-year institution",
           NON_DEGREE: "HDEGOFR1=1, not degree-granting",
           ABSENT_FROM_SFA: "no row in SFA2122, so no grant or net price",
           SUPPRESSED_GRANT: "IGRNT_A is the -2 sentinel, not a value"}


def test_the_read_path_loads_merges_and_filters(synthetic):
    """Eight of thirteen survive, and the survivors are the expected eight."""
    assert set(synthetic["UNITID"]) == SURVIVES
    assert len(synthetic) == 8

    # The merge must bring every file's column across, not silently lose one.
    for col in ["INSTNM", "STABBR", "CONTROL_LABEL", "TUITION2", "IGRNT_A",
                "NET_PRICE_MID", "BAND_GRANT", "COA", "SAT_TOTAL_75",
                "ADMISSIONS_RATE", "GRAD_RATE", "VALUE_SCORE"]:
        assert col in synthetic.columns, col

    # One row per institution. A many-to-many merge on a duplicated UNITID would
    # multiply rows and inflate every count the app reports.
    assert synthetic["UNITID"].is_unique


@pytest.mark.parametrize("unitid,reason", sorted(DROPPED.items()))
def test_each_dropped_institution_is_dropped_for_its_stated_reason(synthetic, unitid, reason):
    """A row with no financial basis is excluded, never imputed (CLAUDE.md §2)."""
    assert unitid not in set(synthetic["UNITID"]), reason


def test_sentinels_become_missing_rather_than_values(synthetic):
    """IPEDS writes -1/-2/-3/-9 for "not applicable". Left numeric they would score.

    -2 on a graduation rate would pass through load_rates as -0.02 and rank as a
    real, very bad college rather than as an absent measurement.
    """
    f = synthetic.set_index("UNITID")

    assert pd.isna(f.loc[SENTINELS, "SATVR75"])
    assert pd.isna(f.loc[SENTINELS, "SAT_TOTAL_75"])
    assert pd.isna(f.loc[SENTINELS, "ADMISSIONS_RATE"])
    assert f.loc[SENTINELS, "DATA_GAPS"] == "no_sat,no_admit_rate"

    assert pd.isna(f.loc[NO_BAND_GRANT, "GRAD_RATE"])   # -2, not -0.02
    assert "no_grad_rate" in f.loc[NO_BAND_GRANT, "RISK_FLAGS"]

    # And a sentinel in a column the row cannot be analysed without drops the row
    # outright instead of scoring a negative grant.
    assert SUPPRESSED_GRANT not in set(synthetic["UNITID"])


def test_the_public_private_column_pairs_coalesce(synthetic):
    """The defect this guards is the one that cost the most here: reading NPT442
    alone looked universal and covered private institutions only, silently dropping
    all 726 public universities from an app about affordability."""
    f = synthetic.set_index("UNITID")

    # Private: NPT442 / GRN4A42.
    assert f.loc[HEALTHY_PRIVATE, "NET_PRICE_MID"] == 19000
    assert f.loc[HEALTHY_PRIVATE, "BAND_GRANT"] == 21000
    # Public, in-state: NPIS442 / GIS4A42. Present at all only because of the coalesce.
    assert f.loc[HEALTHY_PUBLIC, "NET_PRICE_MID"] == 14000
    assert f.loc[HEALTHY_PUBLIC, "BAND_GRANT"] == 9000
    assert f.loc[HEALTHY_PUBLIC, "CONTROL_LABEL"] == "Public"
    assert (synthetic["CONTROL_LABEL"] == "Public").sum() == 1


def test_coa_is_the_identity_ipeds_nets_against(synthetic):
    """COA = net price + that cohort's published average grant, exactly.

    Phase 3's finding. Also the impossible-value check from CLAUDE.md §1: a college
    can never cost less than its own net price, and the old hand-summed sticker put
    459 of 1,907 colleges in that state.
    """
    complete = synthetic[synthetic["COA_COMPLETE"]]
    assert len(complete) == 7

    identity = complete["NET_PRICE_MID"] + complete["BAND_GRANT"]
    assert np.allclose(complete["COA"], identity)
    assert (complete["COA"] >= complete["NET_PRICE_MID"]).all()
    assert (complete["DISCOUNT"] >= 0).all()

    # No band grant means no recoverable sticker. Not estimated -- flagged.
    f = synthetic.set_index("UNITID")
    assert pd.isna(f.loc[NO_BAND_GRANT, "COA"])
    assert f.loc[NO_BAND_GRANT, "COA_COMPLETE"] == False  # noqa: E712 (numpy bool)
    assert "incomplete_coa" in f.loc[NO_BAND_GRANT, "RISK_FLAGS"]


def test_rate_columns_are_scaled_by_declaration(synthetic):
    """0-100 in the file, 0..1 in the frame, per config.RATE_COLUMNS."""
    f = synthetic.set_index("UNITID")
    assert f.loc[HEALTHY_PRIVATE, "GRAD_RATE"] == pytest.approx(0.68)
    assert f.loc[HEALTHY_PRIVATE, "ADMISSIONS_RATE"] == pytest.approx(0.55)

    for col in ["GRAD_RATE", "ADMISSIONS_RATE"]:
        vals = synthetic[col].dropna()
        assert vals.between(0, 1).all(), col


def test_a_file_that_stops_matching_its_declaration_fails_loudly():
    """load_rates verifies its own result. A source file that switches scale must
    raise rather than score every college wrong by 100x.

    This is the check that replaced a `max > 1.5` heuristic -- which read the data to
    decide what the data meant, and would leave an all-small-rates subset unscaled
    with no error at all.
    """
    with pytest.raises(ValueError, match="GRAD_RATE"):
        load_rates(pd.DataFrame({"GRAD_RATE": [150.0], "ADMISSIONS_RATE": [50.0]}))


def test_an_undeclared_unit_is_a_bug_not_a_guess(monkeypatch):
    """Units come from each variable's dictionary entry. An unrecognised declaration
    is a mistake in the declaration, and guessing around it is how a rate column
    silently changes meaning."""
    monkeypatch.setitem(config.RATE_COLUMNS, "GRAD_RATE", "ratio")
    with pytest.raises(ValueError, match="unknown declared unit"):
        load_rates(pd.DataFrame({"GRAD_RATE": [0.5]}))


def test_flags_are_raised_from_real_files_not_just_in_memory_frames(synthetic):
    """The RISK_FLAGS / DATA_GAPS split, through the whole read path."""
    f = synthetic.set_index("UNITID")

    assert f.loc[HEALTHY_PRIVATE, "RISK_FLAGS"] == ""
    assert f.loc[HEALTHY_PRIVATE, "DATA_GAPS"] == ""
    assert f.loc[NO_GRAD_RATE, "RISK_FLAGS"] == "no_grad_rate"
    assert pd.isna(f.loc[NO_GRAD_RATE, "VALUE_SCORE"])

    # Average institutional grant above the whole cost of attendance is impossible
    # for one student: the two figures average different cohorts, so generosity is
    # unusable for that college and it is flagged rather than left to top the list.
    assert f.loc[GRANT_OVER_COST, "AID_SHARE"] > 1
    assert "aid_share_above_coa" in f.loc[GRANT_OVER_COST, "RISK_FLAGS"]

    # An unmapped CONTROL is labelled, not dropped or guessed.
    assert f.loc[UNCLASSIFIED, "CONTROL_LABEL"] == "Other"
    assert f.loc[FOR_PROFIT, "CONTROL_LABEL"] == "Private for-profit"


def test_meta_reproduces_the_fixtures_known_numbers(data_dir):
    """`meta()` is what the UI reports the dataset to be, so its arithmetic is
    checked against a frame small enough to count by hand -- the same method that
    proved the real load path correct by reproducing 1907 / 2200 / 63997 / 985."""
    data_dir(SYNTHETIC)
    m = data.meta()

    assert m["colleges_in_dataset"] == 8
    assert m["sat_coverage"] == 7                 # 999003's SAT is a -2 sentinel
    assert m["net_price_min"] == 3000             # 999009
    assert m["net_price_max"] == 22000            # 999010
    assert m["flagged_count"] == 3                # 999004, 999009, 999010
    assert m["data_gap_count"] == 1               # 999003
    assert m["unscoreable_count"] == 2            # 999004, 999010: no grad rate
    assert m["median_aid_share"] == 0.25
    assert m["median_mgi"] == 0.3874

    # The methodology travels with the numbers, on every deployment.
    assert "need-based and merit" in m["metric_notes"]["grant_aid"]
    assert sum(m["value_weights"].values()) == pytest.approx(1.0)


def test_a_missing_file_names_the_file_and_the_directory(data_dir, tmp_path):
    """The failure a deploy actually hits: DATA_DIR exists and is empty."""
    data_dir(tmp_path)
    with pytest.raises(DatasetUnavailable) as e:
        data.build_dataset()

    assert "HD2022.csv" in str(e.value)
    assert str(tmp_path) in str(e.value)


def test_an_empty_dataset_fails_loudly_instead_of_emptily(data_dir):
    """Files found, no usable rows -- wrong release, renamed columns, placeholders.

    This used to surface from np.nanmin inside meta() as "zero-size array to
    reduction operation minimum which has no identity", which names neither the cause
    nor the directory. An empty dataset is never a legitimate state for this app.
    """
    data_dir(ALL_DROPPED)
    with pytest.raises(DatasetUnavailable) as e:
        data.build_dataset()

    msg = str(e.value)
    assert ALL_DROPPED in msg
    assert "2 institutions survived" in msg
    assert "TUITION2" in msg and "IGRNT_A" in msg


def test_synthetic_institutions_are_never_given_a_merit_verdict(synthetic):
    """Fixture UNITIDs match nothing on the CDS roster, so every row must come out
    unchecked. Attaching a real institution's published aid policy to an invented
    college would be worse than leaving the column dark."""
    assert set(synthetic["MERIT_POLICY"]) == {"unknown"}
    assert set(synthetic["MERIT_POLICY_STATUS"]) == {"not_checked"}
    assert set(synthetic["MERIT_POLICY_YEAR"]) == {""}


def test_the_fixtures_are_never_the_app_default():
    """Test input, not a fallback. If a broken deployment could quietly serve these
    rows, the app would be presenting invented colleges as IPEDS findings."""
    default = os.path.realpath(os.path.join(os.path.dirname(data.__file__), "..", "data"))
    assert os.path.realpath(SYNTHETIC) != default
    assert "fixtures" not in os.path.realpath(config.DATA_DIR)

    # And the data announces itself, so a stray screenshot cannot be mistaken for real.
    hd = pd.read_csv(os.path.join(SYNTHETIC, "HD2022.csv"), encoding="latin-1")
    assert len(hd) == 13
    assert hd["INSTNM"].str.startswith("ZZ SYNTHETIC").all()
    assert (hd["UNITID"] >= 999000).all()
