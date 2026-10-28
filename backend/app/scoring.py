"""Metric + score calculations. Kept separate so the formulas are easy to audit."""
import pandas as pd


def pct_rank(series: pd.Series, higher_is_better: bool = True) -> pd.Series:
    """Percentile rank 0..1. NaNs stay NaN."""
    r = series.rank(pct=True)
    return r if higher_is_better else (1.0 - r)


def add_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """Add every derived column the API returns. Input already merged + cleaned."""
    df = df.copy()

    # --- core money metrics ---
    # COA = total sticker (cost of attendance). Prefer a real COA; else build it.
    if "COA" not in df.columns:
        df["COA"] = df.get("TUITION2")
    # data.py sets COA_COMPLETE from how many charge components were actually
    # present. Fall back to a simple not-null check when a caller hands us a frame
    # that didn't go through that path (e.g. tests).
    if "COA_COMPLETE" not in df.columns:
        df["COA_COMPLETE"] = df["COA"].notna()

    # Discount = what the sticker hides vs what mid-income families actually pay.
    df["DISCOUNT"] = df["COA"] - df["NET_PRICE_MID"]

    # MGI (original assignment): grant / tuition sticker.
    df["MGI"] = df["IGRNT_A"] / df["TUITION2"]

    # Aid share: grant as a fraction of the FULL sticker (COA). Headline generosity.
    df["AID_SHARE"] = df["IGRNT_A"] / df["COA"]

    # Net price ratio: share of sticker a family still pays. Lower = better.
    df["NET_PRICE_RATIO"] = df["NET_PRICE_MID"] / df["COA"]

    # --- Value Score (0-100): mean of 3 equally-weighted percentile ranks ---
    affordability = pct_rank(df["NET_PRICE_MID"], higher_is_better=False)  # cheaper = better
    quality = pct_rank(df["GRAD_RATE"], higher_is_better=True)
    generosity = pct_rank(df["AID_SHARE"], higher_is_better=True)
    # Plain addition: NaN propagates on purpose. A college missing any component is
    # NOT scoreable, and rank_and_filter() drops it rather than ranking it last or
    # crediting it with imputed data. (The former `fill_value=NaN` was a no-op
    # that read as if it handled missing values.)
    df["VALUE_SCORE"] = (affordability + quality + generosity) / 3.0 * 100.0

    # --- Legacy composite (the original formula, kept for comparison) ---
    df["COMPOSITE_LEGACY"] = (df["MGI"] + df["GRAD_RATE"]) / df["NET_PRICE_RATIO"]

    # --- data-quality bookkeeping ---
    df["COMPONENTS_USED"] = df.apply(_components_used, axis=1)
    df["RISK_FLAGS"] = df.apply(_risk_flags, axis=1)
    df["DATA_GAPS"] = df.apply(_data_gaps, axis=1)

    return df


def _components_used(row) -> str:
    used = []
    for col, name in [("COA", "sticker"), ("IGRNT_A", "grant"),
                      ("NET_PRICE_MID", "net_price"), ("ADMISSIONS_RATE", "admit_rate"),
                      ("GRAD_RATE", "grad_rate"), ("SAT_TOTAL_75", "sat")]:
        if col in row and pd.notna(row[col]):
            used.append(name)
    return ",".join(used)


def _risk_flags(row) -> str:
    """Problems that make a college's ranking untrustworthy.

    Only fields that feed Value Score or the money comparison belong here, because
    `exclude_flagged` drops these rows. A missing field that merely leaves a chart
    sparse is a DATA_GAP, not a risk flag -- see _data_gaps().
    """
    flags = []
    if not row.get("COA_COMPLETE", True):
        # Sticker was reconstructed from only some of its charge components, so
        # DISCOUNT and AID_SHARE are measured against an understated total.
        flags.append("incomplete_coa")
    if pd.isna(row.get("GRAD_RATE")):
        flags.append("no_grad_rate")
    return ",".join(flags)


def _data_gaps(row) -> str:
    """Missing fields that affect display only.

    Neither SAT nor admissions rate enters Value Score, so their absence never
    removes a college from the ranking -- it just leaves gaps in the charts.
    """
    gaps = []
    if pd.isna(row.get("SAT_TOTAL_75")):
        gaps.append("no_sat")
    if pd.isna(row.get("ADMISSIONS_RATE")):
        gaps.append("no_admit_rate")
    return ",".join(gaps)


def rank_and_filter(df: pd.DataFrame, max_net_price: float, mgi_at_least_median: bool,
                    top_n: int, exclude_flagged: bool) -> pd.DataFrame:
    """Apply the same filters the live app exposes, then rank by Value Score."""
    out = df.copy()

    # need the essentials to rank at all
    out = out.dropna(subset=["COA", "NET_PRICE_MID", "IGRNT_A"])

    # Value Score needs all three components (affordability, quality, generosity).
    # If one is missing the score is NaN, which would sort last silently instead of
    # being excluded honestly -- so drop unscoreable rows outright. Deliberately NOT
    # imputed: crediting a college with a median graduation rate it never reported
    # would let non-reporting schools outrank ones that reported honestly.
    out = out.dropna(subset=["VALUE_SCORE"])

    if max_net_price is not None:
        out = out[out["NET_PRICE_MID"] <= max_net_price]

    if mgi_at_least_median:
        # Median over the WHOLE cleaned dataset, not the rows left after the filters
        # above. A post-filter median moves whenever the user changes max_net_price,
        # and since cheap colleges are usually the generous ones it would set the bar
        # well above "more generous than a typical 4-year college", which is what this
        # filter claims to mean.
        median_mgi = df["MGI"].median()
        out = out[out["MGI"] >= median_mgi]

    if exclude_flagged:
        out = out[out["RISK_FLAGS"] == ""]

    out = out.sort_values("VALUE_SCORE", ascending=False).reset_index(drop=True)
    out.insert(0, "RANK", out.index + 1)

    if top_n:
        out = out.head(int(top_n))
    return out
