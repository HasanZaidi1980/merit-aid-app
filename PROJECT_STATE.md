# Project State — Merit Aid Finder

**Last updated:** 2026-10-28 · **Branch:** `main` @ `31971cf` · **Remote:** github.com/HasanZaidi1980/merit-aid-app

This is the single source of truth for *where the project stands* and *what remains*.
It deliberately does not restate architecture, formulas, or environment traps — it
points at the doc that owns each. Update this file when a phase moves; update the
owning doc when a fact changes.

| Doc | Owns |
|---|---|
| **PROJECT_STATE.md** | ← this file. Status + the road to completion. |
| `HANDOFF.md` | Who works on this (Claude Code / Cowork split), guardrails, applied fixes. |
| `PROJECT_BRIEF.md` | Architecture, data pipeline, how to run, task ideas. |
| `FORMULAS.md` | Every metric definition; resolved vs still-open scoring questions. |
| `observed-api-contract.md` | The API contract and 24-field row schema. |
| `GOTCHAS.md` | Environment traps (PowerShell, Python versions, Docker, ports, secrets). |
| `ANALYSIS.md` | What the reference app is and what was observable from outside. |
| `DEPLOYMENT.md` | GCP deploy steps and teardown. |

---

## 1. Status at a glance

| Area | State | Notes |
|---|---|---|
| Version control | ✅ Done | `main` pushed to GitHub. 5 commits. |
| Runs locally | ✅ Done | Docker (`docker compose up --build`) and direct (uvicorn + vite). |
| Backend API | ✅ Working | All 5 endpoints verified; 24-field rows. |
| Frontend | ✅ Working | 5 charts, sortable table, CSV export, RAG panel. |
| RAG / AI | ⚠️ Works, degraded | Runs on TF-IDF fallback, not embeddings. Live Claude answers confirmed. |
| Scoring logic | ⚠️ Partly validated | 4 issues resolved + tested; **4 still open** (see `FORMULAS.md`). |
| Tests | ⚠️ Partial | 8 tests over scoring/flags. No `data.py` or endpoint tests. |
| **Real data** | ❌ **Not yet** | Still 300 synthetic colleges. Download in progress (Cowork). |
| Error handling | ❌ Missing | Backend failure = permanent "Loading…" spinner. |
| Deployment | ❌ Not started | Terraform + K8s manifests exist, never applied. |

**One-line summary:** the app is built, version-controlled and demonstrably working,
but it is still running on fake data and would fail silently in front of a user if the
backend hiccuped. Those two things are the gate to everything else.

---

## 2. What is verified

Confirmed by running it, not by reading it:

- `docker compose up --build` builds both images and serves on :8080.
- Direct run works: uvicorn on :8000, Vite on :5173 with the `/api` proxy.
- `/api/health`, `/api/meta`, `/api/colleges`, `/api/rag/status`, `/api/rag/query` all
  return 200 with the expected shapes. Rows carry 24 fields including `DATA_GAPS`.
- RAG answers end-to-end against a live `ANTHROPIC_API_KEY` using `claude-sonnet-5`,
  correctly citing colleges by mission theme.
- The flag split behaves as designed. Against a fixture with realistic missingness,
  **11 of the top 20 colleges were missing SAT data and were correctly kept** — under
  the previous `RISK_FLAGS` behaviour all 11 would have been silently dropped.
- `pytest` — 8 passing, no data files required.
- Frontend builds clean (`npm run build`).

## 3. What is unverified or missing

1. **Everything data-dependent.** Sample data has no missing values, no outliers, and
   its net price is constructed from the same components the app sums into `COA` — so
   it is circular with the formula it is meant to test.
2. **Four open scoring questions** — COA vs net price comparability, the percent-scaling
   heuristic, whether equal weighting is defensible, and non-configurable weights.
   `FORMULAS.md` §Still open is authoritative.
3. **No error state anywhere in the UI.** `getMeta()` has no `.catch()`; a failed call
   leaves `meta` null and the page renders "Loading…" forever.
4. **RAG runs on TF-IDF.** `sentence-transformers` is commented out of
   `requirements.txt`, so retrieval is lexical. A question sharing no vocabulary with
   the missions returns "No relevant mission statements found" even when relevant
   colleges exist.
5. **Thin test coverage.** Nothing covers `data.py` (load, merge, clean, sentinels) or
   the endpoints.
6. **Deployment never exercised.** See §6 for the 502 hypothesis that should be fixed
   before the first deploy, not after.

---

## 4. Decisions already made

Settled. Don't relitigate without a reason.

- **This is a reconstruction, and correctness beats fidelity.** The original source was
  never available. Where behaviour was inferred, prefer making it right and documented
  over matching an unknown original (`PROJECT_BRIEF` §2).
- **Only Claude Code commits.** Cowork has equal access to files and the console but
  runs no git write commands (`HANDOFF.md` §Who works on this).
- **`RISK_FLAGS` vs `DATA_GAPS`.** Scoring-relevant problems drop a college;
  display-only gaps never do. `exclude_flagged` gates on the former alone.
- **Unscoreable rows are dropped, never imputed.** Crediting a non-reporting college
  with a median graduation rate would let it outrank honest reporters.
- **The MGI median is dataset-wide**, not recomputed after filtering.
- **The API may exceed the reference app's 23 fields.** Additions are backward
  compatible; nothing is renamed or removed.

---

## 5. Next steps

Phases are ordered by dependency. Each has a **Done when** you can actually check.

### Phase 1 — Load the real IPEDS 2022-23 data ⏳ *in progress (Cowork)*

The app is meaningless on 300 synthetic colleges. The reference app had 1,907 real ones.

- [ ] Download the 8 files from the [IPEDS Data Center](https://nces.ed.gov/ipeds/datacenter/DataFiles.aspx) (complete data files, CSV).
- [ ] Verify column-name case before renaming. `data.py` uppercases headers **only** for
      `HD2022`; the other seven are read with exact uppercase names and will `KeyError`.
- [ ] Resolve the `SFA2122_P1` / `_P2` question — the app expects two files; confirm what
      IPEDS actually publishes rather than guessing.
- [ ] Place in `backend/data/` under the exact names in `config.py`. **Never commit them.**

**Done when:** `/api/meta` returns ~1,900 colleges and the backend starts without error.

### Phase 2 — Validate the pipeline against known numbers 🔒 *blocked by Phase 1*

This is the only ground truth the project has. Do not skip it, and do not change the
data year until it passes (see §6).

- [ ] Compare `/api/meta` against the reference app's observed values:
      `colleges_in_dataset` 1907 · `median_aid_share` 0.3184 · `net_price_min` 2200 ·
      `net_price_max` 63997 · `sat_coverage` 985.
- [ ] Record every delta with an explanation. `flagged_count` will **not** match the
      reference's 1352 — the `RISK_FLAGS` definition changed deliberately.
- [ ] Confirm `ADMISSIONS_RATE` / `GRAD_RATE` arrive as percentages and the ÷100
      heuristic fires correctly.
- [ ] Check sentinel handling (−1/−2/−3/−9 and `.`) against the real dictionaries.
- [ ] `pytest` still green.

**Done when:** every metric either matches the reference or has a written explanation.

### Phase 3 — Close the open scoring questions 🔒 *blocked by Phase 2*

Only answerable on real data. `FORMULAS.md` §Still open is the checklist.

- [ ] **COA vs net price comparability.** Confirm against the IPEDS dictionary whether
      `NPT442` is defined against a cost basket `COA` doesn't reconstruct (fees,
      other expenses). If so, fix `COA` or document the bias explicitly.
- [ ] **Replace the percent-scaling heuristic** with an explicit per-column declaration.
- [ ] **Test the equal weighting.** Report the Value Score distribution, each
      component's correlation with final rank, and sensitivity to reweighting.
- [ ] **Make weights configurable** and report them in `/api/meta`.

**Done when:** `FORMULAS.md` §Still open is empty or every remaining item is a conscious
accepted trade-off.

### Phase 4 — Harden the app for a real user

Do this before deploying. The failure it prevents is the failure most likely to occur.

- [ ] **Add error states.** `getMeta()` needs a `.catch()`; show a real error with a
      retry instead of an endless spinner. Same for `getColleges`.
- [ ] **Empty state** when filters return zero rows.
- [ ] **Fix the RAG dead-end** — enable `sentence-transformers`, or soften the
      similarity threshold and say "no strong match" instead of "none found".
- [ ] Surface the retrieval mode (embeddings vs TF-IDF) in the UI.
- [ ] Input validation on `/api/colleges` — helpful 4xx messages, not 500s.
- [ ] Consider code-splitting the 4.8 MB bundle (1.4 MB gzipped, nearly all Plotly).

**Done when:** killing the backend produces a visible, recoverable error in the UI.

### Phase 5 — Extend test coverage

- [ ] `data.py`: load, merge, clean, sentinel handling, empty-result handling.
- [ ] Endpoint tests via `TestClient`, including malformed query params.
- [ ] RAG endpoint with and without an API key.
- [ ] Smoke test that boots the stack and hits `/api/health`, `/api/meta`, `/api/colleges`.
- [ ] CI (lint + tests on push).

**Done when:** `pytest` covers every module and runs in CI.

### Phase 6 — Upgrade to IPEDS 2023-24 🔒 *blocked by Phase 2*

Full plan in §6 below.

### Phase 7 — Deploy to GCP

Fix the manifests first — they contain the probable cause of the reference app's 502s.

- [ ] **`emptyDir` for data.** `deploy/k8s/backend.yaml` mounts an empty volume, so the
      pod boots with no CSVs. Use a GCS CSI mount or an init container.
- [ ] **No NEG annotation** on the backend Service, so GKE Ingress health-checks `/` on
      the node port — which FastAPI doesn't serve. Add
      `cloud.google.com/neg: '{"ingress": true}'`, or a BackendConfig pointing the health
      check at `/api/health`.
- [ ] Add a `startupProbe`; move off the deprecated `@app.on_event("startup")` to a
      lifespan handler.
- [ ] Consider `replicas: 2` so a restart isn't an outage.
- [ ] Then follow `DEPLOYMENT.md`: Terraform → upload data → secret → build/push → apply.
- [ ] **Tear down when the demo is over.** GKE + a load balancer bill continuously.

**Done when:** the external IP serves the app and `/api/*` survives a pod restart.

### Phase 8 — Finish

- [ ] README reflects the deployed URL and the real data year.
- [ ] `PROJECT_STATE.md` (this file) marked complete.
- [ ] Teardown verified — no lingering GCP billing.

---

## 6. The IPEDS 2023-24 upgrade plan

### Why 2023-24 and not newer

Checked against the [IPEDS Data Release Schedule](https://nces.ed.gov/ipeds/survey-components/data-release-schedule) on 2026-10-28:

| Collection year | IC / HD | SFA, ADM, GR |
|---|---|---|
| **2023-24** | Final (Sep 23, 2025) | **Final** (Dec 9, 2025) |
| 2024-25 | Final (Sep 8, 2026) | **Provisional** (Dec 9, 2025) |
| 2025-26 | Provisional (Jul 28, 2026) | **Not released** |

There is no complete "2025" dataset — the winter-survey components this app depends on
most (aid, admissions, graduation rates) don't exist for 2025-26 yet. 2024-25 would be
one year fresher but its aid and admissions data are provisional and subject to
revision, which is the wrong trade for an app that outputs dollar figures families may
act on. **2023-24 is the newest year where all eight files exist and are final**, and
it is still two collection cycles newer than what the app uses now.

### Why it must wait for Phase 2

Phase 2 validates the pipeline by reproducing the reference app's published numbers,
which are 2022-23. Change the data year first and every discrepancy becomes
unattributable — a merge bug, a renamed column, and a genuine year-over-year change all
look identical. Validate on 2022-23, *then* upgrade, so any diff is a real-world change
you can explain.

### Expected file mapping

Following the existing convention (collection year 2022-23 → `HD2022`, with SFA lagging
one year → `SFA2122`). **Verify against the Data Center before relying on this:**

| Current | Expected 2023-24 |
|---|---|
| `HD2022.csv` | `HD2023.csv` |
| `SFA2122_P1.csv` | `SFA2223_P1.csv` |
| `SFA2122_P2.csv` | `SFA2223_P2.csv` |
| `IC2022_AY.csv` | `IC2023_AY.csv` |
| `ADM2022.csv` | `ADM2023.csv` |
| `DRVADM2022.csv` | `DRVADM2023.csv` |
| `DRVGR2022.csv` | `DRVGR2023.csv` |
| `IC2022Mission.csv` | `IC2023Mission.csv` |

Note SFA always lags the charges data by a year — that's IPEDS, not a bug in the app.

### Steps

1. **Diff the dictionaries first.** Download both years' Excel dictionaries and compare
   the columns the app reads: `IGRNT_A`, `NPT442`, `TUITION2`, `CHG4AY3`, `CHG5AY3`,
   `CHG6AY3`, `CHG7AY3`, `SATVR75`, `SATMT75`, `DVADM01`, `GBA4RTT`, `ICLEVEL`,
   `HDEGOFR1`, `CONTROL`. Report any rename, redefinition or unit change **before**
   touching code.
2. **Download** the 2023-24 complete data files (CSV, final release).
3. **Update the filenames** — 8 strings in [`config.py:25-32`](backend/app/config.py#L25-L32)
   and the matching 8 in [`scripts/make_sample_data.py`](backend/scripts/make_sample_data.py),
   so the sample generator keeps producing files the loader can find.
4. **Update display copy** — the "IPEDS 2022-23" strings in `frontend/src/App.jsx`,
   `PROJECT_BRIEF.md` and `ANALYSIS.md`.
5. **Run `pytest`.** Fixtures are in-memory and year-agnostic, so a failure here means
   the swap broke something real.
6. **Compare old vs new `/api/meta`** side by side: college count, median aid share, net
   price range, SAT coverage, flagged count. Explain each movement.
7. **Spot-check the top 20.** Large rank changes should trace to real changes in aid or
   price, not to a column that quietly changed meaning.
8. **Commit on its own branch**, separate from any code change, so the ranking movement
   is attributable to the data alone.

### Set expectations on one metric

`GBA4RTT` is a **4-year** graduation rate, so it describes a cohort that enrolled four
or more years before collection. It is structurally backward-looking whichever release
you use. Fresher data meaningfully improves prices and aid; it barely moves grad rates.

### Rollback

Keep the 2022-23 CSVs in a separate local folder (not the repo — they're gitignored).
Reverting is: restore those files and revert the filename commit.

**Done when:** the app serves 2023-24 data, `/api/meta` movements are all explained, and
`pytest` is green.

---

## 7. Known risks

| Risk | Impact | Mitigation |
|---|---|---|
| Real IPEDS column names differ from the hardcoded ones | Backend won't start | Phase 1 verification step; report, don't silently rename |
| `COA` understates the real cost basket | Biases `DISCOUNT` and `AID_SHARE` on every row | Phase 3, item 1 — highest-priority open question |
| GKE Ingress health-checks `/` | 502s on `/api/*` with the site up | Phase 7 — fix manifests before first deploy |
| Backend failure is invisible to users | Permanent spinner, no recovery | Phase 4 — add error states |
| GCP left running after the demo | Continuous billing | Phase 8 teardown; `DEPLOYMENT.md` has the commands |
| Two agents editing one file | Lost work | `HANDOFF.md` — announce files before editing |

---

## 8. Recent history

| Commit | What |
|---|---|
| `31971cf` | PROJECT_BRIEF + README updated for the test suite and 24-field schema |
| `3723705` | Frontend wired to `median_mgi` and `DATA_GAPS` |
| `b8e58d0` | First test suite — 8 tests over scoring and the flag split |
| `cc0b55d` | Documented the `RISK_FLAGS` / `DATA_GAPS` split |
| `dc81437` | Initial commit |

Earlier in the reconstruction (pre-git), four scoring issues were found and fixed: the
`fill_value=NaN` no-op in Value Score, the post-filter MGI median, the always-true
`COA_COMPLETE`, and `/api/meta` reporting a median the filter doesn't use. All four are
recorded in `FORMULAS.md` §Resolved and covered by tests.
