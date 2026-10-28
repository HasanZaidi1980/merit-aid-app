# Merit Aid Finder — Reconstruction

> **What this is:** a from-scratch, working rebuild that matches the *observable behavior*
> of the live app at `http://136.68.78.253/` — same API endpoints, same data
> schema, same charts, same scoring. It is **NOT** a copy of your friend's source code
> (that can't be recovered from a URL — see `ANALYSIS.md`). Treat it as a faithful
> functional twin, not a byte-for-byte replica.

## Run it locally in 3 steps

**Option A — Docker (whole stack at once):**
```bash
# 1. generate demo data (or drop the real 7 IPEDS CSVs into backend/data/)
cd backend && pip install -r requirements.txt && python scripts/make_sample_data.py && cd ..
# 2. (optional) enable AI answers
echo "ANTHROPIC_API_KEY=sk-ant-..." > .env
# 3. build + run
docker compose up --build
```
Open **http://localhost:8080**.

**Option B — run each part directly:**
```bash
# backend
cd backend
pip install -r requirements.txt
python scripts/make_sample_data.py          # writes 8 sample CSVs to backend/data/
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
pytest                                      # 17 tests, no data files required
```
Fixtures are built in memory, not read from `backend/data/` — the sample data has no
missing values, so it exercises none of the data-quality logic.

## Using the real IPEDS data
Replace the sample files in `backend/data/` with the real 7 files (same names):
`HD2022.csv, SFA2122.csv, IC2022_AY.csv, ADM2022.csv, DRVADM2022.csv, DRVGR2022.csv, IC2022Mission.csv`. Restart the backend.

## Structure
```
backend/    FastAPI app — data pipeline, scoring, RAG, API
  app/data.py       load + clean + merge the 7 files
  app/scoring.py    MGI, Aid Share, Value Score, Legacy composite  ← audit the formulas here
  app/merit_policy.py  curated need-only roster — the one thing IPEDS can't tell us
  app/education.py  percentile breakpoints + histograms for the education section
  app/rag.py        mission-statement embeddings + retrieval + Claude answer
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
> Share measure *generosity*, not merit. 11 of the top 23 ranked colleges award no merit
> aid at all. The app says so in the UI and flags 26 known need-only institutions via
> `MERIT_POLICY`; the real fix needs Common Data Set H2A. See `PROJECT_BRIEF.md` §5.1.

## Learn the numbers
The app has a built-in education section, because none of these figures mean what a
first-time reader assumes:
- **Build a College** — drag tuition, grant, net price and the rest, and watch the Value
  Score and its ranking move against all 1,907 real colleges, live.
- **Explain anywhere** — a `?` beside every metric gives a one-line definition, the
  formula, the usual misconception, and where that college sits in the distribution.
- **Head to head** — two colleges, metric by metric. Admissions rate and SAT 75th are
  deliberately marked *no winner*: neither one makes a college better.

## AI feature
Uses a **local embedding model** (sentence-transformers) to index mission statements, retrieves the most relevant ones for a question, and asks **Claude** to synthesize an answer from them. Without `ANTHROPIC_API_KEY` set, it still runs and returns the retrieved passages (and falls back to TF-IDF if sentence-transformers isn't installed).

See `DEPLOYMENT.md` for GCP.
