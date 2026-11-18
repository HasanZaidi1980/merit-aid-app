# Observed API Contract — Merit Aid Finder

Everything here was captured from the **live** app at `http://136.68.78.253/`. This is the real behavior an accurate rebuild must match. (This is the observable *contract*, not the source code — see ANALYSIS.md.)

## Frontend assets
- `GET /` → static HTML shell (served by nginx)
- `GET /assets/index-CYJlgjog.js` → bundled app (Vite build)
- `GET /assets/index-Bt4x7w8r.css` → bundled styles
- Google Fonts: Inter (400–800)

## API endpoints

### `GET /api/meta`
Dataset stats + defaults + the toggleable dimensions. Response as captured from the
reference app, **plus** the three keys this reconstruction adds —
`no_merit_aid_count`, `awards_merit_count`, `merit_policy_coverage`,
`metric_notes`, `value_weights` and `defaults.exclude_no_merit`,
each marked below. (The reference values for `flagged_count`, `data_gap_count` and
`unscoreable_count` predate the RISK_FLAGS/DATA_GAPS split and no longer match ours.)

**`median_aid_share` is no longer compared against the reference's 0.3184.** That
figure was derived from the reference app's understated cost of attendance; Phase 3
replaced ours with the basket IPEDS itself nets against, so the two are not measuring
the same denominator. Ours is 0.2942. See `FORMULAS.md` §3.
```json
{
  "colleges_in_dataset": 1907,
  "median_aid_share": 0.3184,
  "median_mgi": 0.4515,
  "net_price_min": 2200,
  "net_price_max": 63997,
  "flagged_count": 1352,
  "data_gap_count": 0,
  "unscoreable_count": 0,
  "sat_coverage": 985,
  "no_merit_aid_count": 5,                                       /* added */
  "awards_merit_count": 19,                                      /* added */
  "merit_policy_coverage": { "verified": 24, "attempted": 56, "..." : "..." },
  "metric_notes": { "grant_aid": "...", "merit_policy": "...",
                    "cost_of_attendance": "..." },               /* added */
  "value_weights": {                                             /* added */
    "affordability": 0.3333, "graduation": 0.3333, "generosity": 0.3333
  },
  "defaults": {
    "max_net_price": 25000,
    "mgi_at_least_median": true,
    "top_n": 20,
    "exclude_flagged": true,
    "exclude_no_merit": false                                    /* added */
  },
  "dimensions": [
    { "key": "sticker",    "label": "Total Cost of Attendance", "column": "COA",          "required_for": ["Aid Share", "Discount"] },
    { "key": "grant",      "label": "Avg Institutional Grant", "column": "IGRNT_A",        "required_for": ["Aid Share", "Value Score"] },
    { "key": "net_price",  "label": "Net Price",               "column": "NET_PRICE_MID",  "required_for": ["Value Score", "Discount"] },
    { "key": "admit_rate", "label": "Admissions Rate",         "column": "...",  "required_for": ["..."] }
    /* list continues: grad rate, SAT — full set drives the sidebar toggles */
  ]
}
```

### `GET /api/colleges`
Ranked shortlist. Query params (all observed):
- `max_net_price` (e.g. `25000`)
- `mgi_at_least_median` (`true`/`false`)
- `top_n` (e.g. `20`)
- `exclude_flagged` (`true`/`false`)
- `exclude_no_merit` (`true`/`false`) — **added**, defaults `false`

Each college row has these 27 fields:
```
RANK, UNITID, INSTNM, STABBR, CONTROL_LABEL,
COA, COA_COMPLETE, TUITION2, IGRNT_A, NET_PRICE_MID, DISCOUNT,
ADMISSIONS_RATE, GRAD_RATE, SATVR75, SATMT75, SAT_TOTAL_75,
AID_SHARE, VALUE_SCORE, COMPONENTS_USED, RISK_FLAGS, DATA_GAPS,
MERIT_POLICY, MERIT_POLICY_YEAR, MERIT_POLICY_STATUS,
MGI, NET_PRICE_RATIO, COMPOSITE_LEGACY
```

> **Changed 2026-10-28, extended 2026-11-17** — this reconstruction returns **27**
> fields, not the 23 observed on the reference app. `DATA_GAPS` and `MERIT_POLICY`
> were added first; `MERIT_POLICY_YEAR` and `MERIT_POLICY_STATUS` followed in Phase 4.
> `RISK_FLAGS` has narrowed; see the notes below. All four additions are
> backward-compatible: nothing was renamed or removed, so a client reading the
> original 23 is unaffected. `test_api_row_schema_is_additive_only` asserts the
> original 23 remain a subset and pins the field count at 27.
Notes:
- `VALUE_SCORE` (0–100) = mean of 3 percentile ranks: affordability, grad rate, aid
  generosity. A college missing any component has **no** Value Score and is excluded
  from every ranking — it is never imputed or scored on a subset.
- `COMPOSITE_LEGACY` = the original assignment formula, retained for comparison.
- `AID_SHARE` = institutional grants ÷ total sticker (COA).
- `COMPONENTS_USED` = which inputs were available for that row.
- `RISK_FLAGS` = problems that make the **ranking** untrustworthy: `incomplete_coa`
  (sticker reconstructed from only some charge components, so Discount and Aid Share
  are measured against an understated total) and `no_grad_rate`. The
  `exclude_flagged` parameter drops exactly these rows and nothing else.
- `DATA_GAPS` = missing fields that affect **display only**: `no_sat`,
  `no_admit_rate`. Neither feeds Value Score, so neither ever removes a college from
  the ranking. They previously lived in `RISK_FLAGS`, which meant the default view
  discarded most of the dataset over fields with no bearing on the result.
- `MERIT_POLICY` = `need_only`, `awards_merit` or `unknown`, read from that
  institution's own Common Data Set section H2A line n. **`unknown` means unchecked,
  never "awards merit aid" and never "awards none"** — it is 1,883 of 1,907 colleges.
  It is a fact about the institution rather than a property of our data, so it is in
  neither flag column and affects no score; `exclude_no_merit` is the only thing that
  reads it, and it drops `need_only` only.
- `MERIT_POLICY_YEAR` *(added 2026-11-17)* = the CDS edition the verdict came from,
  e.g. `"2025-26"`; `""` when there is no verdict. The year is load-bearing, not
  decoration: Yale answers line n 6/28/1, 6/24/0 and 0/0/0 in three consecutive
  editions. A verdict more than `coverage.stale_after_editions` behind
  `coverage.current_edition` expires back to `unknown` on its own.
- `MERIT_POLICY_STATUS` *(added 2026-11-17)* = `resolved` (24),
  `attempted_unresolved` (32) or `not_checked` (1,851). Splits the two causes of
  `unknown` — we read the college's CDS and H2A was not readable, versus nobody
  looked. Both are still `unknown` as a policy; the status never upgrades to an
  answer. Clients should render them differently, because one dash for both is how a
  coverage gap starts reading as a finding.

### `GET /api/merit-policy`  *(added)*
Every CDS-verified record with its provenance, plus the institutions the check could
not resolve — so a client can state how far the sourcing got rather than imply
completeness.
```json
{
  "verified": [{
    "unitid": 166027, "name": "Harvard University", "policy": "awards_merit",
    "cds_year": "2025-26", "line_n": "4 / 20", "avg": "$4,728 / $5,279",
    "note": "Previously labelled need-based only. That was wrong.",
    "source_url": "https://...CDS_2025-2026.pdf",
    "checked_on": "2026-11-17", "method": "parsed+read"
  }],
  "unresolved": [{ "unitid": 217156, "name": "Brown University", "reason": "CDS download 404" }],
  "coverage": { "verified": 24, "need_only": 5, "awards_merit": 19,
                "attempted": 56, "unresolved": 32, "stale": 0,
                "checked_on": "2026-11-17",
                "current_edition": "2025-26", "stale_after_editions": 2,
                "source": "Common Data Set section H2A, line n",
                "scope": "the default top 50 shortlist, attempted in full; ...",
                "sector_caveat": "96% private against 57.4% of the dataset; ..." },
  "status": "cds_sourced",
  "note": "..."
}
```
**Shape changed 2026-11-17.** It previously returned `need_only` / `count` / `basis`
from a hand-compiled roster. That roster was wrong for 5 of its 26 entries, so it was
replaced by per-institution CDS sourcing. `policy` is `need_only`, `awards_merit` or
(by absence) `unknown` — see `FORMULAS.md` §4.

**Read `coverage.verified` against `coverage.attempted`, never against
`colleges_in_dataset`.** The two figures mean different things and only the pair is
honest: attempted is what we committed to, resolved is what the institutions actually
published. Sourcing was scoped to the default top 50 and attempted in full there — 50
of 50 attempted, 23 resolved — because a full-dataset crawl measured ~38% end-to-end
and was rejected. `coverage.scope` and `coverage.sector_caveat` carry that context
through the API so a client cannot report the rate without it: the top 50 is 96%
private nonprofit against 57.4% of the dataset.

### `GET /api/education/distributions`  *(added)*
Reference distributions for the education section, ~8 KB. Lets the browser re-score a
hypothetical college on every slider drag without a request per drag.
```json
{
  "n": 1907,
  "scored_n": 1727,
  "components": {
    "net_price": { "column": "NET_PRICE_MID", "higher_is_better": false, "breakpoints": [ /* 101 */ ] },
    "grad_rate": { "...": "..." },
    "aid_share": { "...": "..." }
  },
  "value_score_breakpoints": [ /* 101 */ ],
  "dimensions": {
    "sticker": { "n": 1907, "min": 2229, "p25": 0, "median": 27141, "p75": 0, "max": 83421,
                 "bin_edges": [ /* 29 */ ], "bin_counts": [ /* 28 */ ] }
  }
}
```
- `breakpoints` are p0…p100 inclusive, so a percentile rank inverts by binary search.
- `scored_n` (1,727) is smaller than `n` (1,907) because a missing graduation rate
  makes a college unscoreable. Rank a hypothetical against `scored_n`, not `n`.
- Every summary is computed over non-null values only — SAT covers 985 colleges, and
  counting the blanks would drag the median toward zero.

### ~~`GET /api/rag/status`~~ and ~~`POST /api/rag/query`~~ — **removed 2026-11-17**

A deliberate, stated divergence from the reference app, which does expose both.

They served mission-statement retrieval built on `IC2022Mission.csv` — a file that is
**sample-generator output**, not IPEDS data. Verified against the IPEDS data center:
`IC2022Mission.zip` returns 404, as does `IC2008Mission.zip`; 2006 and 2007 return 200.
IPEDS has published no mission file since 2007, so these endpoints could only ever have
served fabricated text. `CLAUDE.md` §2 forbids shipping known-untrue content, so they
were removed rather than reproduced. The real 2007 file reaches only 36.2% of our
universe (7 of the default top 20) — measured, not assumed. Full reasoning in
`PROJECT_STATE.md` Phase 3.5.

Clients should expect **5 endpoints**, not 7.

## Observed reliability note
`/api/*` intermittently returned **502 Bad Gateway** while the static site stayed up — backend upstream was briefly unreachable. Real, reproducible; worth flagging to your friend.
