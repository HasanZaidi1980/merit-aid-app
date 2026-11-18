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
| Backend API | ✅ Working | 5 endpoints, 25-field rows. The 2 RAG endpoints were removed — see below. |
| Frontend | ✅ Working | 5 charts, sortable table, CSV export, education section. RAG panel removed. |
| RAG / AI | 🗑️ **Removed 2026-11-17** | It ran on fabricated data. `IC2022Mission.csv` was sample-generator output sitting among the real IPEDS files; IPEDS has published no mission file since 2007. |
| Scoring logic | ✅ Validated on real data | 10 issues resolved + tested; **none open** (see `PROJECT_BRIEF.md` §6). Formulas in `FORMULAS.md`. |
| Merit vs need-based aid | ✅ CDS-sourced across the shortlist | The 26-college hand roster was **wrong for 5 of them**; now read from each college's own CDS H2A with provenance, a year, and an expiry. **Default top 50: 50 attempted, 23 resolved**; 24 of 1,907 dataset-wide. A full crawl was measured at ~38% and rejected — see Phase 4. |
| Tests | ⚠️ Partial | 40 tests over scoring, flags, net-price coalescing, COA basis, rate scales, weights, merit policy, the year on the row and verdict staleness. No endpoint tests. |
| **Real data** | ✅ **Installed & validated** | Real IPEDS 2022-23: 1,907 colleges (726 public / 1,095 private nonprofit / 86 for-profit). 5 of 5 reference metrics match. |
| Error handling | ⚠️ Partial | `/api/meta` failure now shows a real error with a retry. `getColleges` and the empty state are still silent. |
| Deployment | ❌ Not started | Terraform + K8s manifests exist, never applied. |

**One-line summary:** the app runs on real, validated IPEDS data and produces defensible
rankings — Stanford #1 at $77,662 sticker against a $7,332 net price for a mid-income
family, which is exactly the thesis. The numbers are right; the word "merit" on them was
not, and is now corrected in the UI and sourced per-institution from each college's own
Common Data Set (Phase 4). What remains is
a UI that still fails silently on `getColleges`, and the deploy.

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
- `pytest` — 40 passing.
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
