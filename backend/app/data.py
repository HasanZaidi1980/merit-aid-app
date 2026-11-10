"""Load + clean the 8 IPEDS CSVs and merge them into one analysis table."""
import os
import functools
import numpy as np
import pandas as pd

from . import config
from . import scoring
from .scoring import add_metrics


def _read(name: str) -> pd.DataFrame:
    path = os.path.join(config.DATA_DIR, config.FILES[name])
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Missing IPEDS file: {config.FILES[name]} in {config.DATA_DIR}. "
            f"Run scripts/make_sample_data.py for a demo, or add the real files."
        )
    # IPEDS files are latin-1; UNITID is the join key everywhere.
    return pd.read_csv(path, encoding="latin-1", low_memory=False)


def _clean_missing(df: pd.DataFrame, cols) -> pd.DataFrame:
    for c in cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
            df[c] = df[c].replace(config.MISSING_SENTINELS, np.nan)
    return df


def net_price(sfa: pd.DataFrame) -> pd.Series:
    """Average net price for the $75k-$110k band, across the whole universe.

    IPEDS splits this into two mutually exclusive variables that share an identical
    dictionary title, so the distinction is invisible unless you check which rows
    carry a value:

        NPT442   private institutions (CONTROL 2, 3)
        NPIS442  public institutions, in-state (CONTROL 1)

    Reading NPT442 alone silently drops every public university -- 726 of 1907 in
    IPEDS 2022-23, for a tool whose whole subject is affordability. Coalescing the
    two reproduces the reference app's `colleges_in_dataset` (1907) and
    `sat_coverage` (985) exactly.

    They should never both be populated for one institution; NPT442 wins if they are.
    """
    price = sfa["NPT442"] if "NPT442" in sfa.columns else pd.Series(np.nan, index=sfa.index)
    if "NPIS442" in sfa.columns:
        price = price.combine_first(sfa["NPIS442"])
    return price


def band_grant(sfa: pd.DataFrame) -> pd.Series:
    """Average grant+scholarship aid for the same $75k-$110k Title IV cohort as net price.

    Split across two mutually exclusive variables on exactly the same public/private
    lines as NPIS442/NPT442, so it coalesces the same way:

        GRN4A42  private institutions
        GIS4A42  public institutions, in-state

    Verified on IPEDS 2022-23: never both populated (0 of 1907), 726 publics carry
    GIS4A42 and 1181 privates carry GRN4A42 -- the identical 726/1181 split as the
    net-price pair -- and neither ever appears without its matching net-price column.

    This is what makes COA reconstructible; see build_dataset().
    """
    grant = sfa["GRN4A42"] if "GRN4A42" in sfa.columns else pd.Series(np.nan, index=sfa.index)
    if "GIS4A42" in sfa.columns:
        grant = grant.combine_first(sfa["GIS4A42"])
    return grant


def load_rates(df: pd.DataFrame) -> pd.DataFrame:
    """Convert declared-percent rate columns to 0..1, then verify the result.

    config.RATE_COLUMNS declares each column's unit from its IPEDS dictionary entry
    instead of inferring it from the values. The old `max > 1.5` test read the data to
    decide what the data meant, which fails silently on any subset whose rates all
    happen to be small.
    """
    for col, unit in config.RATE_COLUMNS.items():
        if col not in df.columns:
            continue
        if unit == "percent":
            df[col] = df[col] / 100.0
        elif unit != "fraction":
            raise ValueError(f"{col}: unknown declared unit {unit!r}")
        vals = df[col].dropna()
        if len(vals) and (vals.min() < 0 or vals.max() > 1):
            raise ValueError(
                f"{col} declared {unit!r} but lands outside 0..1 after conversion "
                f"(min={vals.min()}, max={vals.max()}). The source file's scale "
                f"changed -- fix the declaration in config.RATE_COLUMNS."
            )
    return df


@functools.lru_cache(maxsize=1)
def build_dataset() -> pd.DataFrame:
    """Merge + clean + add metrics. Cached so it loads once per process."""
    hd = _read("hd")
    hd.columns = [c.upper() for c in hd.columns]
    # 4-year, degree-granting only.
    for c in ["ICLEVEL", "HDEGOFR1"]:
        if c in hd.columns:
            hd[c] = pd.to_numeric(hd[c], errors="coerce")
    hd = hd[(hd.get("ICLEVEL") == 1) & (hd.get("HDEGOFR1") >= 3)]
    hd = hd[["UNITID", "INSTNM", "STABBR", "CONTROL"]].copy()
    hd["CONTROL_LABEL"] = hd["CONTROL"].map({1: "Public", 2: "Private nonprofit",
                                             3: "Private for-profit"}).fillna("Other")

    sfa = _clean_missing(_read("sfa"), ["IGRNT_A", "NPT442", "NPIS442", "GRN4A42", "GIS4A42"])
    sfa = sfa.assign(NET_PRICE_MID=net_price(sfa), BAND_GRANT=band_grant(sfa))
    sfa = sfa[["UNITID", "IGRNT_A", "NET_PRICE_MID", "BAND_GRANT"]]
    ic = _clean_missing(_read("ic_ay"), ["TUITION2"])[["UNITID", "TUITION2"]]

    adm = _clean_missing(_read("adm"), ["SATVR75", "SATMT75"])[["UNITID", "SATVR75", "SATMT75"]]
    drvadm = _clean_missing(_read("drvadm"), ["DVADM01"])[["UNITID", "DVADM01"]] \
        .rename(columns={"DVADM01": "ADMISSIONS_RATE"})
    drvgr = _clean_missing(_read("drvgr"), ["GBA4RTT"])[["UNITID", "GBA4RTT"]] \
        .rename(columns={"GBA4RTT": "GRAD_RATE"})

    df = hd
    for other in [sfa, ic, adm, drvadm, drvgr]:
        df = df.merge(other, on="UNITID", how="left")

    # --- COA: the cost basket IPEDS actually netted against ---------------------
    # Not hand-summed from charge columns any more. IPEDS defines net price as
    #
    #     net price = total cost of attendance - average grant and scholarship aid
    #
    # for one cohort (full-time first-time Title IV recipients, income $75k-$110k,
    # 2021-22), so the COA that net price was computed against is recoverable by
    # adding the published average grant for that same cohort straight back on.
    #
    # Verified two ways on the real 1907:
    #   * against an independent reconstruction from the 2021-22 charge columns
    #     weighted by living arrangement (the formula the dictionary spells out) --
    #     the two agree to under $1 on 1543 of 1544 institutions, median diff $0;
    #   * no college can land below its own net price, where the old hand-summed COA
    #     put 459 of 1907 (24%) at a negative discount, which is impossible.
    #
    # The hand-summed version understated cost two ways: TUITION2 is tuition with no
    # required fees, and it omitted on-campus other expenses entirely. It also mixed
    # 2022-23 charges against a 2021-22 net price. This matches both year and basket.
    df["COA"] = df["NET_PRICE_MID"] + df["BAND_GRANT"]
    df["COA_COMPLETE"] = df["NET_PRICE_MID"].notna() & df["BAND_GRANT"].notna()

    # SAT 75th total; rate columns scaled by declaration, not by inspection.
    df["SAT_TOTAL_75"] = df["SATVR75"] + df["SATMT75"]
    df = load_rates(df)

    # Drop rows with no financial basis to analyze.
    df = df.dropna(subset=["TUITION2", "IGRNT_A", "NET_PRICE_MID"], how="any")

    df = add_metrics(df)
    return df.reset_index(drop=True)


@functools.lru_cache(maxsize=1)
def load_missions() -> pd.DataFrame:
    m = _read("mission")
    m.columns = [c.lower() for c in m.columns]
    m = m.rename(columns={"unitid": "UNITID"})
    text_col = "mission" if "mission" in m.columns else m.columns[-1]
    m = m[["UNITID", text_col]].rename(columns={text_col: "mission"})
    m = m.dropna(subset=["mission"])
    return m.reset_index(drop=True)


def meta() -> dict:
    df = build_dataset()
    flagged = (df["RISK_FLAGS"] != "").sum()
    gaps = (df["DATA_GAPS"] != "").sum()
    return {
        "colleges_in_dataset": int(len(df)),
        "median_aid_share": round(float(df["AID_SHARE"].median()), 4),
        # The threshold `mgi_at_least_median` actually applies. Reported so the UI
        # can show the real number instead of median_aid_share, which is a different
        # ratio (grant / COA rather than grant / tuition).
        "median_mgi": round(float(df["MGI"].median()), 4),
        "net_price_min": int(np.nanmin(df["NET_PRICE_MID"])),
        "net_price_max": int(np.nanmax(df["NET_PRICE_MID"])),
        # Scoring-relevant problems only; `exclude_flagged` drops exactly these.
        "flagged_count": int(flagged),
        # Display-only gaps (no SAT / no admit rate). These never drop a college.
        "data_gap_count": int(gaps),
        # Colleges with no Value Score at all; excluded from every ranking.
        "unscoreable_count": int(df["VALUE_SCORE"].isna().sum()),
        "sat_coverage": int(df["SAT_TOTAL_75"].notna().sum()),
        # Colleges on the curated need-only list that survive the pipeline. Shown so
        # the UI can state the coverage of that list rather than imply it is complete.
        "no_merit_aid_count": int((df["MERIT_POLICY"] == "need_only").sum()),
        # What the generosity metrics actually measure. Surfaced through the API so
        # the correction travels with the data instead of living only in UI copy.
        "metric_notes": {
            "grant_aid": (
                "IGRNT_A is total institutional grant aid — need-based and merit "
                "awards combined. IPEDS publishes no split, so MGI and Aid Share "
                "measure generosity, not merit."
            ),
            "cost_of_attendance": (
                "COA is the cost basket IPEDS itself netted against: the published "
                "average grant for the $75k-$110k Title IV cohort added back to that "
                "cohort's net price (2021-22). It is NOT a hand-summed sticker, and "
                "runs about 6% under the on-campus published price because IPEDS "
                "weights room/board across living arrangements. DISCOUNT is therefore "
                "identically that published grant figure."
            ),
            "merit_policy": (
                "MERIT_POLICY is 'need_only' for colleges on a curated list of "
                "institutions that publicly award no merit scholarships, and "
                "'unknown' otherwise. Unknown means unchecked."
            ),
        },
        # The Value Score weighting actually in force, normalised. Reported so the
        # methodology is auditable from the API rather than implicit in the code.
        "value_weights": scoring.value_weights(),
        "defaults": config.DEFAULTS,
        "dimensions": [
            {"key": "sticker", "label": "Total Cost of Attendance", "column": "COA",
             "required_for": ["Aid Share", "Discount"]},
            {"key": "grant", "label": "Avg Institutional Grant", "column": "IGRNT_A",
             "required_for": ["Aid Share", "Value Score"]},
            {"key": "net_price", "label": "Net Price", "column": "NET_PRICE_MID",
             "required_for": ["Value Score", "Discount"]},
            {"key": "admit_rate", "label": "Admissions Rate", "column": "ADMISSIONS_RATE",
             "required_for": ["Trade-offs chart"]},
            {"key": "grad_rate", "label": "Graduation Rate", "column": "GRAD_RATE",
             "required_for": ["Value Score"]},
            {"key": "sat", "label": "SAT 75th", "column": "SAT_TOTAL_75",
             "required_for": ["Trade-offs chart"]},
        ],
    }
