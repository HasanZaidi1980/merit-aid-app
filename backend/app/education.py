"""Reference distributions for the education section.

The "Build a College" sandbox has to re-score a hypothetical institution on every
slider drag. Doing that server-side would mean a request per pixel of travel, so
instead the backend ships the shape of the real distribution once and the browser
scores against it locally.

What makes that exact rather than approximate: VALUE_SCORE is the mean of three
percentile ranks, and a percentile rank is fully determined by the sorted
distribution. 101 breakpoints (p0, p1, ... p100) reproduce it to within half a
percentile -- close enough that the number the sandbox shows matches the number
the ranking would give, which is the whole point of letting users poke at it.
"""
import functools

import numpy as np
import pandas as pd

# The three inputs to VALUE_SCORE, with the direction each one improves in.
# `higher_is_better` has to travel with the data: net price is the one component
# where a bigger number is a worse college, and a sandbox that got that backwards
# would teach the opposite of the truth.
_COMPONENTS = {
    "net_price": ("NET_PRICE_MID", False),
    "grad_rate": ("GRAD_RATE", True),
    "aid_share": ("AID_SHARE", True),
}

# Everything the explain-this cards draw a distribution strip for.
_DIMENSIONS = {
    "sticker": "COA",
    "tuition": "TUITION2",
    "grant": "IGRNT_A",
    "net_price": "NET_PRICE_MID",
    "admit_rate": "ADMISSIONS_RATE",
    "grad_rate": "GRAD_RATE",
    "sat": "SAT_TOTAL_75",
    "aid_share": "AID_SHARE",
    "discount": "DISCOUNT",
    "value_score": "VALUE_SCORE",
}

_BINS = 28


def _summary(s: pd.Series) -> dict:
    """Five-number summary plus a histogram, from the non-null values only."""
    v = s.dropna().to_numpy(dtype=float)
    if v.size == 0:
        return {"n": 0}
    counts, edges = np.histogram(v, bins=_BINS)
    return {
        "n": int(v.size),
        "min": float(v.min()), "max": float(v.max()),
        "p25": float(np.percentile(v, 25)),
        "median": float(np.percentile(v, 50)),
        "p75": float(np.percentile(v, 75)),
        # Histogram as parallel arrays -- smaller over the wire than 28 objects,
        # and Plotly wants it in this shape anyway.
        "bin_edges": [round(float(e), 4) for e in edges],
        "bin_counts": [int(c) for c in counts],
    }


@functools.lru_cache(maxsize=1)
def distributions() -> dict:
    """Percentile breakpoints + histograms for the whole cleaned dataset.

    Cached: the underlying frame is itself cached and never mutated in-process,
    so this is computed once per boot.
    """
    from .data import build_dataset

    df = build_dataset()

    # The sandbox splits the sticker into "tuition" and "everything else" so the
    # user can see it is a sum. Housing + books is not an IPEDS column, so derive
    # it here rather than making the browser guess a plausible range for it.
    df = df.assign(EXTRAS=df["COA"] - df["TUITION2"])

    components = {}
    for key, (col, higher_is_better) in _COMPONENTS.items():
        v = df[col].dropna().to_numpy(dtype=float)
        components[key] = {
            "column": col,
            "higher_is_better": higher_is_better,
            # p0..p100 inclusive: index i is the value at the i-th percentile, so
            # the browser can invert it with a binary search.
            "breakpoints": [round(float(x), 4)
                            for x in np.percentile(v, np.arange(101))],
        }

    # Breakpoints for the *output* too, so the sandbox can answer the question that
    # actually lands -- "where would this college rank?" -- rather than only showing
    # a 0-100 score with no frame of reference.
    scored = df["VALUE_SCORE"].dropna().to_numpy(dtype=float)

    return {
        "n": int(len(df)),
        # Colleges with a Value Score at all. Smaller than `n` because a missing
        # graduation rate makes a college unscoreable, and ranking against 1,907
        # when only 1,727 can be ranked would overstate every position.
        "scored_n": int(scored.size),
        "components": components,
        "value_score_breakpoints": [round(float(x), 4)
                                    for x in np.percentile(scored, np.arange(101))],
        "dimensions": {**{k: _summary(df[c]) for k, c in _DIMENSIONS.items()},
                       "extras": _summary(df["EXTRAS"])},
    }
