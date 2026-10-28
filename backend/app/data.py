"""Load + clean the 8 IPEDS CSVs and merge them into one analysis table."""
import os
import functools
import numpy as np
import pandas as pd

from . import config
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

    sfa1 = _clean_missing(_read("sfa_p1"), ["IGRNT_A"])[["UNITID", "IGRNT_A"]]
    sfa2 = _clean_missing(_read("sfa_p2"), ["NPT442"])[["UNITID", "NPT442"]] \
        .rename(columns={"NPT442": "NET_PRICE_MID"})
    ic = _clean_missing(_read("ic_ay"), ["TUITION2", "CHG4AY3", "CHG5AY3", "CHG6AY3", "CHG7AY3"])
    # Build COA (cost of attendance) if the component columns exist.
    coa_parts = [c for c in ["TUITION2", "CHG4AY3", "CHG5AY3"] if c in ic.columns]
    ic_cols = ["UNITID", "TUITION2"]
    if coa_parts:
        # min_count=1 keeps a partial sum rather than NaN, so a college reporting
        # tuition but no room/board still gets a COA -- an understated one. Record
        # whether every component was actually present so that case can be flagged
        # instead of silently passing as a complete sticker.
        ic["COA"] = ic[coa_parts].sum(axis=1, min_count=1)
        ic["COA_COMPLETE"] = ic[coa_parts].notna().all(axis=1)
        ic_cols += ["COA", "COA_COMPLETE"]
    ic = ic[ic_cols]

    adm = _clean_missing(_read("adm"), ["SATVR75", "SATMT75"])[["UNITID", "SATVR75", "SATMT75"]]
    drvadm = _clean_missing(_read("drvadm"), ["DVADM01"])[["UNITID", "DVADM01"]] \
        .rename(columns={"DVADM01": "ADMISSIONS_RATE"})
    drvgr = _clean_missing(_read("drvgr"), ["GBA4RTT"])[["UNITID", "GBA4RTT"]] \
        .rename(columns={"GBA4RTT": "GRAD_RATE"})

    df = hd
    for other in [sfa1, sfa2, ic, adm, drvadm, drvgr]:
        df = df.merge(other, on="UNITID", how="left")

    if "COA" not in df.columns:
        df["COA"] = df["TUITION2"]
        df["COA_COMPLETE"] = df["COA"].notna()

    # SAT 75th total; percentages -> 0..1 scale.
    df["SAT_TOTAL_75"] = df["SATVR75"] + df["SATMT75"]
    for c in ["ADMISSIONS_RATE", "GRAD_RATE"]:
        if df[c].max(skipna=True) and df[c].max(skipna=True) > 1.5:
            df[c] = df[c] / 100.0

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
        "defaults": config.DEFAULTS,
        "dimensions": [
            {"key": "sticker", "label": "Total Sticker (COA)", "column": "COA",
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
