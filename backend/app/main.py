"""FastAPI app. Mirrors the endpoints observed on the live site."""
import math
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from . import config, data, education, merit_policy, rag

app = FastAPI(title="Merit Aid Finder (reconstruction)", version="1.0")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

# Fields returned per college — the observed 23-field schema plus DATA_GAPS and
# MERIT_POLICY. Both are additive; nothing from the original contract was removed.
ROW_FIELDS = [
    "RANK", "UNITID", "INSTNM", "STABBR", "CONTROL_LABEL",
    "COA", "COA_COMPLETE", "TUITION2", "IGRNT_A", "NET_PRICE_MID", "DISCOUNT",
    "ADMISSIONS_RATE", "GRAD_RATE", "SATVR75", "SATMT75", "SAT_TOTAL_75",
    "AID_SHARE", "VALUE_SCORE", "COMPONENTS_USED", "RISK_FLAGS", "DATA_GAPS",
    "MERIT_POLICY", "MGI", "NET_PRICE_RATIO", "COMPOSITE_LEGACY",
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
    """The curated need-only roster, so the UI can show its size and sourcing."""
    return {
        "need_only": merit_policy.roster(),
        "count": len(merit_policy.NEED_ONLY_UNITIDS),
        "status": "provisional",
        "note": (
            "IPEDS reports total institutional grant aid (IGRNT_A) with no "
            "need-versus-merit split, so this list is curated from published "
            "institutional policy, not derived from the data. Absence means "
            "unchecked, not that merit aid is offered."
        ),
    }


@app.get("/api/rag/status")
def rag_status():
    return rag.status()


class RagQuery(BaseModel):
    question: str
    unitids: list[int] | None = None
    college_names: dict[str, str] | None = None


@app.post("/api/rag/query")
def rag_query(q: RagQuery):
    return rag.answer(q.question, unitids=q.unitids, college_names=q.college_names)


@app.get("/api/health")
def health():
    return {"ok": True}


@app.on_event("startup")
def _warmup():
    """Build the dataset + RAG index once at boot so status reports ready."""
    try:
        data.build_dataset()
        rag.get_index()
    except Exception as e:  # never let warmup crash the server
        print(f"[warmup] skipped: {e}")
