# Project Brief — Merit Aid Finder

A briefing for Claude Cowork (or any agent) picking this project up to **test, analyze, and improve** it. Read this first; it explains what the project is, how it's built, what's uncertain, and where to focus.

This doc absorbed the former `FORMULAS.md` (§5–§6, §12) and `GOTCHAS.md` (§9) so there is one place to look. For *what's left to do*, see `PROJECT_STATE.md`.

| | |
|---|---|
| §1 | [What the project is](#1-what-the-project-is) |
| §2 | [IMPORTANT context — this is a reconstruction](#2-important-context--this-is-a-reconstruction) |
| §3 | [Architecture](#3-architecture) |
| §4 | [The data](#4-the-data) |
| §5 | [Metrics & scoring](#5-metrics--scoring) |
| §6 | [Scoring status — resolved and still open](#6-scoring-status--resolved-and-still-open) |
| §7 | [API contract](#7-api-contract) |
| §8 | [How to run](#8-how-to-run) |
| §9 | [Environment gotchas](#9-environment-gotchas) |
| §10 | [Known gaps, risks & things to verify](#10-known-gaps-risks--things-to-verify) |
| §11 | [Suggested tasks](#11-suggested-tasks) |
| §12 | [Where to change things](#12-where-to-change-things) |
| §13 | [File map](#13-file-map) |

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
- **Backend** loads 7 IPEDS CSVs, cleans + merges them on `UNITID`, computes metrics, and serves ranked results. It also builds a vector index over college mission statements for the AI feature.
- **Deployment target** is GCP (GKE behind a Google Cloud Load Balancer), mirroring the reference app.

### Key backend files
- `app/data.py` — load, clean (IPEDS missing-value sentinels −1/−2/−3/−9 → NaN), filter to 4-year degree-granting, merge the 7 files, build the analysis table.
- `app/scoring.py` — all derived metrics and the ranking/filtering logic. **Audit here.**
- `app/rag.py` — mission-statement embeddings (local `sentence-transformers`, TF-IDF fallback) + retrieval + Claude answer generation.
- `app/main.py` — the `/api/*` endpoints.
- `scripts/make_sample_data.py` — generates 8 realistic sample CSVs so the app runs without the real dataset.

---

## 4. The data

### The 7 IPEDS files

Placed in `backend/data/` with **exact** names:

| File | Supplies |
|---|---|
| HD2022.csv | College directory + filter (name, state, control, level) |
| SFA2122.csv | Avg institutional grant (`IGRNT_A`) + net price (`NPT442` private / `NPIS442` public) |
| IC2022_AY.csv | Sticker price / cost-of-attendance components (`TUITION2`, charges) |
| ADM2022.csv | SAT 75th percentile scores |
| DRVADM2022.csv | Admissions rate (`DVADM01`) |
| DRVGR2022.csv | Graduation rate (`GBA4RTT`) |
| IC2022Mission.csv | Mission statements (for the AI feature) |

The app runs on generated **sample data** out of the box; real IPEDS files drop in by the same names.

### Columns the app reads

| Column | Meaning | Source file |
|---|---|---|
| `TUITION2` | Tuition sticker (in-state/published) | IC2022_AY.csv |
| `CHG4AY3`, `CHG5AY3` | Room & board / other charge components | IC2022_AY.csv |
| `COA` | Total sticker (cost of attendance) — **derived**, see §5 | IC2022_AY.csv |
| `IGRNT_A` | Average institutional grant per student | SFA2122.csv |
| `NET_PRICE_MID` | Net price, $75k–$110k band — **derived**, coalesces `NPT442` (private) and `NPIS442` (public), see below | SFA2122.csv |
| `ADMISSIONS_RATE` | Admit rate (IPEDS `DVADM01`) | DRVADM2022.csv |
| `GRAD_RATE` | 4-year graduation rate (IPEDS `GBA4RTT`) | DRVGR2022.csv |
| `SATVR75`, `SATMT75` | SAT 75th percentile, verbal + math | ADM2022.csv |

### Cleaning applied first (`data.py`)

- **Net price is coalesced from two variables.** IPEDS splits it into `NPT442` (private institutions) and `NPIS442` (public, in-state). The two share an identical dictionary title and are mutually exclusive, so reading `NPT442` alone looks correct while silently dropping **726 of 1907** public universities. `data.net_price()` combines them. See §6 Resolved.
- IPEDS missing sentinels `-1, -2, -3, -9` → `NaN`. In the real 2022-23 files **no negative sentinels appear** in any column this app reads — IPEDS leaves those cells blank — so this replacement is inert for this dataset. Kept for other years/columns.
- Universe filter: `ICLEVEL == 1` **and** `HDEGOFR1 >= 3` (4-year, degree-granting).
- All 7 files joined on `UNITID` (left joins onto the directory table).
- Rows missing **any** of `TUITION2`, `IGRNT_A`, `NET_PRICE_MID` are dropped — no financial basis to analyze.
- `ADMISSIONS_RATE` and `GRAD_RATE` are divided by 100 **only if** the column max exceeds 1.5 (heuristic to detect percent-vs-fraction encoding). See §6.

> **Column-name case matters.** `data.py` uppercases headers only for `HD2022`; the other seven files are read with exact uppercase column names and will raise `KeyError` if the real headers differ. Verify before swapping in real data.

---

## 5. Metrics & scoring

The definitive reference for every number the app computes. All of it lives in `backend/app/scoring.py` (metrics + ranking) and `backend/app/data.py` (inputs). **If you change a formula, update this section in the same turn.**

> **Status:** these formulas are a *reconstruction* of the reference app's described behavior, not a verified copy of an original implementation. They are internally consistent and defensible, but "matches the original" is unproven. §6 lists what is still open.

### COA (total sticker)

```
COA = TUITION2 + CHG4AY3 + CHG5AY3     # summed with min_count=1
COA = TUITION2                          # fallback if charge columns absent
COA_COMPLETE = every charge component used to build COA was present
```

`min_count=1` means the sum is non-NaN if *at least one* component exists — so a college with tuition but no room/board figure still gets a COA, equal to tuition alone. That understates its sticker and therefore understates its Discount and inflates its Aid Share, which is why `COA_COMPLETE` is false for it and `incomplete_coa` is flagged. See §6.

### The metrics

All computed in `add_metrics()`.

**Discount**
```
DISCOUNT = COA - NET_PRICE_MID
```
Dollars the sticker price overstates what a middle-income family actually pays. Bigger = better deal. This is what the dumbbell chart draws.

**MGI — Merit Generosity Index**
```
MGI = IGRNT_A / TUITION2
```
The original project's metric. Grant relative to **tuition only**. Used by the `mgi_at_least_median` filter, not by Value Score.

**Aid Share**
```
AID_SHARE = IGRNT_A / COA
```
Grant relative to the **full** sticker. The headline generosity measure, and the generosity input to Value Score.

> Note the denominators differ: `MGI` divides by tuition, `AID_SHARE` by total COA. Both are reported; they are not interchangeable and `AID_SHARE` is always the smaller of the two when charge components exist.

**Net Price Ratio**
```
NET_PRICE_RATIO = NET_PRICE_MID / COA
```
Fraction of sticker the family still pays. **Lower is better.**

### Value Score (0–100) — the primary ranking metric

```
affordability = percentile_rank(NET_PRICE_MID, higher_is_better=False)
quality       = percentile_rank(GRAD_RATE,     higher_is_better=True)
generosity    = percentile_rank(AID_SHARE,     higher_is_better=True)

VALUE_SCORE = (affordability + quality + generosity) / 3 * 100
```

- `percentile_rank` is pandas `Series.rank(pct=True)`; for "lower is better" it returns `1 - rank`.
- Three components, **equal weight** (⅓ each). Weights are hard-coded, not configurable.
- **Scope:** percentiles are computed over the *entire cleaned dataset*, before any user filter is applied. So a Value Score of 90 means "top 10% of all 4-year colleges", not "top 10% of the colleges currently shown". This is deliberate — scores stay stable as the user moves the filters — but it surprises people.
- **A missing component makes the college unscoreable**, and `rank_and_filter()` excludes it (see the ranking order below). It is not imputed and not scored on the components that happen to be present — see §6 Resolved for why.

**Legacy Score**
```
COMPOSITE_LEGACY = (MGI + GRAD_RATE) / NET_PRICE_RATIO
```
The original assignment's composite, retained for comparison only. Never used for ranking. Note it is **not** a faithful reproduction of the original: the original divided by a tuition-based ratio, whereas `NET_PRICE_RATIO` here is COA-based. Unbounded and heavily skewed — don't treat it as comparable to Value Score.

### Filtering & ranking order

`rank_and_filter()` applies steps **in this order** — the order matters:

1. Drop rows missing `COA`, `NET_PRICE_MID`, or `IGRNT_A`.
2. Drop rows with no `VALUE_SCORE` (any of the three components missing). These are excluded unconditionally — independent of `exclude_flagged` — because an unscoreable college cannot be ranked honestly.
3. `NET_PRICE_MID <= max_net_price` (default 25000).
4. If `mgi_at_least_median`: keep `MGI >= median(MGI)`, where the median is taken over the **whole cleaned dataset**, so the threshold does not move when the user changes the other filters.
5. If `exclude_flagged`: keep only rows where `RISK_FLAGS == ""`.
6. Sort by `VALUE_SCORE` descending; assign `RANK` starting at 1.
7. Truncate to `top_n` (default 20).

**Defaults** (`config.DEFAULTS`, echoed by `/api/meta`): `max_net_price=25000`, `mgi_at_least_median=True`, `top_n=20`, `exclude_flagged=True`.

### Data-quality bookkeeping

Three columns, split by whether the missing field actually affects the result:

- `COMPONENTS_USED` — which inputs were present for that row.
- `RISK_FLAGS` — problems that make the **ranking** untrustworthy: `incomplete_coa`, `no_grad_rate`. `exclude_flagged` gates on this column and nothing else.
- `DATA_GAPS` — missing fields that affect **display only**: `no_sat`, `no_admit_rate`. These never remove a college from the ranking.

In practice `no_grad_rate` can never appear on a *returned* row, because step 2 drops unscoreable rows before step 5 — so `exclude_flagged` is gated by `incomplete_coa` alone. The flag still counts in `/api/meta`'s `flagged_count`, which is computed over the whole dataset.

---

## 6. Scoring status — resolved and still open

### Resolved (2026-10-28)

- **Unscoreable colleges were ranked, not excluded.** `Series.add(other, fill_value=np.nan)` was a no-op, so a college missing `GRAD_RATE` scored `NaN` and sorted last silently. Now `rank_and_filter()` drops rows without a `VALUE_SCORE` outright. Two alternatives were rejected deliberately: *partial averaging* (scoring on the components present) rewards non-reporting, because the missing field is almost always the graduation rate that would have pulled a cheap, generous school down; and *median imputation* (what the original pipeline did via `fillna`) credits a college with outcomes it never reported, letting it outrank one that reported honestly.
- **Median MGI was computed post-filter.** It now uses the whole cleaned dataset. The old behavior took the median of the net-price-filtered subset, which (a) moved the bar whenever the user changed the slider and (b) set it far above "more generous than typical", because low net price is largely *caused* by large grants. On a test fixture the post-filter median was 0.691 against a dataset median of 0.596.
- **`exclude_flagged` dropped colleges over fields that don't affect the score.** `RISK_FLAGS` now holds only scoring-relevant problems (`incomplete_coa`, `no_grad_rate`); `no_sat` and `no_admit_rate` moved to a new `DATA_GAPS` column. Neither feeds Value Score, so neither removes a college from the ranking any more. On the reference app 1352 of 1907 colleges were flagged while SAT coverage was only 985, meaning the default view was likely discarding most of the dataset — and hiding good-value colleges — for cosmetic reasons. Confirmed on a gapped fixture: **11 of the top 20 colleges were missing SAT data and would previously have been dropped.**
- **`COA_COMPLETE` was always true.** It tested `COA.notna()`, but COA is built with `min_count=1` and falls back to tuition, so it was never null and `incomplete_coa` never fired. It now means *every* charge component was present. Without this, splitting the flags would have left `exclude_flagged` with nothing to do.
- **`/api/meta` reported a median the filter doesn't use.** It exposed `median_aid_share` (grant ÷ COA) while `mgi_at_least_median` applies a median of `MGI` (grant ÷ tuition). `median_mgi` is now reported alongside it, plus `data_gap_count` and `unscoreable_count`.

- **Net price dropped every public university.** The app read `NPT442` only, which covers private institutions; `NPIS442` carries the public (in-state) figure. Both have the same dictionary title, so nothing about the data looks wrong — the universe is just half missing. Coalescing the two reproduces the reference app's `colleges_in_dataset` (1907) and `sat_coverage` (985) **exactly**, from 1181/605 before. For a tool about affordability for middle-income families, publics were the wrong half to lose.

All six are covered by `backend/tests/test_scoring.py`.

### Still open

Ordered by how much they could distort results.

1. **COA vs net price comparability.** `DISCOUNT` and `NET_PRICE_RATIO` assume `COA` and the net-price variables cover the same basket of costs. IPEDS net price is defined against *total* cost of attendance including allowances this hand-summed COA doesn't reconstruct, so the two are probably not apples-to-apples.

   This is now the **only unexplained gap** against the reference app: with publics included, four of five `/api/meta` metrics match exactly, and `median_aid_share` is 0.343 against the reference's 0.3184. A larger denominator closes it, which points straight at COA. IPEDS publishes **`DRVIC2022`** ("Total cost of attendance: Academic year 2022-23"), almost certainly what the reference used. Switching to it would also retire the 174 `incomplete_coa` colleges. **Verify the variant matches the net-price basket before switching** — COA differs by in-state/out-of-state and on/off-campus, and public net price is in-state.
2. **Percent-scaling heuristic.** Dividing by 100 only when `max > 1.5` is fragile: a real dataset where every rate happens to be ≤ 1.5 (or already fractional) would be mis-scaled with no error. Prefer an explicit per-column declaration.
3. **Equal weighting is an assertion, not a finding.** ⅓/⅓/⅓ was chosen because the reference app described equal weight. Whether that produces sensible rankings on the real IPEDS data is untested — check the Value Score distribution and each component's correlation with the final rank.
4. **Weights are not configurable.** Exposing them (and reporting them in `/api/meta`) would make the methodology auditable instead of implicit.

---

## 7. API contract

- `GET /api/meta` — dataset stats (including `median_mgi`, the threshold `mgi_at_least_median` actually applies), default filter values, and the list of toggleable data dimensions.
- `GET /api/colleges?max_net_price=&mgi_at_least_median=&top_n=&exclude_flagged=` — ranked shortlist; each row has 24 fields (see `observed-api-contract.md`).
- `GET /api/rag/status` — `{ index_ready, api_key_set }`.
- `POST /api/rag/query` — body `{ question, unitids?, college_names? }` → `{ answer, sources, mode }`. Retrieval is scoped to the currently shown colleges.
- `GET /api/health` — liveness.

---

## 8. How to run

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
pytest                                 # 9 tests, no data files needed
```
The suite builds its fixtures in memory rather than reading `backend/data/`, because the generated sample data has no missing values and so exercises none of the flag/degradation logic. Don't "fix" a test by pointing it at the CSVs.

The AI feature works without a key (returns retrieved passages); set `ANTHROPIC_API_KEY` for synthesized answers.

> **Windows + old PowerShell:** `&&` is rejected — run the commands one per line. See §9.

---

## 9. Environment gotchas

Things that have actually broken this project, and the fix. Check here before debugging a setup problem from scratch. Local machine: **Windows**, project at `C:\Users\amatu\Downloads\merit-aid-app`.

### Windows / PowerShell

**`&&` is not a valid statement separator.** The installed PowerShell predates `&&` support, so chained commands fail with `The token '&&' is not a valid statement separator in this version`.

Run them one per line:
```powershell
cd backend
pip install pandas numpy
python scripts/make_sample_data.py
cd ..
docker compose up --build
```
(`;` also works as a separator, but it ignores failures — one-per-line is safer.)

### Python versions

**Local Python is 3.13; the project targets 3.12.** `pip install -r requirements.txt` fails locally on **scikit-learn** — there's no prebuilt wheel for 3.13 against the pinned version, so pip tries to compile from source and dies in ninja/MSVC.

You don't need the full install locally. Docker builds on `python:3.12-slim`, where wheels exist. Locally you only need enough to generate sample data:
```powershell
pip install pandas numpy
python scripts/make_sample_data.py
```

**`backend/myenv/` is a Python 3.13 venv** left in the project. It's gitignored, so harmless to the repo. It has `pandas`, `numpy`, `scikit-learn`, `fastapi` and `pytest` installed and is usable for running the test suite and uvicorn directly; just don't treat it as the project's target environment.

### Docker

**Docker Desktop must be running before any `docker` command.** Otherwise:
```
failed to connect to the docker API at npipe:////./pipe/dockerDesktopLinuxEngine
```
That is not a project error — open Docker Desktop, wait for the whale icon to report running (~30s), then retry.

**`frontend/nginx.conf` is required by the frontend image.** It has gone missing once (lost in a cleanup) and the build failed with:
```
COPY nginx.conf /etc/nginx/conf.d/default.conf: "/nginx.conf": not found
```
If you see that, the file is absent — recreate it. It serves the built SPA and proxies `/api/` to `http://backend:8000`. `frontend/.dockerignore` went missing the same way.

**The large-bundle warning on build is expected** — Plotly is ~4.8 MB minified (1.4 MB gzipped). Not an error; cosmetic only.

**`docker compose up --build` is for local development, not production.** It builds the same images you'd deploy, which makes it a good rehearsal, but it runs only on this machine with no load balancer or scaling. Production is the Terraform + GKE path in `DEPLOYMENT.md`.

### Ports

| Service | URL |
|---|---|
| Frontend (Docker) | http://localhost:8080 |
| Backend API | http://localhost:8000 |
| Frontend (Vite dev) | http://localhost:5173 |

In Docker the frontend proxies `/api` to the backend container by service name (`backend:8000`). In Vite dev mode the proxy is configured in `vite.config.js`. Either way the browser only ever calls same-origin `/api/*` — don't hard-code `localhost:8000` in frontend code.

### Data

**The 7 IPEDS filenames are exact.** Drop them in `backend/data/`:
```
HD2022.csv  SFA2122.csv  IC2022_AY.csv  ADM2022.csv
DRVADM2022.csv  DRVGR2022.csv  IC2022Mission.csv
```
A missing file raises a `FileNotFoundError` naming the file — that error means a name mismatch, not corrupt data.

**`build_dataset()` is `lru_cache`d.** The dataset loads once per process, so swapping CSVs has **no effect until the backend restarts.** If your numbers don't change after replacing the data, that's why.

**`IC2022Mission.csv` does not exist.** IPEDS published `IC{year}Mission` for **2004–2007 only**; there is no 2022 equivalent anywhere in the catalog, and the only "mission" hits in the IC2022/HD2022 dictionaries are substrings of "admission". The reference app's claim to index official mission statements from this file therefore cannot be literally true. The RAG feature currently runs on generated text — see §10.

**Use the revised files.** IPEDS archives carry both provisional and revised releases (`adm2022.csv` and `adm2022_rv.csv`). Prefer `_rv` (revised September 2024). For the columns this app reads the counts are identical either way.

**Sample vs real data.** `scripts/make_sample_data.py` writes 300 synthetic colleges so the app runs without the real dataset. Sample data will produce plausible-looking but meaningless rankings — check which one you're on before drawing any conclusion from the output. Real files overwrite the samples (same names).

**Sample data cannot validate the pipeline.** It has no missing values, and its net price is constructed from the same components the app sums into `COA` — so it is circular with the formula it is meant to test. To exercise the flag paths, generate a dataset with realistic missingness.

### AI / RAG feature

**It runs without an API key.** `/api/rag/query` returns the retrieved mission passages with a note instead of a synthesized answer. Set `ANTHROPIC_API_KEY` (in `.env` locally, Secret Manager in GCP) to get Claude-generated answers.

**Retrieval silently falls back to TF-IDF** if `sentence-transformers` isn't installed (it's commented out in `requirements.txt` because it pulls in torch). The response's `mode` field reports which path ran — `sentence-transformers` or `tfidf-fallback`. Retrieval quality differs noticeably, so check `mode` before judging answer quality.

**TF-IDF can dead-end.** If a question shares no vocabulary with the scoped missions, similarity is 0, the `sims[i] <= 0` guard drops every candidate, and the user sees "No relevant mission statements found" even though those colleges do have missions. Real embeddings wouldn't do this.

**The index is built at startup** and persisted to `INDEX_DIR`. `/api/rag/status` reports `index_ready` and `api_key_set`.

### Secrets & ignored paths

Never commit or log: `.env`, `backend/data/`, `backend/index/`, `backend/myenv/`, `frontend/node_modules/`. All are already in `.gitignore` — keep it that way. `ANTHROPIC_API_KEY` comes from the environment or a Kubernetes secret, never source.

### Git

**Only Claude Code commits.** Claude Cowork has equal file and console access but runs no git write commands, and Claude Code owns `.gitignore`, hooks, and CI config. See "Who works on this" in `HANDOFF.md`.

The repo exists and is pushed to github.com/HasanZaidi1980/merit-aid-app on `main`.

### Cloud (not yet exercised)

Nothing has been deployed yet, so none of the GCP steps are battle-tested. Three things to remember when you get there:

- **The backend manifest mounts an `emptyDir` for data**, so the pod boots with no CSVs and `/api/meta` will fail while `/api/health` still passes. Fix before deploying.
- **GKE plus a load balancer bills continuously.** Run the teardown in `DEPLOYMENT.md` (`kubectl delete -f deploy/k8s/` then `terraform destroy`) when a demo is done.
- **Delete the load balancer before `terraform destroy`**, or the destroy can hang on resources the Ingress still holds.

---

## 10. Known gaps, risks & things to verify

1. **Scoring fidelity** — the Value Score/percentile logic is reconstructed; confirm it's statistically sound (NaN handling in percentile ranks, ties, whether equal weighting is defensible) and matches the intended definition. §6 tracks resolved vs open.
2. **COA construction** — `COA` is summed from tuition + charge components when present, else falls back to tuition. Verify this matches how net price is measured, so `Discount` and `Aid Share` are apples-to-apples. This is §6's top open item.
3. **Reference app showed intermittent `502`s** on `/api/*` — worth reproducing under load; check backend startup time, resource limits, readiness probes. The likely cause is in the manifests, not the code: see §9 Cloud and `PROJECT_STATE.md` Phase 7.
4. **Test coverage is partial** — `backend/tests/test_scoring.py` covers scoring, the flag split and net-price coalescing (9 tests). Still missing: `data.py` load/merge/clean, API tests for malformed params, and the RAG endpoint with and without a key.
5. **RAG fallback** — if `sentence-transformers` isn't installed it silently uses TF-IDF; retrieval quality differs. Confirm which is intended and make it explicit. See §9.
5a. **The RAG feature has no real data source.** `IC2022Mission.csv` does not exist — IPEDS stopped publishing mission statements after 2007 (§9). The options are the 2007 file (real but 15 years stale, and coverage against the 2022 universe is unmeasured), another source, or keeping generated text and labelling it plainly in the UI. Decide before presenting the feature as fact.
6. **Frontend bundle is large** (Plotly). Fine for a demo; could be code-split.
7. **No error states in the UI** — `getMeta()` has no `.catch()`, so a backend failure leaves the page on a permanent "Loading…" with no retry. Given the known 502 risk, this is the most likely failure a real user would hit.
8. **Percentage scaling** — admissions/graduation rates are divided by 100 only when values look like percentages; check this heuristic against the real IPEDS files.

---

## 11. Suggested tasks

Task *ideas*, not a sequenced plan — `PROJECT_STATE.md` owns the roadmap.

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

## 12. Where to change things

| Change | File |
|---|---|
| Any formula, the weights, the ranking order | `backend/app/scoring.py` |
| Inputs, cleaning, COA construction, scaling | `backend/app/data.py` |
| Default filter values | `backend/app/config.py` (`DEFAULTS`) |
| Fields exposed by the API | `backend/app/main.py` (`ROW_FIELDS`) |
| The 8 expected filenames (e.g. a data-year upgrade) | `backend/app/config.py` (`FILES`) **and** `backend/scripts/make_sample_data.py` |

Changing `ROW_FIELDS` or renaming a column is a **breaking API change** — the frontend reads these names directly. See `observed-api-contract.md`.

Changing a formula means updating §5 in the same turn, and moving the entry in §6 if it resolves an open item.

---

## 13. File map

```
merit-aid-app/
  PROJECT_BRIEF.md          ← this file. Architecture, data, formulas, gotchas, tasks
  PROJECT_STATE.md          status at a glance + phased roadmap, incl. the 2023-24 data upgrade
  HANDOFF.md                current status + how Claude Code and Cowork split the work
  README.md                 how to run
  ANALYSIS.md               what the live reference app is + cloud/hosting findings
  observed-api-contract.md  exact endpoints + the 24-field schema this app returns
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
