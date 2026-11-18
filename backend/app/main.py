"""FastAPI app. Mirrors the endpoints observed on the live site."""
import math
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

from . import config, data, education, merit_policy

app = FastAPI(title="Merit Aid Finder (reconstruction)", version="1.0")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

# Fields returned per college — the observed 23-field schema plus DATA_GAPS,
# MERIT_POLICY and (Phase 4) MERIT_POLICY_YEAR / MERIT_POLICY_STATUS. All four are
# additive; nothing from the original contract was ever renamed or removed.
ROW_FIELDS = [
    "RANK", "UNITID", "INSTNM", "STABBR", "CONTROL_LABEL",
    "COA", "COA_COMPLETE", "TUITION2", "IGRNT_A", "NET_PRICE_MID", "DISCOUNT",
    "ADMISSIONS_RATE", "GRAD_RATE", "SATVR75", "SATMT75", "SAT_TOTAL_75",
    "AID_SHARE", "VALUE_SCORE", "COMPONENTS_USED", "RISK_FLAGS", "DATA_GAPS",
    "MERIT_POLICY", "MERIT_POLICY_YEAR", "MERIT_POLICY_STATUS",
    "MGI", "NET_PRICE_RATIO", "COMPOSITE_LEGACY",
]


def _clean(v):
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return None
    return v


@app.get("/api/meta")
def get_meta():
    return data.meta()


@app.get("/api/colleges")
def get_colleges(
    max_net_price: float = Query(config.DEFAULTS["max_net_price"]),
    mgi_at_least_median: bool = Query(config.DEFAULTS["mgi_at_least_median"]),
    top_n: int = Query(config.DEFAULTS["top_n"]),
    exclude_flagged: bool = Query(config.DEFAULTS["exclude_flagged"]),
    exclude_no_merit: bool = Query(config.DEFAULTS["exclude_no_merit"]),
):
    from .scoring import rank_and_filter
    df = data.build_dataset()
    ranked = rank_and_filter(df, max_net_price, mgi_at_least_median, top_n,
                             exclude_flagged, exclude_no_merit)
    rows = []
    for _, r in ranked.iterrows():
        rows.append({f: _clean(r[f]) if f in r else None for f in ROW_FIELDS})
    return {"count": len(rows), "colleges": rows}


@app.get("/api/education/distributions")
def education_distributions():
    """Reference distributions so the browser can score a hypothetical college."""
    return education.distributions()


@app.get("/api/merit-policy")
def get_merit_policy():
    """Every CDS-verified merit-aid record, with provenance and coverage."""
    return {
        "verified": merit_policy.roster(),
        "unresolved": merit_policy.unverified(),
        "coverage": merit_policy.coverage(),
        "status": "cds_sourced",
        "note": (
            "Each record was read from that institution's own Common Data Set, "
            "section H2A line n: students with no financial need who were awarded "
            "institutional non-need-based scholarship or grant aid, excluding "
            "athletic awards and tuition benefits. 'need_only' means that line "
            "reported zero for the CDS year shown -- not that no student ever "
            "received merit money, since the CDS cannot see merit aid layered on "
            "top of a need award. 'unknown' means unchecked, for the whole "
            "dataset except the institutions listed here. Sourcing was scoped to "
            "the default top 50 shortlist and attempted in full there: 23 of 50 "
            "resolved. A full-dataset crawl was measured at roughly 38% and "
            "rejected rather than built -- see coverage.scope and "
            "coverage.sector_caveat, and read coverage.verified against "
            "coverage.attempted, not against the dataset size."
        ),
    }


@app.get("/api/health")
def health():
    return {"ok": True}


@app.on_event("startup")
def _warmup():
    """Build the dataset once at boot so the first request isn't slow."""
    try:
        data.build_dataset()
    except Exception as e:  # never let warmup crash the server
        print(f"[warmup] skipped: {e}")
