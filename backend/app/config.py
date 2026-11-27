"""Central configuration. All values overridable via environment variables."""
import os

# Where the 6 IPEDS CSV files live. Locally: ./data. In GCP: a path where the
# Cloud Storage bucket is mounted, or a local cache synced from the bucket.
DATA_DIR = os.getenv("DATA_DIR", os.path.join(os.path.dirname(__file__), "..", "data"))

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

# Which IPEDS release to read. Set IPEDS_YEAR to switch; both years stay runnable so
# a difference between them can be diffed rather than guessed at. The label is the
# INSTITUTIONAL year -- the money always lags it by one, which FILES_BY_YEAR records
# per release rather than leaving to memory.
IPEDS_YEAR = os.getenv("IPEDS_YEAR", "2022-23")

# There is no mission file in either year: IPEDS last published institutional mission
# statements for 2007 (IC2007Mission; IC2008Mission and IC2022Mission return 404 from
# the IPEDS data center, verified 2026-11-17). See PROJECT_STATE.md for why the RAG
# panel was removed.
#
# Filenames are as IPEDS ships them inside the download zips, which is not
# consistently cased -- HD2023.csv is uppercase while sfa2223.csv is lowercase, and
# the 2022-23 set in backend/data/ was renamed to uppercase by hand when it was
# installed. data._read() resolves the name case-insensitively so that neither a
# rename nor a case-sensitive filesystem can turn this into a missing-file error.
FILES_BY_YEAR = {
    "2022-23": {
        "hd":       "HD2022.csv",
        # One file, not the two the reconstruction originally assumed. IPEDS has never
        # published an SFA P1/P2 split; both IGRNT_A and the net-price columns live here.
        "sfa":      "SFA2122.csv",      # money: 2021-22
        "ic_ay":    "IC2022_AY.csv",    # tuition: 2022-23
        "adm":      "ADM2022.csv",
        "drvadm":   "DRVADM2022.csv",
        "drvgr":    "DRVGR2022.csv",
    },
    "2023-24": {
        "hd":       "HD2023.csv",
        "sfa":      "SFA2223.csv",      # money: 2022-23
        "ic_ay":    "IC2023_AY.csv",    # tuition: 2023-24
        "adm":      "ADM2023.csv",
        "drvadm":   "DRVADM2023.csv",
        "drvgr":    "DRVGR2023.csv",
    },
}

if IPEDS_YEAR not in FILES_BY_YEAR:
    raise ValueError(
        f"IPEDS_YEAR={IPEDS_YEAR!r} is not a release this app knows. "
        f"Known: {sorted(FILES_BY_YEAR)}"
    )

FILES = FILES_BY_YEAR[IPEDS_YEAR]

# The net-price and grant variables are NOT year-coded the way their names suggest.
# Verified against the SFA2223 dictionary on 2026-11-27: the trailing digit is an
# index relative to the file's own survey year, not a fixed year code.
#
#   in SFA2122:  NPT442 / NPIS442 / GRN4A42 / GIS4A42  ->  2021-22
#   in SFA2223:  NPT442 / NPIS442 / GRN4A42 / GIS4A42  ->  2022-23   (same names!)
#                NPT441 / NPIS441 / GRN4A41 / GIS4A41  ->  2021-22
#
# So the column names never change between releases and the app needs no mapping --
# but anyone "fixing" this by pattern-matching the old year onto ...1 would silently
# serve data a year stale, with no error anywhere. That is why this is written down.
SFA_YEAR_BY_RELEASE = {"2022-23": "2021-22", "2023-24": "2022-23"}
SFA_MONEY_YEAR = SFA_YEAR_BY_RELEASE[IPEDS_YEAR]

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
