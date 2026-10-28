# Observed API Contract — Merit Aid Finder

Everything here was captured from the **live** app at `http://136.68.78.253/`. This is the real behavior an accurate rebuild must match. (This is the observable *contract*, not the source code — see ANALYSIS.md.)

## Frontend assets
- `GET /` → static HTML shell (served by nginx)
- `GET /assets/index-CYJlgjog.js` → bundled app (Vite build)
- `GET /assets/index-Bt4x7w8r.css` → bundled styles
- Google Fonts: Inter (400–800)

## API endpoints

### `GET /api/meta`
Dataset stats + defaults + the toggleable dimensions. Real response:
```json
{
  "colleges_in_dataset": 1907,
  "median_aid_share": 0.3184,
  "net_price_min": 2200,
  "net_price_max": 63997,
  "flagged_count": 1352,
  "sat_coverage": 985,
  "defaults": {
    "max_net_price": 25000,
    "mgi_at_least_median": true,
    "top_n": 20,
    "exclude_flagged": true
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

Each college row has these 23 fields:
```
RANK, UNITID, INSTNM, STABBR, CONTROL_LABEL,
COA, COA_COMPLETE, TUITION2, IGRNT_A, NET_PRICE_MID, DISCOUNT,
ADMISSIONS_RATE, GRAD_RATE, SATVR75, SATMT75, SAT_TOTAL_75,
AID_SHARE, VALUE_SCORE, COMPONENTS_USED, RISK_FLAGS,
MGI, NET_PRICE_RATIO, COMPOSITE_LEGACY
```
Notes:
- `VALUE_SCORE` (0–100) = mean of 3 percentile ranks: affordability, grad rate, aid generosity.
- `COMPOSITE_LEGACY` = the original assignment formula, retained for comparison.
- `AID_SHARE` = institutional grants ÷ total sticker (COA).
- `COMPONENTS_USED` / `RISK_FLAGS` = which inputs were available / data-quality warnings (graceful degradation).

### `GET /api/rag/status`
```json
{ "index_ready": true, "api_key_set": true }
```

### `POST /api/rag/query`  (the "Ask" button)
Not fully captured (backend returned 502 during probing), but the UI sends a natural-language question and the answer is drawn only from the mission statements of the colleges currently shown. Expected shape: `{ "question": "...", ... }` → `{ "answer": "...", "sources": [...] }`.

## Observed reliability note
`/api/*` intermittently returned **502 Bad Gateway** while the static site stayed up — backend upstream was briefly unreachable. Real, reproducible; worth flagging to your friend.
