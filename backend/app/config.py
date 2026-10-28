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
