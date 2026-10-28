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
`no_merit_aid_count`, `metric_notes` and `defaults.exclude_no_merit`, each marked
below. (The reference values for `flagged_count`, `data_gap_count` and
`unscoreable_count` predate the RISK_FLAGS/DATA_GAPS split and no longer match ours.)
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
  "no_merit_aid_count": 26,                                      /* added */
  "metric_notes": { "grant_aid": "...", "merit_policy": "..." }, /* added */
  "defaults": {
    "max_net_price": 25000,
    "mgi_at_least_median": true,
    "top_n": 20,
    "exclude_flagged": true,
    "exclude_no_merit": false                                    /* added */
  },
  "dimensions": [
    { "key": "sticker",    "label": "Total Sticker (COA)",     "column": "COA",           "required_for": ["Aid Share", "Discount"] },
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

Each college row has these 25 fields:
```
RANK, UNITID, INSTNM, STABBR, CONTROL_LABEL,
COA, COA_COMPLETE, TUITION2, IGRNT_A, NET_PRICE_MID, DISCOUNT,
ADMISSIONS_RATE, GRAD_RATE, SATVR75, SATMT75, SAT_TOTAL_75,
AID_SHARE, VALUE_SCORE, COMPONENTS_USED, RISK_FLAGS, DATA_GAPS,
MERIT_POLICY, MGI, NET_PRICE_RATIO, COMPOSITE_LEGACY
```

> **Changed 2026-10-28** — this reconstruction returns **25** fields, not the 23
> observed on the reference app. `DATA_GAPS` and `MERIT_POLICY` are new and
> `RISK_FLAGS` has narrowed; see the notes below. Both additions are
> backward-compatible: nothing was renamed or removed, so a client reading the
> original 23 is unaffected. `test_api_row_schema_is_additive_only` asserts the
> original 23 remain a subset.
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
- `MERIT_POLICY` = `need_only` for institutions on a curated list that publicly award
  no merit scholarships, `unknown` otherwise. **`unknown` means unchecked, never
  "awards merit aid"** — the list covers 26 of 1,907 colleges. It is a fact about the
  institution rather than a property of our data, so it is in neither flag column and
  affects no score; `exclude_no_merit` is the only thing that reads it.

### `GET /api/merit-policy`  *(added)*
The curated roster itself, so a client can state the list's size and sourcing rather
than imply completeness.
```json
{
  "need_only": [{ "unitid": 217156, "name": "Brown University", "basis": "ivy_agreement" }],
  "count": 26,
  "status": "provisional",
  "note": "IPEDS reports total institutional grant aid (IGRNT_A) with no need-versus-merit split..."
}
```
`basis` is `ivy_agreement` (the Ivy League agreement commits all eight members to
need-based aid only) or `published` (the institution's own aid pages state it).

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

### `GET /api/rag/status`
```json
{ "index_ready": true, "api_key_set": true }
```

### `POST /api/rag/query`  (the "Ask" button)
Not fully captured (backend returned 502 during probing), but the UI sends a natural-language question and the answer is drawn only from the mission statements of the colleges currently shown. Expected shape: `{ "question": "...", ... }` → `{ "answer": "...", "sources": [...] }`.

## Observed reliability note
`/api/*` intermittently returned **502 Bad Gateway** while the static site stayed up — backend upstream was briefly unreachable. Real, reproducible; worth flagging to your friend.
