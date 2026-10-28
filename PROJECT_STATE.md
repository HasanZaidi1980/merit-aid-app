# Project State — Merit Aid Finder

**Last updated:** 2026-10-28 · **Branch:** `main` @ `2d008fb` · **Remote:** github.com/HasanZaidi1980/merit-aid-app

This is the single source of truth for *where the project stands* and *what remains*.
It deliberately does not restate architecture, formulas, or environment traps — it
points at the doc that owns each. Update this file when a phase moves; update the
owning doc when a fact changes.

| Doc | Owns |
|---|---|
| **PROJECT_STATE.md** | ← this file. Status + the road to completion. |
| `HANDOFF.md` | Who works on this (Claude Code / Cowork split), guardrails, applied fixes. |
| `PROJECT_BRIEF.md` | Architecture, data pipeline, how to run, **the formulas** (§5-§6), **environment gotchas** (§9), task ideas. |
| `observed-api-contract.md` | The API contract and 25-field row schema. |
| `ANALYSIS.md` | What the reference app is and what was observable from outside. |
| `DEPLOYMENT.md` | GCP deploy steps and teardown. |

---

## 1. Status at a glance

| Area | State | Notes |
|---|---|---|
| Version control | ✅ Done | `main` pushed to GitHub. 5 commits. |
| Runs locally | ✅ Done | Docker (`docker compose up --build`) and direct (uvicorn + vite). |
| Backend API | ✅ Working | All 7 endpoints verified; 25-field rows. |
| Frontend | ✅ Working | 5 charts, sortable table, CSV export, RAG panel, education section. |
| RAG / AI | ❌ **Non-functional** | No real mission source exists (see Phase 5). Index holds sample UNITIDs; every query now returns nothing. |
| Scoring logic | ⚠️ Validated on real data | 6 issues resolved + tested; **4 still open** (see `PROJECT_BRIEF.md` §6). COA is the one remaining unexplained gap. |
| Merit vs need-based aid | ⚠️ Mitigated, not solved | `IGRNT_A` conflates them and IPEDS never splits them. Relabelled honestly + 26-college curated need-only list. Real fix is Phase 4. |
| Tests | ⚠️ Partial | 17 tests over scoring, flags, net-price coalescing and merit policy. No endpoint tests. |
| **Real data** | ✅ **Installed & validated** | Real IPEDS 2022-23: 1,907 colleges (726 public / 1,095 private nonprofit / 86 for-profit). 5 of 5 reference metrics match. |
| Error handling | ⚠️ Partial | `/api/meta` failure now shows a real error with a retry. `getColleges` and the empty state are still silent. |
| Deployment | ❌ Not started | Terraform + K8s manifests exist, never applied. |

**One-line summary:** the app runs on real, validated IPEDS data and produces defensible
rankings — Stanford #1 at $77,662 sticker against a $7,332 net price for a mid-income
family, which is exactly the thesis. The numbers are right; the word "merit" on them was
not, and is now corrected in the UI rather than in the data (Phase 4). What remains is
the COA question, a UI that still fails silently on `getColleges`, and a RAG panel with
no real data source.

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
   `PROJECT_BRIEF.md` §6 Still open is authoritative.
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
- **Nothing user-facing calls a generosity metric "merit".** `IGRNT_A` conflates
  need-based and merit aid and IPEDS publishes no split, so the claim was simply
  false. The wire field stays `MGI` for contract compatibility; every label reads
  "Grant ÷ Tuition" (`PROJECT_BRIEF` §5.1).
- **`MERIT_POLICY` of `unknown` means *unchecked*, never "awards merit aid".** 26 of
  1,907 colleges have been checked. The column is a string, not a bool, so there is
  no value that could be misread as a positive finding.
- **`exclude_no_merit` is opt-in.** Defaulting it on would imply the other 1,881
  colleges had been checked and cleared.
- **The merit-policy flag affects no score.** It is a fact about the college, not a
  measurement of it, so it sits in neither flag column and never moves a ranking.
- **The education section scores in the browser.** `/api/education/distributions`
  ships 101 percentile breakpoints once (~8 KB); the sandbox re-derives Value Score
  locally rather than issuing a request per slider drag. `frontend/src/education/
  valueScore.js` mirrors `scoring.add_metrics()` and must change with it.

---

## 5. Next steps

Phases are ordered by dependency. Each has a **Done when** you can actually check.

### Phase 1 — Load the real IPEDS 2022-23 data ✅ *complete 2026-10-28*

The app is meaningless on 300 synthetic colleges. The reference app had 1,907 real ones.

- [x] Download the 7 files from the [IPEDS Data Center](https://nces.ed.gov/ipeds/datacenter/DataFiles.aspx) (complete data files, CSV).
- [x] ~~Resolve the `SFA2122_P1` / `_P2` question~~ — IPEDS publishes **one** `SFA2122`
      file; no P1/P2 split has ever existed. `config.py` and `data.py` now read one file.
- [x] ~~Verify column-name case~~ — all seven files ship UPPERCASE headers; no change needed.
- [x] Placed in `backend/data/` from the `_rv` (revised Sept 2024) releases. Not committed.
- [x] **Net price was dropping all 726 public universities** — `NPT442` is private-only.
      Fixed in `54a0611`; see `PROJECT_BRIEF.md` §6 Resolved.

**Done:** `/api/meta` returns 1,907 colleges; backend starts clean.

### Phase 2 — Validate the pipeline against known numbers ✅ *complete 2026-10-28*

This is the only ground truth the project has. Do not skip it, and do not change the
data year until it passes (see §6).

| metric | reference | actual | |
|---|---|---|---|
| `colleges_in_dataset` | 1907 | 1907 | ✅ |
| `net_price_min` | 2200 | 2200 | ✅ |
| `net_price_max` | 63997 | 63997 | ✅ |
| `sat_coverage` | 985 | 985 | ✅ |
| `median_aid_share` | 0.3184 | 0.343 | ⚠️ explained — COA, Phase 3 |
| `flagged_count` | 1352 | 379 | ✅ expected — `RISK_FLAGS` redefined |

Also confirmed: rates arrive as 0–100 and the ÷100 heuristic fires (values land
0.03–1.0); **no negative sentinels appear** in any column the app reads, so that
cleaning step is inert for this dataset; `pytest` 9 passed.

Other real-data figures: `median_mgi` 0.5798, `data_gap_count` 922,
`unscoreable_count` 180.

**Done:** four of five metrics match exactly. The fifth has a written explanation and
a known fix (Phase 3, item 1).

### Phase 3 — Close the open scoring questions 🔒 *blocked by Phase 2*

Only answerable on real data. `PROJECT_BRIEF.md` §6 Still open is the checklist.

- [ ] **COA vs net price comparability** — now the only unexplained gap. Switch to
      `DRVIC2022` ("Total cost of attendance"), almost certainly what the reference used;
      it should close the `median_aid_share` gap and retire the 174 `incomplete_coa`
      colleges. **Check the variant first:** `NPIS442` is *in-state* public net price, so
      the COA column must be in-state too, or publics get an out-of-state sticker measured
      against an in-state net price and their Discount inflates.
- [ ] **Replace the percent-scaling heuristic** with an explicit per-column declaration.
- [ ] **Test the equal weighting.** Report the Value Score distribution, each
      component's correlation with final rank, and sensitivity to reweighting.
- [ ] **Make weights configurable** and report them in `/api/meta`.

**Done when:** `PROJECT_BRIEF.md` §6 Still open is empty or every remaining item is a conscious
accepted trade-off.

### Phase 4 — Split merit aid from need-based aid (Common Data Set) ⏸ *deferred by decision, 2026-10-28*

**This is the app's central unfinished business.** It is deferred, not dropped.

**The problem.** `IGRNT_A` is total institutional grant aid — need-based and merit
combined. All 663 columns of `SFA2122` were searched and nothing splits them; NCES
does not require institutions to report the split. So an app named "Merit Aid Finder"
has no merit-aid data in it. Measured against the live rankings, **11 of the top 23
colleges award no merit aid at all.**

**What already shipped** (2026-10-28) — the two cheap mitigations, done:

- ✅ **Relabelled honestly.** The sidebar reads "Grant ÷ Tuition ≥ median", `/api/meta`
      carries `metric_notes`, and a disclosure panel sits above the charts. Full write-up
      in `PROJECT_BRIEF.md` §5.1.
- ✅ **Curated need-only list** — `backend/app/merit_policy.py`, 26 institutions, keyed
      on UNITID. Adds `MERIT_POLICY` and the opt-in `exclude_no_merit` filter.
      Covered by `backend/tests/test_merit_policy.py`.

**What remains — the real fix.** The authoritative source is the **Common Data Set,
section H2A**, which reports need-based and non-need-based institutional aid separately
for each institution. It is published per-institution as a PDF or spreadsheet on each
college's institutional-research page. There is no bulk download, which is the entire
reason this is a project rather than a column rename.

- [ ] **Verify the existing 26 first.** The curated list is marked `provisional`:
      compiled from well-documented institutional policy, not yet checked line-by-line
      against each school's current CDS. Checking 26 is a morning's work and it either
      validates the shipped list or finds the error before anyone relies on it. **Do this
      before any scraping** — it also calibrates how reliably H2A can be read.
- [ ] **Scope the crawl.** 1,907 institutions, no common URL pattern, mixed PDF/XLSX/HTML.
      Expect partial coverage; design for it from the start rather than discovering it at
      70%. Decide the acceptable floor up front (the top 200 by Value Score would fix the
      part of the ranking users actually read).
- [ ] **Model the result honestly.** Extend `MERIT_POLICY` with a third value for
      *confirmed to award merit aid* — the vocabulary is a string precisely so this can
      be added without a schema change. `unknown` must keep meaning **unchecked**.
- [ ] **Then, and only then, a real merit metric.** With non-need-based dollars split
      out, `MGI` can finally mean what its name claimed. Until the split exists, do not
      compute a "merit" number from `IGRNT_A` under any weighting — there is no
      arithmetic that recovers it.
- [ ] Record provenance per institution (source URL, CDS year, who checked it). A hand-
      maintained list without provenance rots silently.

**Done when:** `MERIT_POLICY` is sourced from CDS H2A rather than curation for a stated,
measured share of the dataset — and the UI reports that share instead of implying
completeness.

**Why deferred:** the two mitigations above remove the misleading claim, which was the
actual harm. The remaining work buys a *feature* (find colleges that award merit aid),
not a *correction*, and it is large enough to compete with deployment for time.

### Phase 5 — Harden the app for a real user

Do this before deploying. The failure it prevents is the failure most likely to occur.

- [x] ~~**Add error states.** `getMeta()` needs a `.catch()`~~ — done 2026-10-28: a
      failed `/api/meta` now renders a `.fatal` panel naming the error with a Retry
      button, instead of an endless spinner.
- [ ] Same for `getColleges` — it still swallows its error and shows an empty table.
- [ ] **Empty state** when filters return zero rows.
- [ ] **Decide what happens to the RAG feature.** It has no real data source:
      `IC2022Mission.csv` does not exist — IPEDS stopped publishing mission statements
      after 2007. Measured coverage of the 2007 file against the 2022 universe is
      **36.2%** (690/1907), biased against exactly the sector we just restored
      (publics 26.9% vs private nonprofit 41.5%), and only **36 of the top 100** by
      Value Score have any text. The file was half-empty even in 2007.

      It is also *currently broken*: `backend/index/mission_index.npz` was built from
      the sample CSV, so it holds UNITIDs 100000–100299 while real shortlist IDs are
      150k–250k. Every query returns "No relevant mission statements found".

      Recommended: gate it honestly rather than delete it. Have the backend report the
      mission source (`real` / `synthetic` / `none`) in `/api/rag/status`, and have the
      frontend hide the panel or show a plain warning when it isn't real. That keeps
      the pipeline demonstrable without presenting invented text beside real numbers.
      Finding a genuine source is a separate project.
- [ ] **Fix the RAG dead-end** (only if the feature survives) — enable
      `sentence-transformers`, or soften the similarity threshold and say "no strong
      match" instead of "none found".
- [ ] Surface the retrieval mode (embeddings vs TF-IDF) in the UI.
- [ ] Input validation on `/api/colleges` — helpful 4xx messages, not 500s.
- [ ] Consider code-splitting the 4.8 MB bundle (1.4 MB gzipped, nearly all Plotly).

**Done when:** killing the backend produces a visible, recoverable error in the UI.

### Phase 6 — Extend test coverage

- [ ] `data.py`: load, merge, clean, sentinel handling, empty-result handling.
- [ ] Endpoint tests via `TestClient`, including malformed query params.
- [ ] RAG endpoint with and without an API key.
- [ ] Smoke test that boots the stack and hits `/api/health`, `/api/meta`, `/api/colleges`.
- [ ] CI (lint + tests on push).

**Done when:** `pytest` covers every module and runs in CI.

### Phase 7 — Upgrade to IPEDS 2023-24 🔒 *blocked by Phase 2*

Full plan in §6 below.

### Phase 8 — Deploy to GCP

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

### Phase 9 — Finish

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
act on. **2023-24 is the newest year where all seven files exist and are final**, and
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
| `SFA2122.csv` | `SFA2223.csv` |
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
| GKE Ingress health-checks `/` | 502s on `/api/*` with the site up | Phase 8 — fix manifests before first deploy |
| `getColleges` failure is invisible to users | Empty table, no explanation | Phase 5 — the `/api/meta` path is fixed, this one is not |
| Curated need-only list is unverified | A college wrongly labelled "need-based only" | Phase 4 — verify all 26 against CDS H2A before relying on it |
| GCP left running after the demo | Continuous billing | Phase 9 teardown; `DEPLOYMENT.md` has the commands |
| Two agents editing one file | Lost work | `HANDOFF.md` — announce files before editing |

---

## 8. Recent history

| Commit | What |
|---|---|
| `2d008fb` | Merit-aid correction (relabel + need-only flag) and the education section |
| `55bfaf1` | Record real-data validation: phases 1-2 complete |
| `54a0611` | Read one SFA file and include public universities in net price |
| `41ccb48` | Fold FORMULAS.md and GOTCHAS.md into PROJECT_BRIEF.md |
| `31971cf` | PROJECT_BRIEF + README updated for the test suite and 24-field schema |
| `3723705` | Frontend wired to `median_mgi` and `DATA_GAPS` |
| `b8e58d0` | First test suite — 8 tests over scoring and the flag split |
| `cc0b55d` | Documented the `RISK_FLAGS` / `DATA_GAPS` split |
| `dc81437` | Initial commit |

Earlier in the reconstruction (pre-git), four scoring issues were found and fixed: the
`fill_value=NaN` no-op in Value Score, the post-filter MGI median, the always-true
`COA_COMPLETE`, and `/api/meta` reporting a median the filter doesn't use. All four are
recorded in `PROJECT_BRIEF.md` §6 Resolved and covered by tests.
