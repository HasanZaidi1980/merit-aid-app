# Test fixtures — SYNTHETIC DATA, NOT IPEDS

**Nothing in this directory is real.** Every institution here is invented, every
UNITID is fake (`999001`+, outside the range IPEDS assigns), and every dollar figure
was chosen to make one code path run. No number here may be quoted, screenshotted,
charted or cited as a finding about any college. `CLAUDE.md` §2: *"Sample data must
never be mistaken for real."*

These files exist because of a gap Phase 6 found: the suite was entirely in-memory,
so `data.py` — the load / merge / clean / sentinel / drop path that produced every
number the app displays — never ran under test at all. It was the least covered code
in the project and the most consequential. These fixtures let `build_dataset()` be
exercised end to end from actual CSVs on disk.

## This is test input. It is never a fallback.

`DATA_DIR` is pointed here by the tests and by nothing else. The app has no code path
that falls back to this directory when the real files are absent — a missing dataset
raises `data.DatasetUnavailable`, which the API answers with a 503 naming the missing
file. Serving invented colleges in place of a broken deployment would be the worst
possible failure mode for an app whose only value is that its numbers are real.

`test_data_pipeline.py::test_the_fixtures_are_never_the_app_default` asserts both
halves of that: the default `DATA_DIR` does not point here, and every institution
name in these files announces itself as synthetic.

## `ipeds_synthetic/` — 13 institutions, one per code path

Real IPEDS column names and the real 6 filenames, so the fixture exercises the
actual `config.FILES` / column plumbing rather than a parallel schema.

| UNITID | What it is there to prove |
|---|---|
| 999001 | Private, complete. The healthy case: `NPT442` + `GRN4A42` → COA. |
| 999002 | Public, complete. `NPIS442` + `GIS4A42` — the coalescing that once dropped all 726 publics. |
| 999003 | `SATVR75`/`SATMT75`/`DVADM01` = `-2`. Sentinels must become NaN → `DATA_GAPS`, never a score of −2. |
| 999004 | Blank `GBA4RTT`. No grad rate → `RISK_FLAGS=no_grad_rate`, no Value Score, excluded from the ranking but still in the dataset. |
| 999005 | Blank `TUITION2`. Dropped: no financial basis to analyse. |
| 999006 | `ICLEVEL=2` (two-year). Dropped by the 4-year filter. |
| 999007 | `HDEGOFR1=1` (non-degree). Dropped by the degree-granting filter. |
| 999008 | Present in HD and IC, absent from SFA. The left merge leaves NaN; the row is dropped, not zero-filled. |
| 999009 | `IGRNT_A` (9,000) exceeds COA (5,000) → `aid_share_above_coa`. Impossible for one student; flagged rather than left to top the ranking. |
| 999010 | `NPT442` with no `GRN4A42`, plus `GBA4RTT=-2`. COA unrecoverable → `incomplete_coa` *and* `no_grad_rate`. |
| 999011 | `CONTROL=3` → "Private for-profit". |
| 999012 | `CONTROL=-3` → "Other". The label must not fail or guess on an unmapped control. |
| 999013 | `IGRNT_A=-2`. A sentinel in a *required* column drops the row; it is never scored as −2. |

Eight of the thirteen survive cleaning. Five are dropped, each for a different
documented reason — the drops are the point, not an accident of the sample.

## `ipeds_all_dropped/` — the empty-result case

Two institutions, neither reporting any financials. Every row is dropped, so the
dataset comes out empty. `build_dataset()` must raise `DatasetUnavailable` naming the
directory and the counts, instead of handing an empty frame to `meta()`, where
`np.nanmin` failed with *"zero-size array to reduction operation minimum"* — a
message that names neither the cause nor where to look.
