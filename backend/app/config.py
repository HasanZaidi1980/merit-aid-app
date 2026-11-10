"""Central configuration. All values overridable via environment variables."""
import os

# Where the 8 IPEDS CSV files live. Locally: ./data. In GCP: a path where the
# Cloud Storage bucket is mounted, or a local cache synced from the bucket.
DATA_DIR = os.getenv("DATA_DIR", os.path.join(os.path.dirname(__file__), "..", "data"))

# Where the built vector index is persisted (Persistent Disk in GCP).
INDEX_DIR = os.getenv("INDEX_DIR", os.path.join(os.path.dirname(__file__), "..", "index"))

# Anthropic API key for RAG answer generation. Read from env / Secret Manager.
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")

# Default filter values (mirror /api/meta on the live app).
DEFAULTS = {
    "max_net_price": 25000,
    "mgi_at_least_median": True,
    "top_n": 20,
    "exclude_flagged": True,
    # Off by default: the curated need-only list covers 26 of 1,907 colleges, so
    # filtering on it by default would imply the rest had been checked and cleared.
    "exclude_no_merit": False,
}

# The 8 IPEDS files this app expects (exact filenames).
FILES = {
    "hd":       "HD2022.csv",
    # One file, not the two the reconstruction originally assumed. IPEDS has never
    # published an SFA P1/P2 split; both IGRNT_A and the net-price columns live here.
    "sfa":      "SFA2122.csv",
    "ic_ay":    "IC2022_AY.csv",
    "adm":      "ADM2022.csv",
    "drvadm":   "DRVADM2022.csv",
    "drvgr":    "DRVGR2022.csv",
    "mission":  "IC2022Mission.csv",
}

# IPEDS uses these as "missing / not applicable" sentinels.
MISSING_SENTINELS = [-1, -2, -3, -9]

# Declared units for the rate columns, taken from each variable's IPEDS dictionary
# entry rather than inferred from the values. DVADM01's description says "Ratios are
# converted to percentages and rounded to the nearest whole number"; GBA4RTT is a
# graduation rate on the same 0-100 scale.
#
# This replaces a `max > 1.5` heuristic. The heuristic happened to fire correctly on
# the full 2022-23 universe, but it reads the data to decide what the data means: on
# a filtered or small subset where every rate is small it would silently leave
# percentages unscaled, making every rate 100x too low with no error. A declaration
# cannot do that -- and load_rates() verifies the result lands in 0..1, so a file
# that stops matching its declaration fails loudly instead of scoring wrong.
RATE_COLUMNS = {
    "ADMISSIONS_RATE": "percent",   # DRVADM2022.DVADM01
    "GRAD_RATE": "percent",         # DRVGR2022.GBA4RTT
}

# Value Score weights. Equal thirds by default -- see FORMULAS.md for the sensitivity
# analysis behind that choice. Overridable per-deployment so the methodology is a
# stated configuration rather than a constant buried in the scoring code; /api/meta
# reports whatever is actually in force.
VALUE_WEIGHTS = {
    "affordability": float(os.getenv("WEIGHT_AFFORDABILITY", 1.0 / 3.0)),
    "graduation": float(os.getenv("WEIGHT_GRADUATION", 1.0 / 3.0)),
    "generosity": float(os.getenv("WEIGHT_GENEROSITY", 1.0 / 3.0)),
}
