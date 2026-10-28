# Project Brief — Merit Aid Finder

A briefing for Claude Cowork (or any agent) picking this project up to **test, analyze, and improve** it. Read this first; it explains what the project is, how it's built, what's uncertain, and where to focus.

---

## 1. What the project is

**Merit Aid Finder** helps middle-class families (household income ~$75k–$110k) find 4-year colleges that offer the best *all-around value* — generous institutional grant aid relative to a high sticker price, balanced against affordability and graduation outcomes.

The core insight: some colleges have scary sticker prices but give large institutional grants, so the price a family actually pays can be lower than at a "cheaper" school. This app surfaces those hidden deals from official U.S. Department of Education **IPEDS 2022-23** data, ranks colleges by a composite value metric, visualizes the trade-offs, and offers an AI feature that cross-checks the numbers against each college's stated mission.

Audience/context: this began as a student data project (a Python pipeline) and was rebuilt as a web app.

---

## 2. IMPORTANT context — this is a reconstruction

This codebase is a **from-scratch functional reconstruction** that matches the *observable behavior* of a deployed reference app (same API endpoints, same data schema, same charts, same described scoring). It is **not** the original author's source code — that was never available. Practical implications for you:

- The **scoring formulas** in `backend/app/scoring.py` are a best-effort reconstruction from the app's on-screen descriptions. They are plausible and self-consistent but may differ from the original's internal weighting. **Treat scoring as a prime candidate for verification and improvement.**
- Anywhere behavior is inferred rather than confirmed, prefer making it correct and well-documented over matching an unknown original.

See `ANALYSIS.md` and `observed-api-contract.md` for what was actually observed on the reference app.

---

## 3. Architecture

```
frontend/  React + Vite + Plotly single-page app (Financial Dashboard theme)
backend/   FastAPI (Python) — data pipeline, scoring, RAG, JSON API
deploy/    Terraform (GCP: VPC, GKE, Artifact Registry, Cloud Storage) + K8s manifests
docker-compose.yml   runs frontend + backend together locally
```

- **Frontend** calls same-origin `/api/*`. In dev, Vite proxies to the backend; in prod, nginx proxies to the backend service.
- **Backend** loads 8 IPEDS CSVs, cleans + merges them on `UNITID`, computes metrics, and serves ranked results. It also builds a vector index over college mission statements for the AI feature.
- **Deployment target** is GCP (GKE behind a Google Cloud Load Balancer), mirroring the reference app.

### Key backend files
- `app/data.py` — load, clean (IPEDS missing-value sentinels −1/−2/−3/−9 → NaN), filter to 4-year degree-granting, merge the 8 files, build the analysis table.
- `app/scoring.py` — all derived metrics and the ranking/filtering logic. **Audit here.**
- `app/rag.py` — mission-statement embeddings (local `sentence-transformers`, TF-IDF fallback) + retrieval + Claude answer generation.
- `app/main.py` — the `/api/*` endpoints.
- `scripts/make_sample_data.py` — generates 8 realistic sample CSVs so the app runs without the real dataset.

---

## 4. The data (8 IPEDS files)

Placed in `backend/data/` with exact names:

| File | Supplies |
|---|---|
| HD2022.csv | College directory + filter (name, state, control, level) |
| SFA2122_P1.csv | Avg institutional grant (`IGRNT_A`) |
| SFA2122_P2.csv | Net price for mid-income families (`NPT442`) |
| IC2022_AY.csv | Sticker price / cost-of-attendance components (`TUITION2`, charges) |
| ADM2022.csv | SAT 75th percentile scores |
| DRVADM2022.csv | Admissions rate (`DVADM01`) |
| DRVGR2022.csv | Graduation rate (`GBA4RTT`) |
| IC2022Mission.csv | Mission statements (for the AI feature) |

The app runs on generated **sample data** out of the box; real IPEDS files drop in by the same names.

---

## 5. Metrics & scoring (audit these)

- **MGI (Merit Generosity Index)** = `IGRNT_A / TUITION2` — grant vs tuition sticker (original assignment metric).
- **Aid Share** = `IGRNT_A / COA` — grant as a fraction of *total* sticker (cost of attendance). Headline generosity.
- **Net Price Ratio** = `NET_PRICE_MID / COA` — share of sticker a family still pays (lower = better).
- **Discount** = `COA − NET_PRICE_MID`.
- **Value Score (0–100)** = mean of three equally-weighted percentile ranks: affordability (lower net price), graduation rate, and aid generosity (aid share). **This is the primary ranking metric.**
- **Legacy Score** = `(MGI + grad_rate) / net_price_ratio` — the original formula, retained for comparison.

Default filters (also user-adjustable): net price ≤ $25,000, MGI ≥ dataset median, top 20, exclude data-flagged rows.

---

## 6. API contract

- `GET /api/meta` — dataset stats (including `median_mgi`, the threshold `mgi_at_least_median` actually applies), default filter values, and the list of toggleable data dimensions.
- `GET /api/colleges?max_net_price=&mgi_at_least_median=&top_n=&exclude_flagged=` — ranked shortlist; each row has 24 fields (see `observed-api-contract.md`).
- `GET /api/rag/status` — `{ index_ready, api_key_set }`.
- `POST /api/rag/query` — body `{ question, unitids?, college_names? }` → `{ answer, sources, mode }`. Retrieval is scoped to the currently shown colleges.
- `GET /api/health` — liveness.

---

## 7. How to run

**Docker (whole stack):**
```bash
cd merit-aid-app/backend && pip install -r requirements.txt && python scripts/make_sample_data.py && cd ..
# optional: echo "ANTHROPIC_API_KEY=sk-ant-..." > .env    (enables AI answers)
docker compose up --build     # → http://localhost:8080
```

**Direct:**
```bash
cd backend && pip install -r requirements.txt && python scripts/make_sample_data.py
uvicorn app.main:app --reload          # http://localhost:8000
cd ../frontend && npm install && npm run dev   # http://localhost:5173
```

**Tests:**
```bash
cd backend && pip install -r requirements.txt -r requirements-dev.txt
pytest                                 # 8 tests, no data files needed
```
The suite builds its fixtures in memory rather than reading `backend/data/`, because
the generated sample data has no missing values and so exercises none of the
flag/degradation logic. Don't "fix" a test by pointing it at the CSVs.

The AI feature works without a key (returns retrieved passages); set `ANTHROPIC_API_KEY` for synthesized answers.

> **Note on Windows + old PowerShell:** `&&` is rejected — run the commands one per
> line. See `GOTCHAS.md`.

---

## 8. Known gaps, risks & things to verify

1. **Scoring fidelity** — the Value Score/percentile logic is reconstructed; confirm it's statistically sound (NaN handling in percentile ranks, ties, whether equal weighting is defensible) and matches the intended definition.
2. **COA construction** — `COA` is summed from tuition + charge components when present, else falls back to tuition. Verify this matches how net price is measured, so `Discount` and `Aid Share` are apples-to-apples.
3. **Reference app showed intermittent `502`s** on `/api/*` — worth reproducing under load; check backend startup time, resource limits, readiness probes.
4. **Test coverage is partial** — `backend/tests/test_scoring.py` covers scoring and the flag split (8 tests). Still missing: `data.py` load/merge/clean, API tests for malformed params, and the RAG endpoint with and without a key.
5. **RAG fallback** — if `sentence-transformers` isn't installed it silently uses TF-IDF; retrieval quality differs. Confirm which is intended and make it explicit.
6. **Frontend bundle is large** (Plotly). Fine for a demo; could be code-split.
7. **Data-quality flags** — reworked since this list was written. `RISK_FLAGS` now carries only scoring-relevant problems and `DATA_GAPS` carries display-only ones; `exclude_flagged` gates on the former. Covered by tests. `FORMULAS.md` tracks what's resolved vs still open — read that rather than this list for scoring status.
8. **Percentage scaling** — admissions/graduation rates are divided by 100 only when values look like percentages; check this heuristic against the real IPEDS files.

---

## 9. Suggested tasks for Cowork

**Test**
- ~~Add a `pytest` suite for `scoring.py`~~ — done, `backend/tests/test_scoring.py`. Extend it to `data.py` (load/merge/clean, sentinel handling, empty-result handling).
- Add API tests (FastAPI `TestClient`) for all endpoints, including malformed query params and the RAG endpoint with/without an API key.
- Add a smoke test that boots the stack and hits `/api/health`, `/api/meta`, `/api/colleges`.

**Analyze**
- Validate the scoring statistically; report whether Value Score behaves sensibly across the real dataset (distribution, sensitivity to each component, correlation between Value Score and Legacy Score).
- Profile backend load time and the 502 risk; recommend probe/resource tuning.
- Review data cleaning against the real IPEDS schema for silent mismatches (column names, units, sentinels).

**Improve**
- Make scoring weights configurable and documented; expose them in `/api/meta`.
- Harden error handling and input validation on the API; return helpful messages instead of 500s.
- Add caching / precomputation so filtering is instant on the full dataset.
- Improve RAG (chunking long missions, showing similarity scores in the UI, citing sources inline).
- Code-split the frontend bundle; add loading/empty/error states everywhere.
- Add CI (lint + tests) and a Makefile / task runner.

**Guardrails**
- Keep the API contract in `observed-api-contract.md` stable unless there's a clear reason to change it (the frontend depends on it).
- The `ANTHROPIC_API_KEY` must never be committed or logged; it comes from env / a K8s secret.
- Don't commit real IPEDS data or the generated index (already git-ignored).

---

## 10. File map

```
merit-aid-app/
  PROJECT_BRIEF.md          ← this file
  HANDOFF.md                current status + how Claude Code and Cowork split the work
  README.md                 how to run
  ANALYSIS.md               what the live reference app is + cloud/hosting findings
  observed-api-contract.md  exact endpoints + the 24-field schema this app returns
  FORMULAS.md               every metric, with resolved vs still-open scoring issues
  GOTCHAS.md                environment traps (PowerShell, Python 3.13, missing files)
  DEPLOYMENT.md             GCP deploy steps + teardown
  docker-compose.yml
  backend/
    app/{config,data,scoring,rag,main}.py
    scripts/make_sample_data.py
    tests/test_scoring.py   scoring + flag-split tests (in-memory fixtures)
    conftest.py  requirements.txt  requirements-dev.txt  Dockerfile
  frontend/
    src/{App.jsx,Plot.jsx,api.js,main.jsx,styles.css}
    package.json  vite.config.js  index.html  nginx.conf  Dockerfile
  deploy/
    terraform/{main,variables,outputs}.tf
    k8s/{backend,frontend,ingress}.yaml
```
