# Merit Aid Finder — Reconstruction

[![CI](https://github.com/HasanZaidi1980/merit-aid-app/actions/workflows/ci.yml/badge.svg)](https://github.com/HasanZaidi1980/merit-aid-app/actions/workflows/ci.yml)

**Live: https://merit-aid-finder.com/** — running on GKE, with a Google-managed TLS
certificate *(2026-11-28)*.

`http://136.81.186.158/` still works and is the fallback if DNS or TLS ever misbehaves;
it has no certificate, so type `http://` explicitly on that one — browsers that try HTTPS
first will fail on a bare IP rather than fall back. There is deliberately no
HTTP-to-HTTPS redirect, so both paths keep working independently. `www` is **not** set up:
only the apex resolves.

## What it does

Finds four-year US colleges that are cheap *for a middle-income family* rather than cheap
on paper — the ones whose sticker price is $70-80k and whose actual net price is $10-15k,
which is not information a college ranking usually surfaces.

It ranks **1,907 four-year degree-granting institutions** on a Value Score built from
three percentile ranks (affordability, graduation rate, aid generosity), and shows for
each one the published cost of attendance, the average institutional grant, what a family
earning **$75,000-$110,000** actually pays, admissions selectivity and graduation rate.
There is a comparison table, five charts, CSV export, a head-to-head view, and a sandbox
that re-scores a hypothetical college against the real distribution as you drag sliders.

**The data is real, and it is two survey years, not one:**

| Source | Year | What comes from it |
|---|---|---|
| `HD2022`, `IC2022_AY`, `ADM2022`, `DRVADM2022`, `DRVGR2022` | **IPEDS 2022-23** | Who the institution is, tuition, SAT, admissions rate, graduation rate |
| `SFA2122` | **IPEDS 2021-22** | Every money figure: net price, average grant, and therefore cost of attendance |

Mixing them is unavoidable — IPEDS publishes student financial aid a year behind — but it
means the dollar amounts describe the 2021-22 cohort while the institutional details
describe 2022-23. Nothing in the app is imputed, estimated or filled in: a college missing
a Value Score component is excluded rather than guessed at.

> ⚠️ **It cannot tell you about merit aid specifically.** IPEDS reports one number for all
> institutional grant aid, need-based and merit combined, and publishes no split. The
> generosity figures here measure generosity. Where a college's own Common Data Set
> answers the question directly, the app says so with the year it came from — 24
> institutions so far, out of 56 attempted. See `FORMULAS.md` §4.

> **What this repo is:** a from-scratch rebuild matching the *observable behavior* of the
> app at `http://136.68.78.253/` — same endpoints, same row schema, same charts, same
> scoring. It is **NOT** a copy of that source code (which can't be recovered from a URL —
> see `ANALYSIS.md`). A faithful functional twin, not a byte-for-byte replica.

## Run it locally in 3 steps

**Option A — Docker (whole stack at once):**
```bash
# 1. generate demo data (or drop the real 6 IPEDS CSVs into backend/data/)
cd backend && pip install -r requirements.txt && python scripts/make_sample_data.py && cd ..
# 2. build + run
docker compose up --build
```
Open **http://localhost:8080**.

**Option B — run each part directly:**
```bash
# backend
cd backend
pip install -r requirements.txt
python scripts/make_sample_data.py          # writes 6 sample CSVs to backend/data/
uvicorn app.main:app --reload               # http://localhost:8000
# frontend (new terminal)
cd frontend
npm install
npm run dev                                 # http://localhost:5173 (proxies /api to :8000)
```

## Tests
```bash
cd backend
pip install -r requirements.txt -r requirements-dev.txt
pytest                                      # 88 tests, no data files required
ruff check .                                # lint (config: backend/ruff.toml)
python scripts/smoke_test.py                # boot real uvicorn over sample data
```
Fixtures are built in memory, not read from `backend/data/` — the sample data has no
missing values, so it exercises none of the data-quality logic.

## Using the real IPEDS data
Replace the sample files in `backend/data/` with the real **6** files (same names):
`HD2022.csv, SFA2122.csv, IC2022_AY.csv, ADM2022.csv, DRVADM2022.csv, DRVGR2022.csv`.
Restart the backend — the dataset is cached per process, so swapping files does nothing
until it restarts. `backend/data/` is gitignored and stays that way.

## Structure
```
backend/    FastAPI app — data pipeline, scoring, API
  app/data.py       load + clean + merge the 6 files
  app/scoring.py    MGI, Aid Share, Value Score, Legacy composite  ← audit the formulas here
  app/merit_policy.py  per-institution CDS merit-aid records — the one thing IPEDS can't tell us
  app/education.py  percentile breakpoints + histograms for the education section
  app/main.py       the /api/* endpoints
  scripts/make_sample_data.py   demo dataset generator
frontend/   React + Vite + Plotly SPA (Financial Dashboard theme)
  src/education/    glossary (terse definitions) + browser-side Value Score
  src/components/   Sandbox, Compare, Explain, DistStrip, MeritNote
deploy/     Terraform (VPC, GKE, Artifact Registry, GCS) + K8s manifests
```

## The metrics (plain English)
- **MGI** = grant ÷ tuition sticker (original assignment metric).
- **Aid Share** = grant ÷ total sticker (COA) — headline generosity.
- **Value Score (0–100)** = average of three percentile ranks: affordability, graduation rate, aid generosity.
- **Legacy Score** = (MGI + grad rate) ÷ net-price ratio — the original formula, kept for comparison.

> ⚠️ **"Merit" is a misnomer on these.** IPEDS reports one figure for all institutional
> grant aid — need-based and merit combined — and publishes no split, so MGI and Aid
> Share measure *generosity*, not merit. The app says so in the UI, and `MERIT_POLICY`
> carries what each college's own Common Data Set (section H2A line n) reports, with the
> edition it came from: 24 institutions resolved of 56 attempted, and a verdict expires
> rather than ageing into a claim. See `FORMULAS.md` §4.

## Learn the numbers
The app has a built-in education section, because none of these figures mean what a
first-time reader assumes:
- **Build a College** — drag tuition, grant, net price and the rest, and watch the Value
  Score and its ranking move against all 1,907 real colleges, live.
- **Explain anywhere** — a `?` beside every metric gives a one-line definition, the
  formula, the usual misconception, and where that college sits in the distribution.
- **Head to head** — two colleges, metric by metric. Admissions rate and SAT 75th are
  deliberately marked *no winner*: neither one makes a college better.

## There is no AI feature any more
An earlier version had a RAG panel answering questions over "institutional mission
statements". It was removed in Phase 3.5: the file it indexed, `IC2022Mission.csv`, was
sample-generator output, and IPEDS has published no mission file since **2007**. Nothing
real could have been behind it, so presenting it beside genuine numbers was the worst bug
in the project. The app therefore needs no API key and the deploy needs no secret.

See `DEPLOYMENT.md` for GCP, `PROJECT_STATE.md` for status and phase history,
`FORMULAS.md` for every formula, and `observed-api-contract.md` for the API.
