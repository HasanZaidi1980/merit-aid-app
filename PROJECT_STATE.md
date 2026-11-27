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
| Version control | ✅ Done | `main` pushed to GitHub, protected, with CI on every push. |
| Runs locally | ✅ Done | Docker (`docker compose up --build`) and direct (uvicorn + vite). |
| Backend API | ✅ Working | 5 endpoints, 27-field rows, bounded query params, 503 with a reason when the dataset is absent. The 2 RAG endpoints were removed — see below. |
| Frontend | ✅ Working | 5 charts, sortable table, CSV export, education section. RAG panel removed. |
| RAG / AI | 🗑️ **Removed 2026-11-17** | It ran on fabricated data. `IC2022Mission.csv` was sample-generator output sitting among the real IPEDS files; IPEDS has published no mission file since 2007. |
| Scoring logic | ✅ Validated on real data | 10 issues resolved + tested; **none open** (see `PROJECT_BRIEF.md` §6). Formulas in `FORMULAS.md`. |
| Merit vs need-based aid | ✅ CDS-sourced across the shortlist | The 26-college hand roster was **wrong for 5 of them**; now read from each college's own CDS H2A with provenance, a year, and an expiry. **Default top 50: 50 attempted, 23 resolved**; 24 of 1,907 dataset-wide. A full crawl was measured at ~38% and rejected — see Phase 4. |
| Tests | ✅ 88 tests, in CI | Scoring, the flag split, net-price coalescing, COA basis, rate scales, weights, merit policy, the year on the row, verdict expiry — plus (Phase 6) the real `data.py` read path against a synthetic fixture dataset, all five endpoints via `TestClient`, and a smoke test that boots uvicorn. `ruff` + `pytest` + smoke run on every push. |
| **Real data** | ✅ **Installed & validated** | Real IPEDS 2022-23: 1,907 colleges (726 public / 1,095 private nonprofit / 86 for-profit). 5 of 5 reference metrics match. |
| Error handling | ✅ Done | Server: bad params get a 4xx naming them, a missing dataset a 503 naming the file. UI: both fetches distinguish *nothing answered* from *answered and said no*, quote the server's own message, and offer retry; a filter that matches nothing says so separately. Verified on the live site by scaling the backend to zero. |
| Deployment | ✅ **Live 2026-11-20**, reviewed 2026-11-27 | `http://136.81.186.158/` — **static IP** (reserved 2026-11-25), digest-pinned images, PDBs, uptime alerting, non-root backend, GKE zonal cluster, 2 Spot e2-medium nodes, 2 replicas per service on separate nodes, data fetched from GCS on pod start. ~$3.50-4.00/day, ~$20 spent in the first five days. HTTP-only by choice — see the deferred decision under Phase 9. Teardown cycle in `DEPLOYMENT.md`; **still running for the demo**. |

**One-line summary:** the app runs on real, validated IPEDS data and produces defensible
rankings — Stanford #1 at $77,662 sticker against a $7,332 net price for a mid-income
family, which is exactly the thesis. The numbers are right; the word "merit" on them was
not, and is now corrected in the UI and sourced per-institution from each college's own
Common Data Set (Phase 4). What remains is
nothing in the app's own behaviour: the silent `getColleges` failure was the last of it,
fixed and verified live on 2026-11-25. The deploy has been live on GCP since 2026-11-20.

---

## 2. What is verified

Confirmed by running it, not by reading it:

- `docker compose up --build` builds both images and serves on :8080.
- Direct run works: uvicorn on :8000, Vite on :5173 with the `/api` proxy.
- `/api/health`, `/api/meta`, `/api/colleges`, `/api/merit-policy` and
  `/api/education/distributions` all return 200 with the expected shapes. Rows carry
  **27** fields. `/api/rag/*` returns **404** — removed in Phase 3.5; there are 5
  endpoints, not 7.
- The flag split behaves as designed. Against a fixture with realistic missingness,
  **11 of the top 20 colleges were missing SAT data and were correctly kept** — under
  the previous `RISK_FLAGS` behaviour all 11 would have been silently dropped.
- **Deployed and curled.** `http://136.81.186.158/api/health` → `{"ok":true}` in
  115 ms; `/api/meta` → 1,907 colleges, net price $2,200-$63,997, SAT coverage 985;
  `/api/colleges?top_n=5` → 27 fields a row, Stanford #1 at a $7,332 net price. The
  frontend root serves the built bundle (HTTP 200, `text/html`).
- **A deleted backend pod comes back serving data** — the replacement re-fetched all
  six CSVs from the bucket and reported the same 1907 / 2200 / 63997 / 985.
- `pytest` — **88 passing**, from a clean checkout with no `backend/data/` present.
- `ruff check .` — clean.
- `python scripts/smoke_test.py` — real uvicorn over generated sample data: boots,
  answers all three endpoints, refuses `top_n=-1` with a 422 and an unknown filter
  with a 400.
- Frontend builds clean (`npm run build`).

## 3. What is unverified or missing

1. **Everything data-dependent.** Sample data has no missing values, no outliers, and
   its net price is constructed from the same components the app sums into `COA` — so
   it is circular with the formula it is meant to test.
2. ~~**Four open scoring questions**~~ — all four closed in Phase 3: COA is
   reconstructed from the identity IPEDS nets against, rate scaling is declared per
   column rather than guessed, equal weighting was tested and kept with its
   influence measured, and weights are configurable via `VALUE_WEIGHTS`.
3. **No error state anywhere in the UI.** `getMeta()` has no `.catch()`; a failed call
   leaves `meta` null and the page renders "Loading…" forever.
4. ~~**RAG runs on TF-IDF.**~~ Moot — the whole feature was removed in Phase 3.5.
   `IC2022Mission.csv` was sample-generator output, and IPEDS has published no
   mission file since 2007 (`IC2022Mission.zip` → 404, `IC2007Mission.zip` → 200).
5. ~~**Thin test coverage.**~~ Closed in Phase 6: `data.py` and all five endpoints are
   covered, 88 tests, running in CI on every push.
6. ~~**Deployment never exercised.**~~ Closed in Phase 8 — deployed 2026-11-20 and
   verified live. The 502 hypothesis was right about the cause and incomplete about the
   fix: the NEG annotation is necessary but the health check also has to be pointed at
   `/api/health` by a BackendConfig, and the cluster has to be VPC-native for a NEG to
   exist at all.

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
| `median_aid_share` | ~~0.3184~~ | 0.2942 | ⛔ **retired as a target** — see below |
| `flagged_count` | 1352 | 379 | ✅ expected — `RISK_FLAGS` redefined |

Also confirmed: rates arrive as 0–100 and the ÷100 heuristic fires (values land
0.03–1.0); **no negative sentinels appear** in any column the app reads, so that
cleaning step is inert for this dataset; `pytest` 9 passed.

Other real-data figures: `median_mgi` 0.5798, `data_gap_count` 922,
`unscoreable_count` 180.

**Done:** the four structural metrics match exactly and still do after Phase 3.

**`median_aid_share` is no longer a validation target** *(2026-11-10)*. 0.3184 was
computed on the reference app's own cost-of-attendance choice, which Phase 3 showed was
understated — it put 459 of 1,907 colleges at a negative discount, meaning their net
price exceeded their entire cost of attendance. A number derived from a demonstrably
wrong denominator is a fingerprint of that app's decisions, not ground truth, and
optimising toward it would mean reproducing the defect. The four metrics that remain
are structural (universe size, net-price extremes, SAT coverage) and depend on no COA
choice. Our figure is now 0.2942.

### Phase 3 — Close the open scoring questions ✅ *complete 2026-11-10*

All four items closed. Formulas, measurements and accepted trade-offs are recorded in
**`FORMULAS.md`**, which this phase created (it was referenced by `CLAUDE.md` but had
never existed).

- [x] **COA vs net price comparability** — resolved, but **not** via `DRVIC2022`.
      IPEDS defines net price as *cost of attendance − average grant aid* for one
      cohort, and publishes that grant (`GIS4A42` public / `GRN4A42` private) for the
      same $75k–$110k band and the same 2021-22 year. Adding it back recovers the exact
      basket net price was computed against, so `COA = NET_PRICE_MID + BAND_GRANT`.
      Cross-checked against an independent reconstruction from the 2021-22 charge
      columns weighted by living arrangement: **1,543 of 1,544 agree to under \$1**.
      Negative discounts went **459 → 0**; coverage stayed 1,907; `incomplete_coa` was
      retired, so `flagged_count` fell 379 → 181.
- [x] **Replaced the percent-scaling heuristic** with `config.RATE_COLUMNS`, declared
      from each variable's dictionary entry, plus a post-conversion range check that
      raises instead of scoring wrong.
- [x] **Tested the equal weighting.** Defensible, and kept — but *not neutral*:
      nominal weights are equal while realised influence is not (Spearman vs final
      score: affordability **+0.107**, graduation +0.667, generosity **+0.803**),
      because affordability correlates negatively with the other two. Pre-existing, not
      caused by the COA change. Full numbers in `FORMULAS.md` §5.
- [x] **Weights are configurable** via `config.VALUE_WEIGHTS` / env vars, normalised,
      and reported in `/api/meta` as `value_weights`.

**Done:** `PROJECT_BRIEF.md` §6 Still open is empty; its four entries moved to Resolved.
Remaining trade-offs are recorded in `FORMULAS.md` §3 rather than left implicit.

### Phase 3.5 — Remove the fabricated mission data ✅ *complete 2026-11-17*

`backend/data/IC2022Mission.csv` was **sample-generator output** — 300 rows of
"Sample College N is dedicated to excellence in …" keyed to synthetic UNITIDs
(100000+) — sitting among the six real IPEDS files, with a vector index built from it
and a user-facing "Ask about mission & values (AI)" panel reading from it.

Verified against the IPEDS data center: `IC2022Mission.zip` returns **404**, as does
`IC2008Mission.zip`; `IC2006Mission.zip` and `IC2007Mission.zip` return **200**. IPEDS
has published no mission file since 2007. `HD2022` has no mission column either.

**Decision: remove the feature.** The real 2007 file was downloaded and measured
first, so this was a choice between live options rather than a guess:

| | figure |
|---|---|
| IC2007Mission rows with text | 3,608 |
| matched to our 1,907 universe | **690 (36.2%)** |
| public institutions | 195 / 726 = **26.9%** |
| private nonprofit | 454 / 1,095 = 41.5% |
| top 100 by Value Score | 36 |
| **the shipped default top 20** | **7** |

Shipping it on the 2007 file (the alternative) fails on its own terms. The panel's
purpose is comparison across the shortlist, and it could speak for 7 of the 20
colleges on screen — the 13 silent ones including Williams, MIT, Princeton and Yale.
A user asking "which of these emphasise access?" would get an answer shaped by which
colleges answered a survey in 2007, and the gap is sector-skewed, so publics lose
twice. Labelling that honestly makes it *not a lie*; it cannot make it useful. And
19-year-old prose beside 2021-22 money invites reading the two as contemporaneous.

Keeping it dark was rejected for the reason the brief gives: the synthetic file is
what makes an accidental revival dangerous, so it had to go either way, and what
remained would have been dead code plus a loaded gun.

Removed: `app/rag.py`, both `/api/rag/*` endpoints, `data.load_missions()`, the
frontend panel and `Markdown.jsx`, `scikit-learn` and `anthropic` from
`requirements.txt`, `INDEX_DIR` and the `ANTHROPIC_API_KEY` wiring from the Dockerfile,
compose file and K8s manifests, and the mission block from `make_sample_data.py`.
Deleted locally: the synthetic CSV and `backend/index/`.

**If a real source is ever wanted**, the measured facts are in the table above — the
2007 file exists and reaches 36.2%. That is a decision someone can now make informed.

### Phase 4 — Split merit aid from need-based aid (Common Data Set) ✅ *closed 2026-11-17*

**Closed on evidence, not abandoned.** Full-dataset CDS coverage was evaluated,
measured and rejected with figures; the shortlist a user actually sees was then
attempted in full. What is not possible is recorded as not possible.

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
section H2A line n**: students with no financial need awarded institutional
non-need-based scholarship or grant aid, excluding athletic awards. It is published
per-institution as a PDF, spreadsheet or dashboard on each college's
institutional-research page.

- [x] **Verified the existing 26** *(2026-11-17)* — and the list was **wrong for five
      of them.** Each was labelled "need-based only" in the shipped UI while its own
      current CDS reported non-need-based institutional aid:

      | institution | CDS | H2A line n | avg award |
      |---|---|---|---|
      | Harvard | 2025-26 | 4 / 20 | $4,728 / $5,279 |
      | Stanford | 2025-26 | 3 / 14 | $11,890 / $13,813 |
      | Wellesley | 2025-26 | 4 / 5 / 0 | $55,716 |
      | Middlebury | 2024-25 | 3 / 8 / 0 | $2,700 / $3,850 |
      | Amherst | 2024-25 | 0 / 6 / 0 | $14,801 |

      Four confirmed zero — Colgate (2024-25), Haverford (2025-26), MIT and Yale
      (both 2025-26). **Seventeen could not be verified at all** and are now
      `unknown`, which is what that value has always claimed to mean.

      **MIT's evidence was corrected afterwards.** Its record first cited line n =
      `N/App` from the 2024-25 edition. Not-applicable is a non-answer, not a
      reported zero, so it could not carry the verdict — the same gap in reasoning
      that produced the five false labels above. Verified directly against both
      editions: MIT's 2024-25 CDS does answer line n `N/App`, while its **2025-26
      edition reports an actual `0 / 0 / 0`**. The record now cites 2025-26, and
      `test_no_verdict_rests_on_a_non_answer` rejects `N/App`, `NA` and blanks in
      the `line_n` field across the whole roster.

      `merit_policy.py` was rewritten around verified records with provenance: source
      URL, CDS year, the figures read, date and method. A third value `awards_merit`
      now exists, so the vocabulary can state a positive finding instead of only an
      absence.

      **Yale is why every record carries a year.** Its H2A line n reads 6/28/1 in
      2023-24, 6/24/0 in 2024-25, 0/0/0 in 2025-26. A policy claim with no year is not
      a fact.

- [x] **Scoped the crawl — and the answer is: do not build it.** Measured on the 26
      best-documented institutions in American higher education:

      | calibration | result |
      |---|---|
      | CDS source URL discoverable | 26 / 26 — but only via a third-party archive |
      | document actually downloadable | **19 / 26 (73%)** — 404s, 403s, expired Box links, a Tableau dashboard |
      | H2A line n readable once downloaded | **10 / 19 (53%)** — values live in AcroForm fields, or are masked (`** *`), or are coded spreadsheet cells |
      | **end-to-end success** | **10 / 26 = 38%** |
      | time | ~80 minutes for 26, *with* source URLs already in hand |

      If the Ivies and the NESCAC yield 38%, the long tail of 1,907 will be worse, and
      the independent evidence agrees: a mature third-party CDS archive that has
      already tried this at scale reports, of 3,000 institutions checked, **1,464
      (49%) with no public CDS found** and only **326 (11%) with a current one**.

      A crawler would therefore spend real effort to land somewhere near 20–35%
      coverage, heavily skewed toward wealthy privates — the same sector skew that
      killed the mission feature. **Recommendation: no crawler.** Extend the verified
      list by hand when a specific college matters, which the provenance model now
      supports, and keep `unknown` honest for the rest.

- [x] **A bulk source was retested, as the plan asked, and it does not deliver.**
      `collegedata.fyi` publishes an open CDS archive whose field dictionary declares
      two H2A-derived fields. The bulk snapshot contains **zero rows** for them (all
      7,056 facts are admissions fields). Its API does return them — but it reports
      Yale as **0.0%** where Yale's own 2024-25 CDS reports 24 recipients at $29,162.
      It was used only to locate primary documents; no figure in `merit_policy.py`
      comes from it.

- [x] **Modelled the result honestly.** `need_only` / `awards_merit` / `unknown`, with
      `coverage()` reported through `/api/meta` and `/api/merit-policy` so the UI
      states resolved / attempted / total rather than implying completeness.

- [x] **Rescoped from the dataset to the shortlist, and finished it there**
      *(2026-11-17)*. Coverage of 9 of 1,907 was not a finished phase either: the
      default top 20 had 4 resolved and 16 unknown. So the target became **every
      institution in the default top 50 attempted**, with its outcome and provenance
      recorded. All 50 were attempted; **23 resolved, 27 unresolved.**

      | scope | attempted | resolved | need_only | awards_merit |
      |---|---|---|---|---|
      | default top 20 | 20 / 20 | **10** (was 4) | 2 | 8 |
      | default top 50 | 50 / 50 | **23** | 5 | 18 |
      | whole dataset | 56 | 24 | 5 | 19 |

      Resolution ran at **46%** on the top 50, above the 38% the calibration
      predicted. Fifteen new institutions resolved and fourteen of them award merit
      aid — including **Washington and Lee at rank 3**, which was `unknown` and
      reports 29 / 132 / 0 at an average of **$62,110** for a first-year recipient,
      the largest per-recipient award in the roster. Only Carleton reported zero.

      The fifteen that did not resolve failed for reasons worth recording, because
      they are the shape of the problem and not bad luck: a 403 that refuses
      non-browser clients (Johns Hopkins), a CDS published only inside an
      authenticated SharePoint folder (Wesleyan), a Box share whose direct download
      403s (Soka), an H2A table absent from the PDF text layer (Augustana), an
      institution that publishes IPEDS figures *instead of* a CDS and says so
      (Cleveland Institute of Music), a college that closed in 2023 (Holy Names),
      and nine small or specialised institutions that publish no CDS at all.

- [x] **Verdicts now expire instead of ageing into claims.** `CURRENT_EDITION` and
      `STALE_AFTER_EDITIONS = 2` mean a record more than two editions behind the
      current one stops being reported and reverts to `unknown` with no edit. This
      makes a rule out of the instinct already applied by hand to Colby, whose only
      published CDS is 2019-20. Nothing can quietly become a stale assertion.

- [x] **The year reaches the row, and the two kinds of blank are separated.**
      `MERIT_POLICY_YEAR` and `MERIT_POLICY_STATUS` are additive row fields. The UI
      previously claimed "each label names the year it came from" while rendering no
      year at all, because `cds_year` never left `merit_policy.py` — a label
      overstating what it displays, which is the same class of error as calling
      `IGRNT_A` "merit". `MERIT_POLICY_STATUS` splits *checked, not published* from
      *never checked*; both are `unknown` as a policy, and neither is ever a finding.

- [ ] **A real merit metric remains impossible** for all but the 24 resolved. Until
      the split exists for an institution, no "merit" number is computed from
      `IGRNT_A` under any weighting — there is no arithmetic that recovers it.
      Unchanged by this phase and not expected to change.

**Done when** *(redefined 2026-11-17)*: **every institution in the default top 50 has
been attempted, with its outcome and provenance recorded, and the UI reports resolved
/ attempted / total.** **Met** — 50 of 50 attempted, 23 resolved.

**Why "Done when" was redefined, recorded so it is a decision and not a lowered bar:**
the previous wording ("a stated, measured share of the dataset") could be satisfied by
any number at all, including 9, which is how a phase stays technically met while the
thing a user sees stays blank. The replacement is the strongest guarantee that is
actually ours to give. We control whether we *attempt* an institution; we do not
control whether it published a readable CDS, and at a measured 38–46% hit rate a
resolved-coverage target would have been a promise about other people's websites.
Reporting both numbers is the honest form of that: attempted is a commitment, resolved
is an outcome.

**Coverage statistics here flatter the dataset, and that is stated wherever they
appear** (`coverage()["sector_caveat"]`, the UI footer, `FORMULAS.md` §4). The top 50
is 48 private nonprofits and 2 publics — 96% private against **57.4%** (1,095 of
1,907) across the whole dataset — and is drawn from its most selective, best-endowed
end. Within the slice, 21 of 48 privates and both publics resolved; a 2-college public
sample supports no claim either way about sector, so the skew to report is the
*composition* of the slice, not a measured sector difference. The external evidence is
what bears on the full dataset: an independent archive finds no public CDS for 1,464 of
3,000 institutions, which points to the full-dataset rate being worse than 46%.

**Why the scope changed:** the phase assumed the ceiling was effort. It is not — it is
publication. Roughly half of institutions do not publish a findable CDS at all, and a
meaningful share of those that do publish it in a form no parser can read.
**Full-dataset CDS coverage is therefore rejected on measured evidence, not deferred:**
38% end-to-end on the 26 best-documented institutions in American higher education,
~80 minutes for those 26 with source URLs already in hand, and independent
corroboration at 49% with no public CDS. A 1,907-college crawler would land near
20–35%, skewed to wealthy privates. It was not built, and should not be.

### Phase 5 — Harden the app for a real user ✅ *closed 2026-11-25*

The failure this phase existed to prevent: a backend that is unreachable produced a
working-looking page with an empty table and no explanation, indistinguishable from
filters that legitimately matched nothing. Both now say which, on the live site.

- [x] ~~**Add error states.** `getMeta()` needs a `.catch()`~~ — done 2026-10-28: a
      failed `/api/meta` now renders a `.fatal` panel naming the error with a Retry
      button, instead of an endless spinner.
- [x] **`getColleges` has a real error state** *(2026-11-25)*. It used to end
      `.catch(() => setLoading(false))`, which discarded the error and left an empty
      table. Three outcomes are now distinct, and the page says which: rows, no rows,
      or a failure.

      The enabling fix was in `api.js`, which threw `new Error(r.status)` and so
      discarded the response body — the one thing worth telling a user was the one
      thing thrown away. Errors now carry the server's `detail`, and `kind`
      distinguishes *nothing answered* (fetch rejected) from *answered and said no*.
      The backend's 503 names the dataset file and the directory it looked in, and
      that string is now quoted on screen verbatim.

      Retry re-runs only the rankings fetch rather than reloading the page, which
      would also discard the filters the user had set.

- [x] **Empty state when filters return zero rows** *(2026-11-25)*. It says the
      request *worked*, gives the dataset size that was searched, names whichever
      active filter is most likely responsible, and offers Reset — visually distinct
      from the error card (slate left border, not red).

- [x] **The `/api/meta` failure page was also wrong, and was fixed with it**
      *(2026-11-25)*. It claimed "Can't reach the backend" even when the backend had
      answered with a precise reason, and then offered `uvicorn`/`docker compose`
      advice to someone looking at the deployed site. It now splits the same two cases
      and quotes the server when there is something to quote. This is the page the
      missing-dataset failure actually lands on, because `/api/meta` fails first.

- [x] ~~**Decide what happens to the RAG feature**~~, ~~**Fix the RAG dead-end**~~,
      ~~**Surface the retrieval mode**~~ — all three removed as stale. The feature was
      deleted in Phase 3.5 (its only data source was generated text, and IPEDS has
      published no mission file since 2007), so a list implying it still exists was
      itself misleading. `test_the_removed_rag_endpoints_stay_removed` is what guards
      it now.
- [x] ~~Input validation on `/api/colleges`~~ — done in Phase 6, where the tests that
      found the defects live: bounded `top_n` / `max_net_price`, unknown parameters
      rejected, and a 503 that names the missing file instead of a numpy 500.
- [ ] **Code-splitting the 4.8 MB bundle** (1.4 MB gzipped, nearly all Plotly) —
      deliberately not done, and deliberately left open. It is a performance nicety,
      not a correctness fix: it changes how fast the page arrives, never whether the
      numbers on it are right. Doing it means another image build, push and rollout
      against a live site days before a demo, in exchange for a first-load improvement
      that is invisible on a second visit. Worth doing after the demo.

**Done when:** killing the backend produces a visible, recoverable error in the UI.
**Met**, verified against the live site rather than localhost — `kubectl scale
deploy/backend --replicas=0` while the page was open and in use, then a filter change:

```
Couldn't reach the rankings service

/api/colleges answered HTTP 502 with no explanation, which is what a load
balancer returns when no healthy instance is behind it. The API may be
restarting. This page is served separately from it, which is why you can
still read this -- and nothing is wrong with your filters.

Try again
```

and with the dataset itself removed (`DATA_DIR=/data/missing`):

```
The backend can't serve its data

/api/meta answered HTTP 503 and said:

Missing IPEDS file: HD2022.csv in /data/missing. Run
scripts/make_sample_data.py for a demo, or add the real files.

The app is running; its dataset is not. Nothing here can be fixed from the
browser.
```

The "Shown after filters" tile reads `—` on an error, not `0`, so a failure cannot be
misread as a result. Captured from the deployed site with headless Chrome, since
`curl` returns only the 614-byte React shell.

### Phase 6 — Extend test coverage ✅ *closed 2026-11-18*

**40 tests to 88.** The gap this phase closed was not breadth, it was that the suite
was *entirely* in-memory: every test built a frame and called `add_metrics` directly,
so `data.py` — the code that reads six CSVs off disk, filters the universe, coalesces
the public/private column pairs, converts sentinels, reconstructs COA and decides
which colleges are dropped — had never run under test. It produced every number the
app displays and was the least covered file in the project.

- [x] **`data.py`: load, merge, clean, sentinel handling, empty-result handling**
      *(2026-11-18)*. `tests/test_data_pipeline.py`, 18 tests, run against a
      committed synthetic fixture dataset at `backend/tests/fixtures/` — **not**
      `backend/data/`, which stays gitignored and real-data-only.

      `ipeds_synthetic/` is 13 invented institutions (UNITID 999001+, every name
      prefixed `ZZ SYNTHETIC`, real IPEDS column names), one per code path: a public
      and a private row, `-2` sentinels, a blank graduation rate, a row with no
      tuition, a two-year college, a non-degree-granting one, a row absent from SFA,
      a grant larger than the whole cost of attendance, a missing band grant, an
      unmapped `CONTROL`, and a suppressed grant. Eight of the thirteen survive
      cleaning; the five drops are the point. `ipeds_all_dropped/` is the
      empty-result case.

      The fixture is test input and never a fallback — the app has no code path that
      reads it, and `test_the_fixtures_are_never_the_app_default` asserts both that
      the default `DATA_DIR` does not point there and that every institution name
      announces itself as synthetic. Serving invented colleges in place of a broken
      deployment is the worst failure this app could have.

- [x] **Endpoint tests via `TestClient`, including malformed query params**
      *(2026-11-18)*. `tests/test_api.py`, 27 tests over all five endpoints, the
      27-field row schema, JSON validity, and every way a caller can get
      `/api/colleges` wrong. It found three defects, all of them *wrong answer
      returned as an answer* rather than crashes:

      | Request | Was | Now |
      |---|---|---|
      | `top_n=-1` | 200 with **n−1** colleges (`head(-1)` drops the last row) | 422 |
      | `top_n=0` | 200 with the **whole dataset** (`if top_n:` is false at 0) | 422 |
      | `max_netprice=60000` | 200, parameter ignored, default-filtered list returned | 400 naming it |
      | missing dataset | 500 from `np.nanmin` inside `meta()` | 503 naming the file and directory |

      The first three are the same error as a label overstating its data: a request
      nobody could answer, answered plausibly. Bounds are now declared
      (`top_n` 1–2000, `max_net_price` ≥ 0) and unknown parameters are rejected
      rather than ignored. This overlaps the input-validation item in Phase 5; it was
      done here because these are the tests that found it, and a bound with no test
      is a bound nobody maintains.

- [x] **Dataset failure is diagnosable from outside the container** *(2026-11-18)*.
      New `data.DatasetUnavailable`, raised when a file is missing **or** when files
      are found and no row survives cleaning, answered by the API as 503 with the
      reason. `/api/health` stays 200 — the process is fine, the data is not. This is
      the exact state a pod boots into with the `emptyDir` mount still in
      `deploy/k8s/backend.yaml`, so `curl /api/meta` now diagnoses Phase 8's first
      blocker without shell access.

- [x] ~~**RAG endpoint with and without an API key.**~~ Moot — `/api/rag/*` was
      removed in Phase 3.5 because its only data source was generated text. Replaced
      by `test_the_removed_rag_endpoints_stay_removed`, which asserts both routes
      still 404: the useful remaining test is that fabricated content cannot come
      back.

- [x] **Smoke test that boots the stack** *(2026-11-18)*. `scripts/smoke_test.py`
      generates sample data into a throwaway directory, launches real uvicorn, waits
      on `/api/health`, then checks `/api/meta`, `/api/colleges`, and that bad input
      is refused by a real server rather than only by the in-process test client. It
      writes nothing to `backend/data/`. `make_sample_data.py` now takes an output
      directory (argument, else `$DATA_DIR`, else `../data`) so that is possible.

- [x] **CI (lint + tests on push)** *(2026-11-18)*. `.github/workflows/ci.yml`:
      `ruff check` + `pytest` + the smoke test on Python 3.12, plus a frontend
      `npm ci && npm run build` job, on every push and pull request. Needs **no
      dataset** (the suite is fixture-based) and **no secrets** — the RAG panel was
      the only thing that ever wanted `ANTHROPIC_API_KEY`, and a public repo with no
      secrets in CI has nothing for a workflow to leak. Lint config in
      `backend/ruff.toml`.

- [x] **Verdict expiry is covered, not merely dormant** *(2026-11-18)*. Phase 4's
      staleness rule had never actually expired anything — nothing on the roster is
      stale, so every stale branch was unreached code that would first run on the day
      a human bumps `CURRENT_EDITION`, which is exactly when a regression ships.
      `is_current()` now takes the edition as an argument and the partition is
      computed per edition instead of frozen at import, so
      `test_expiry_fires_when_the_edition_advances` moves the edition forward and
      watches records leave the roster, revert to `unknown`, become
      `attempted_unresolved`, and gain a generated reason — then moves it back and
      asserts they return. Expiry is a function of a declared edition, not a
      mutation, and `test_no_verdict_depends_on_the_clock` asserts the module reads
      no clock at all, so no result in this suite changes overnight.

**Done when** *(redefined 2026-11-18)*: **lint and the full suite run in CI on every
push, and the read path, the five endpoints and a booted server are each covered by
tests that assert behaviour.** **Met.**

**Why "covers every module" was replaced, recorded so it is a decision and not a
lowered bar:** the old wording invites a coverage percentage as the target, and a
percentage is satisfiable by tests that execute lines without asserting anything
about them. The evidence is local: the five false `need_only` labels — the most
serious defect this project has had — were in a module that line coverage would have
called fully exercised. They were caught by checking a claim against its source.
Likewise `top_n=-1` was *always* covered code; what was missing was a test that
asked what it returned. So the bar is which failures the suite would catch, and the
record of that is which real defects each test file was written from.

**Owner action — done 2026-11-20.** CI is now a **required status check** on `main`.
Enabled in GitHub → Settings → Branches and verified in the UI, not taken on report:
*Require status checks to pass before merging* with both `backend (lint, tests,
smoke)` and `frontend (build)` listed as required and accepting updates from GitHub
Actions, plus *Require branches to be up to date*, *Require a pull request before
merging*, and *Require approvals: 1*. A red build now blocks a merge. Owner bypass
stays off, so direct pushes to `main` by the owner are unaffected.

Two things remain open here and are fine to leave: the `pull_request` trigger has
still never fired, because no pull request has ever existed on this repo, and the
frontend has no tests beyond the build.

### Phase 7 — Upgrade to IPEDS 2023-24 ⏸️ *unblocked, deferred by choice*

**Not blocked.** It was gated on Phase 2 (install and validate the real dataset),
which closed on 2026-10-28. Nothing stands in the way of doing it; it is simply not
worth doing before the demo, because it would re-open every number the app displays
and re-validate every figure in these docs for a one-year-newer dataset that changes
no conclusion. Full plan in §6 below.

### Phase 8 — Deploy to GCP ✅ *live 2026-11-20*

**Running at `http://136.81.186.158/`.** Project `merit-aid-app`, zonal cluster
`merit-aid-cluster` in `us-central1-a`, two Spot `e2-medium` nodes, two replicas of
each service behind a Google Cloud load balancer. Every claim below was checked with
`curl`, `kubectl` or `gcloud` against the running cluster, not read off a manifest.

- [x] **`emptyDir` for data — fixed with an init container** *(2026-11-20)*. The
      blocker was never the volume type: nothing populated the volume at all, because
      `backend/data/` is gitignored and `backend/.dockerignore` excludes `data/`, so
      neither the repo nor the image carries the dataset. Each pod now copies the six
      CSVs from `gs://merit-aid-ipeds-2026/` on start and fails its init if it does
      not get exactly six.

      `emptyDir` is kept deliberately. A ReadWriteOnce PVC attaches to one node at a
      time, which would make the two replicas mutually exclusive — the second pod
      would sit Pending forever. The bucket is the durable copy, so a restart cannot
      lose data: it re-fetches it. Verified by deleting a running pod — the
      replacement fetched all six files (20.5 MiB at 53.4 MiB/s) and served
      `colleges_in_dataset 1907 | net_price 2200-63997 | sat_coverage 985`, the same
      four structural targets the suite pins.

- [x] **NEG annotation + BackendConfig** *(2026-11-20)*. Proven at the Google layer
      rather than inferred: `gcloud compute health-checks describe` on the backend NEG
      reports `requestPath: /api/health, port: 8000, USE_FIXED_PORT` — not `/` on a
      node port — and `gcloud compute backend-services get-health` reports
      `HEALTHY;HEALTHY` for both endpoints. No 502 was observed at any point.

- [x] **`startupProbe` added, and `@app.on_event("startup")` replaced with a lifespan
      handler** *(2026-11-20)*. The deprecation warning is gone from the test run (3
      warnings to 1). The handler still swallows a dataset failure on purpose: a pod
      that crashes at import gives Kubernetes a CrashLoopBackOff and no HTTP answer,
      where booting lets `/api/health` stay 200 while `/api/meta` returns the 503 that
      names the missing file.

- [x] **`replicas: 2`, and the second replica actually buys something** *(2026-11-20)*.
      Required pod anti-affinity on `kubernetes.io/hostname`, verified with
      `kubectl get pods -o wide`: the two backends sit on different nodes, as do the
      two frontends. On Spot nodes, two replicas on one node would be preempted
      together.

- [x] **Deployed via `DEPLOYMENT.md`** — which no longer has a secret step. The RAG
      panel was the only consumer of `ANTHROPIC_API_KEY`; the deploy path now has no
      secret at all, and `secretmanager.googleapis.com` was dropped from Terraform.
      There was no dangling `secretKeyRef` in the manifests to clean up.

- [ ] **Tear down when the demo is over.** Still running on purpose. The cycle,
      the order and the reason billing must never be switched off are written into
      `DEPLOYMENT.md`.

**Done when:** the external IP serves the app and `/api/*` survives a pod restart.
**Met**, both verified live.

**Four first-apply surprises, none of them in the recorded blocker list.** This is
what the second day of the estimate was for:

1. **Terraform's own dependency graph.** `google_compute_network` had no `depends_on`
      the API-enablement resources, so the first apply raced them and died with
      "Compute Engine API has not been used in project merit-aid-app before or it is
      disabled". Fixed in `main.tf`.
2. **`e2-small` could not run this at all.** Both second replicas sat Pending with
      "0/2 nodes are available: 2 Insufficient memory": an e2-small offers 1.33 GiB
      allocatable and GKE's own system DaemonSets request ~810 MiB of it. Moving to
      `e2-medium` cleared memory and exposed the real constraint — a *shared-core* E2
      node reports **940m allocatable CPU regardless of size**, of which system pods
      request ~680m.
3. **The requests were the actual bug.** `kubectl top` shows the backend using **3m
      CPU and 81Mi** while serving the real dataset, against requests of 250m/512Mi —
      ~80x and ~6x over. Requests are now set from that measurement (100m/256Mi, with
      limits left at 1 CPU / 768Mi for the boot-time build). The single-replica
      blocker and the node size turned out to be the same blocker, and neither was
      really about nodes.
4. **`ingressClassName: gce` does not work on GKE.** Modernising away from the
      deprecated `kubernetes.io/ingress.class` annotation left the Ingress sitting for
      21 minutes with no address and — the tell — *no events at all*. This cluster has
      no IngressClass objects whatsoever (`kubectl get ingressclass` → No resources
      found); GKE's controller keys off the annotation. Reverted, with the evidence in
      the file so nobody "fixes" it again.

A fifth, smaller one: with required anti-affinity and replicas == nodes, a default
rollout deadlocks, because the surge pod has nowhere to be scheduled. Both Deployments
now set `maxSurge: 0`.

**Cost, from Google's Cloud Billing Catalog API rather than from memory:** the zonal
cluster management fee is **$0.10/hour** ($73/month) and Spot E2 is $0.012440 per
vCPU-hour plus $0.001666 per GiB-hour, making two e2-medium nodes $0.038/hour
($27.90/month). With the load balancer (~$18/month, the one figure not taken from a
primary source) that is **roughly $3.50-4.00 per day**. No other GKE cluster exists on
this billing account, so the one-free-zonal-cluster credit ($74.40/month) should apply
and bring it to roughly $45-50/month — an expectation to confirm against the actual
bill in 24-48 hours, not a measurement.

### Phase 9 — Finish ✅ *closed 2026-11-25*

- [x] **README reflects the deployed URL and the real data year** *(2026-11-25)*.
      Both years, because they differ: the institutional and derived files are IPEDS
      **2022-23**, while student financial aid (`SFA2122`) is **2021-22**. Every net
      price, grant and COA figure in the app comes from that 2021-22 cohort, so saying
      only "2022-23" would overstate how current the money is.

- [x] **The live address is now static** *(2026-11-25)*. The load balancer had an
      ephemeral IP, so a destroy/apply cycle would have returned a different one and
      killed every link already shared — including the one now in the README. The
      address the load balancer was already using was promoted in place
      (`gcloud compute addresses create merit-aid-ip --global
      --addresses=136.81.186.158`), imported into Terraform as
      `google_compute_global_address` so it is code rather than a console artefact,
      and claimed by the Ingress by name. `terraform plan` reports **No changes**, and
      the IP was still `136.81.186.158` and still serving HTTP 200 three minutes after
      the annotation was applied.

      It had to be **global**, not regional: a GKE Ingress creates a global external
      Application Load Balancer, confirmed by the forwarding rule appearing under
      `gcloud compute forwarding-rules list --global` and under no region. A regional
      address cannot serve a global forwarding rule.

- [x] **`PROJECT_STATE.md` marked complete** — Phases 1-6, 8 and 9 closed; Phase 7
      unblocked and deferred by choice.

- [ ] **Teardown verified** — deliberately *not* done. The stack is up for the demo,
      and the teardown order in `DEPLOYMENT.md` is written from the resource
      dependencies rather than from having run it. That is stated there as untested,
      and it stays stated until someone runs it.

### HTTPS: analysed 2026-11-27, awaiting Hasan's decision

Hasan wants HTTPS only if it adds no real cost or risk. It adds a little of both, and
the numbers below are measured rather than recalled.

**A certificate cannot be issued to the IP.** Not an opinion — Google rejects it:

```
$ gcloud compute ssl-certificates create test-ip-cert --domains=136.81.186.158 --global
ERROR: Invalid value for field 'resource.managed.domains[0]': '136.81.186.158'.
       Invalid domain name specified.
```

So HTTPS requires buying a domain. **That is the only real cost, and it is Hasan's
call, not mine. Nothing has been purchased.**

| Item | Cost | Source |
|---|---|---|
| `meritaidfinder.com` | **$12.00/year**, AVAILABLE | `gcloud domains registrations search-domains` |
| `meritaid.app` | $14.00/year, AVAILABLE | same |
| Google-managed certificate (classic, what a GKE `ManagedCertificate` uses) | **no SKU in the price list** → free | Cloud Billing Catalog API, Certificate Manager + Networking services |
| Certificate Manager (a *different*, newer product) | $0.10 / certificate / month | Catalog API, SKU "Certificates usage" |
| Second (HTTPS) forwarding rule on the existing load balancer | **$0, almost certainly** | Catalog API: "Cloud Load Balancer Forwarding Rule **Minimum** Global" $0.025/hr, "Forwarding Rule **Additional** Global" $0.010/hr |

On that last line, precisely: the load balancer is billed as a flat *minimum* that
covers a set of forwarding rules, plus an *additional* per-rule charge beyond it.
There is one rule today and HTTPS would make two, which is inside the documented
included count of five — so the expected marginal cost is **$0/month**, and the
worst case if the included count were one is **$7.30/month**. The rate is verified;
the threshold is not, because the catalog does not publish it.

**The real risk is time, not money.** A managed certificate only begins issuing once
DNS resolves to the load balancer, and issuance has historically taken 15–60 minutes
and occasionally far longer. Days before a presentation, that is the exposure.

**What breaks if the certificate is not ready on the day:** nothing, if it is done the
way below. HTTP stays serving throughout — a GKE Ingress keeps its HTTP forwarding
rule unless `kubernetes.io/ingress.allow-http: "false"` is set, so the plan is to add
HTTPS *alongside* and leave the existing `http://136.81.186.158/` path untouched. A
certificate stuck in `PROVISIONING` means `https://` does not work yet; it does not
affect `http://`. A redirect would only be considered after the certificate reports
`ACTIVE`.

**The static IP is already reserved and Terraform-managed**, so it is a valid A-record
target. That part is done.

**If Hasan declines**, the consequence stays as recorded below, now with one
measured addition: browsers do not merely warn, they can fail outright.

### Deferred decision: no custom domain, so the site is HTTP-only

*Recorded 2026-11-25 so this reads as a choice and not an oversight.* Hasan decided
against a custom domain for now. A domain adds DNS propagation and certificate
provisioning as new failure modes within days of a demo, and it complicates teardown
by leaving a registration and DNS records behind after the cluster is gone.

The consequences, which are real and worth stating plainly:

- **The site is HTTP-only and browsers mark it "Not secure".** There is no way around
  that on a bare IP: a Google-managed certificate requires a domain name, because
  certificates are issued to names and not to addresses.
- **Chrome actively tries HTTPS first.** Observed while capturing the live page on
  2026-11-25: headless Chrome upgraded `http://136.81.186.158/` to `https://`, found
  no certificate, and landed on `chrome-error://chromewebdata/` rather than the site.
  The capture needed `--disable-features=HttpsUpgrades`. Anyone sharing the link
  should write `http://` explicitly and expect some browsers to need a click-through.
- **Nothing sensitive crosses the wire.** The app takes no credentials and no personal
  data; it reads public IPEDS figures and sends filter values. The exposure from plain
  HTTP here is a trust signal, not a data risk.

Reversible in about 20 minutes of work plus certificate provisioning whenever a
domain is wanted: point an A record at `136.81.186.158` — which is static now, so it
is a valid DNS target — then attach a `ManagedCertificate` to the Ingress. See the
HTTPS analysis above for what that costs and what it risks.

### Phase 10 — Production review ✅ *2026-11-27*

Four things added, eight rejected. Every decision below was made from a measurement
taken against the running cluster, and each addition was verified by making it fire
rather than by reading the manifest back.

**What the measurements say.** These are the numbers the decisions rest on:

| Measurement | Value | How |
|---|---|---|
| Backend CPU / memory, idle | **3m / 81Mi** | `kubectl top pod` |
| Backend CPU at 6 concurrent clients (50 rps) | **~430m** each, p50 112ms, p95 165ms | 70s load test from this machine |
| Backend CPU at 24 concurrent clients (74 rps) | **917m / 822m**, p95 498ms, 22 errors in 7,423 | 100s load test |
| Node allocatable CPU (e2-medium, shared core) | **940m**, of which GKE's own system pods request ~680m | `kubectl describe node` |
| Spot preemptions since deploy | **1 in 13.6 node-days** (node `bbfh`, 2026-11-21T04:54:52, recreated 21s later, no outage) | `gcloud compute operations list` |

#### Added

- [x] **Images pinned by digest, not `:latest`** *(2026-11-27)*. With a mutable tag,
      any pod restart pulls whatever was last pushed, so a half-finished image becomes
      the running code at a moment nobody chose — and a preemption has already
      restarted a pod here once. Verified: `kubectl get pods -o jsonpath` shows
      `backend@sha256:5682970461e3…` on both replicas.

      **Operational consequence, deliberately accepted:** a future deploy must refresh
      the digest in the manifest or `kubectl apply` is a no-op that leaves the old
      image running. The command is in `DEPLOYMENT.md` step 3.

- [x] **PodDisruptionBudgets, `minAvailable: 1`** *(2026-11-27)*. This covers the gap
      the anti-affinity does not: a voluntary disruption — `kubectl drain`, a GKE node
      auto-upgrade — draining both nodes in sequence without waiting. Verified by
      firing the Eviction API twice:

      ```
      evicting backend-cc45f4f5d-7crxj  -> {"status":"Success","code":201}
      evicting backend-cc45f4f5d-d2nxt  -> 429 TooManyRequests:
          Cannot evict pod as it would violate the pod's disruption budget.
      ```

      Without the budget both evictions succeed and the service goes to zero. The site
      answered 200 throughout. It does **not** protect against Spot preemption, which
      is involuntary — nothing can veto that, and `replicas: 2` across two nodes is
      what covers it.

- [x] **Uptime check and alert policy, with the delivery path proven** *(2026-11-27)*.
      A 5-minute check on `/api/health` and a policy that opens an incident when it
      fails, carrying a runbook. Verified end to end: a deliberately failing decoy
      check produced a delivered alert in **~300 seconds**, with the incident payload
      arriving on a Pub/Sub channel. Decoy then deleted; the real check reports 100%.

      **This is also how a monitoring bug was caught.** The first version of the check
      was created from Git Bash, which rewrote `/api/health` into
      `/C:/Program Files/Git/api/health`. That check passed — because nginx's SPA
      catch-all (`try_files $uri $uri/ /index.html`) answers **200 for any path that
      is not under `/api/`**. Measured:

      ```
      /api/health        HTTP 200        /not-an-api-path   HTTP 200
      /api/nope          HTTP 404        /C:/anything       HTTP 200
      ```

      So a health check on any non-`/api/` path is green even with the backend dead —
      a monitor that cannot observe the failure it exists for. Only an `/api/` path
      works, which is what the check uses now.

      **One step left for a human:** there is no email channel, because adding one
      means putting an address into cloud config. One line adds it:
      `gcloud alpha monitoring channels create --display-name="me" --type=email
      --channel-labels=email_address=YOU@example.com`, then attach it with
      `gcloud alpha monitoring policies update 6020692583677610040
      --add-notification-channels=…`. Until then incidents are visible in
      Monitoring → Alerting but nobody is told.

- [x] **The backend no longer runs as root** *(2026-11-27)*. It had been uid 0 for a
      week with no reason to be: it reads two directories and binds a port above 1024.
      Now `runAsNonRoot`, uid/gid 1000, `allowPrivilegeEscalation: false`, all
      capabilities dropped, `seccompProfile: RuntimeDefault`. Verified in the pod:
      `uid=1000(?) gid=1000` and it still serves 1,907 colleges. The init container
      stays root because it writes the dataset into the volume.

#### Rejected, with the reason

- **Horizontal Pod Autoscaler — rejected, and this is the one worth explaining.**
      Not because nothing would trigger it: the measurement above shows the backend at
      ~430m under a realistic 50 rps, which is **4× its 100m request**, so an HPA
      targeting 70% of requests would want to scale immediately and keep wanting to.

      It could not do anything about it. The backend has **required** pod
      anti-affinity on hostname, so backend replicas are capped at the number of nodes
      — two. The node pool is fixed at `node_count = 2` with no cluster autoscaler. An
      HPA would therefore sit permanently at `desired 6 / current 2` with a third pod
      Pending on "didn't match pod anti-affinity rules", which is worse than absent:
      it is a control that reports a decision it can never carry out.

      The real throughput lever here is node capacity, not replica count — the pods
      are bounded by a 940m shared-core node, not by how many of them there are. At
      the load this app will actually see (a room of people clicking is single-digit
      concurrency, measured at 50 rps with p95 165ms and one error in 3,514) there is
      nothing to solve.

- **Cluster autoscaler / bigger nodes — rejected for now, available if wanted.** This
      is the honest fix for throughput, and it costs money: node count or machine size
      is the only thing that raises the ceiling. Not justified at measured demo load.

- **Converting the node pool off Spot — rejected on the data.** Measured preemption
      rate is 1 per 13.6 node-days, the one that happened recovered in 21 seconds and
      caused no outage, and the two-replica anti-affinity design absorbed it. Paying
      roughly $14/month more to remove a risk that has already been survived once is
      not a good trade. The residual exposure is a *simultaneous* preemption of both
      nodes, which would mean a few minutes of downtime; the free mitigation is to
      have `docker compose up` ready locally during the presentation rather than to
      buy on-demand VMs.

- **NetworkPolicy — rejected.** It needs the Calico addon enabled on the cluster,
      which is a cluster-level mutation days before a presentation, and the thing it
      would protect is two pods with no secrets, no credentials and no write access to
      anything. It would also have to allow the Google health-check ranges explicitly,
      which is a new way to break the load-balancer path. Worth doing in a cluster
      that hosts more than one application.

- **Blue-green deploys — rejected.** A second full environment needs twice the nodes.
      Rolling is already correct here and already constrained: `maxSurge: 0` (forced by
      the required anti-affinity), so a deploy dips to one replica for about 30
      seconds. The demo-week answer is not to deploy during the demo.

- **Secrets management — moot.** There are no secrets. The RAG panel was the only
      consumer of `ANTHROPIC_API_KEY` and it was deleted in Phase 3.5;
      `secretmanager.googleapis.com` is not even enabled.

- **Storage — already solved in Phase 8.** The dataset comes from GCS on every pod
      start into an `emptyDir`, which is what makes a restart survivable. A PVC would
      make the two replicas mutually exclusive.

- **Workload Identity — rejected for now.** The nodes use the default compute service
      account with `cloud-platform` scope, which is broader than the bucket read they
      need. Tightening it means enabling Workload Identity on the cluster and
      recreating the node pool: the right change, the wrong week.

- **`readOnlyRootFilesystem` — rejected for nginx.** It needs writable mounts for
      `/var/cache/nginx` and `/var/run`, so it is a change with a real chance of
      breaking the frontend for a hardening benefit on a container that serves static
      files. The backend's root filesystem is already effectively read-only in
      practice (it writes nothing).

- **Artifact Registry vulnerability scanning — rejected.** Billed per image scan, and
      it produces a report nobody will act on before the presentation.


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
| ~~`COA` understates the real cost basket~~ | ~~Biases `DISCOUNT` and `AID_SHARE`~~ | ✅ **resolved Phase 3** — COA recovered from the published net-price identity |
| GKE Ingress health-checks `/` | 502s on `/api/*` with the site up | Phase 8 — fix manifests before first deploy |
| `getColleges` failure is invisible to users | Empty table, no explanation | Phase 5 — the `/api/meta` path is fixed, this one is not |
| ~~Curated need-only list is unverified~~ | ~~A college wrongly labelled "need-based only"~~ | ✅ **resolved 2026-11-17** — verified against CDS H2A; 5 of 26 were wrong and are corrected |
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
